// frontend/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';

export interface WebSocketMessage {
  type: string;
  data: any;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onClose?: (event: CloseEvent) => void;
  onOpen?: (event: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(options?: UseWebSocketOptions) {
  const { user } = useAuthStore();
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout>();

  const connect = () => {
    if (!user?.id) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/ws/${user.id}`;
    
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = (event) => {
      setIsConnected(true);
      reconnectAttempts.current = 0;
      options?.onOpen?.(event);
      
      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send('ping');
        }
      }, 30000);
      
      ws.current.addEventListener('close', () => clearInterval(pingInterval));
    };

    ws.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setLastMessage(message);
        options?.onMessage?.(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      options?.onError?.(error);
    };

    ws.current.onclose = (event) => {
      setIsConnected(false);
      options?.onClose?.(event);
      
      // Attempt to reconnect
      if (
        reconnectAttempts.current < (options?.maxReconnectAttempts || 5) &&
        !event.wasClean
      ) {
        reconnectAttempts.current++;
        const interval = options?.reconnectInterval || 5000;
        
        reconnectTimeout.current = setTimeout(() => {
          console.log(`Reconnecting... Attempt ${reconnectAttempts.current}`);
          connect();
        }, interval);
      }
    };
  };

  const disconnect = () => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }
    
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
  };

  const sendMessage = (message: string | object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const data = typeof message === 'string' ? message : JSON.stringify(message);
      ws.current.send(data);
    } else {
      console.error('WebSocket is not connected');
    }
  };

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [user?.id]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    disconnect,
    reconnect: connect,
  };
}
