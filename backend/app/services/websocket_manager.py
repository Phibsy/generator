# backend/app/services/websocket_manager.py
"""
🔌 REELS GENERATOR - WebSocket Manager
Real-time progress updates for video processing
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import json
import asyncio
import logging
import redis.asyncio as redis
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manage WebSocket connections and broadcasts"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self.listener_task = None
    
    async def init_redis(self):
        """Initialize Redis connection"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
            self.pubsub = self.redis_client.pubsub()
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        
        # Subscribe to user's progress channel
        await self.init_redis()
        await self.pubsub.subscribe(f"progress_channel:*")
        
        # Start listener if not running
        if not self.listener_task:
            self.listener_task = asyncio.create_task(self._redis_listener())
        
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        await websocket.send_text(message)
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast message to all connections of a user"""
        if user_id in self.active_connections:
            disconnected = []
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected sockets
            for conn in disconnected:
                self.active_connections[user_id].remove(conn)
    
    async def _redis_listener(self):
        """Listen for Redis pub/sub messages"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"].decode()
                    data = json.loads(message["data"])
                    
                    # Extract task_id from channel name
                    if channel.startswith("progress_channel:"):
                        task_id = channel.split(":")[-1]
                        
                        # Find user_id from task_id (implement your logic)
                        # For now, broadcast to all users
                        for user_id, connections in self.active_connections.items():
                            await self.broadcast_to_user(user_id, {
                                "type": "progress",
                                "task_id": task_id,
                                "data": data
                            })
        
        except Exception as e:
            logger.error(f"Redis listener error: {e}")

# Global connection manager
manager = ConnectionManager()

# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

from fastapi import APIRouter, Depends
from ..api.auth import get_current_user_ws

ws_router = APIRouter()

@ws_router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    current_user = Depends(get_current_user_ws)
):
    """WebSocket endpoint for real-time updates"""
    
    # Verify user owns this connection
    if str(current_user.id) != user_id:
        await websocket.close(code=4003, reason="Unauthorized")
        return
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            # Handle ping/pong
            if data == "ping":
                await manager.send_personal_message("pong", websocket)
            
            # Handle task status requests
            elif data.startswith("status:"):
                task_id = data.split(":")[-1]
                status = await get_task_status(task_id)
                await manager.send_personal_message(
                    json.dumps(status),
                    websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_id)

async def get_task_status(task_id: str) -> dict:
    """Get current task status from Redis"""
    if not manager.redis_client:
        await manager.init_redis()
    
    status_data = await manager.redis_client.get(f"progress:{task_id}")
    
    if status_data:
        return json.loads(status_data)
    else:
        return {
            "progress": 0,
            "status": "unknown",
            "details": {}
        }

# ============================================================================
# PROGRESS BROADCASTER
# ============================================================================

class ProgressBroadcaster:
    """Helper class for broadcasting progress updates"""
    
    def __init__(self, task_id: str, user_id: str):
        self.task_id = task_id
        self.user_id = user_id
        self.redis_client = None
    
    async def update(
        self,
        progress: float,
        status: str,
        details: Optional[dict] = None
    ):
        """Send progress update"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        update_data = {
            "progress": progress,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis
        await self.redis_client.setex(
            f"progress:{self.task_id}",
            300,  # 5 minutes TTL
            json.dumps(update_data)
        )
        
        # Publish to channel
        await self.redis_client.publish(
            f"progress_channel:{self.task_id}",
            json.dumps(update_data)
        )
    
    async def complete(self, result: dict):
        """Mark task as complete"""
        await self.update(100, "completed", result)
    
    async def error(self, error_msg: str):
        """Mark task as failed"""
        await self.update(-1, "failed", {"error": error_msg})

# ============================================================================
# FRONTEND WEBSOCKET CLIENT EXAMPLE
# ============================================================================

"""
// frontend/src/services/websocket.ts
export class VideoProcessingWebSocket {
    private ws: WebSocket | null = null;
    private reconnectInterval: number = 5000;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 5;
    
    constructor(
        private userId: string,
        private onProgress: (data: ProgressUpdate) => void,
        private onError: (error: string) => void
    ) {}
    
    connect() {
        const wsUrl = `ws://localhost:8000/ws/${this.userId}`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            
            // Send ping every 30 seconds
            setInterval(() => {
                if (this.ws?.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 30000);
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'progress') {
                    this.onProgress(data.data);
                } else if (data === 'pong') {
                    // Heartbeat response
                }
            } catch (error) {
                console.error('WebSocket message error:', error);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.onError('Connection error');
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.reconnect();
        };
    }
    
    private reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectInterval);
        }
    }
    
    requestStatus(taskId: string) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(`status:${taskId}`);
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Usage in React component
const useVideoProgress = (userId: string) => {
    const [progress, setProgress] = useState<Record<string, ProgressUpdate>>({});
    const wsRef = useRef<VideoProcessingWebSocket | null>(null);
    
    useEffect(() => {
        wsRef.current = new VideoProcessingWebSocket(
            userId,
            (update) => {
                setProgress(prev => ({
                    ...prev,
                    [update.task_id]: update
                }));
            },
            (error) => {
                console.error('WebSocket error:', error);
            }
        );
        
        wsRef.current.connect();
        
        return () => {
            wsRef.current?.disconnect();
        };
    }, [userId]);
    
    return { progress, requestStatus: wsRef.current?.requestStatus };
};
"""
