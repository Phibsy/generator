// frontend/src/services/websocket.ts
import { ProgressUpdate } from '@/types'

export class VideoProcessingWebSocket {
  private ws: WebSocket | null = null
  private reconnectInterval: number = 5000
  private reconnectAttempts: number = 0
  private maxReconnectAttempts: number = 5
  private heartbeatInterval: NodeJS.Timeout | null = null
  
  constructor(
    private userId: string,
    private onProgress: (data: ProgressUpdate) => void,
    private onError: (error: string) => void
  ) {}
  
  connect() {
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/ws/${this.userId}`
    
    this.ws = new WebSocket(wsUrl)
    
    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
      
      // Start heartbeat
      this.startHeartbeat()
    }
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.type === 'progress') {
          this.onProgress(data.data)
        } else if (data.type === 'batch_progress') {
          // Handle batch progress
          this.onProgress({
            task_id: data.batch_id,
            progress: data.progress.progress_percentage,
            status: 'batch_processing',
            details: data.progress
          })
        } else if (data === 'pong') {
          // Heartbeat response
        }
      } catch (error) {
        console.error('WebSocket message error:', error)
      }
    }
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.onError('Connection error')
    }
    
    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.stopHeartbeat()
      this.reconnect()
    }
  }
  
  private startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 30000) // Send ping every 30 seconds
  }
  
  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }
  
  private reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`)
      
      setTimeout(() => {
        this.connect()
      }, this.reconnectInterval)
    } else {
      this.onError('Maximum reconnection attempts reached')
    }
  }
  
  requestStatus(taskId: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(`status:${taskId}`)
    }
  }
  
  disconnect() {
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

// frontend/src/hooks/useVideoProgress.ts
import { useEffect, useRef } from 'react'
import { useWebSocket } from '@/components/providers/WebSocketProvider'
import { ProgressUpdate } from '@/types'

export function useVideoProgress(taskId?: string) {
  const { progress, requestStatus } = useWebSocket()
  const currentProgress = taskId ? progress[taskId] : null
  
  useEffect(() => {
    if (taskId && !currentProgress) {
      // Request initial status
      requestStatus(taskId)
    }
  }, [taskId, currentProgress, requestStatus])
  
  return {
    progress: currentProgress?.progress || 0,
    status: currentProgress?.status || 'unknown',
    details: currentProgress?.details || {},
    isProcessing: currentProgress?.status === 'processing',
    isCompleted: currentProgress?.status === 'completed',
    isFailed: currentProgress?.status === 'failed',
  }
}

// frontend/src/hooks/useBatchProgress.ts
import { useWebSocket } from '@/components/providers/WebSocketProvider'

export function useBatchProgress(batchId?: string) {
  const { progress } = useWebSocket()
  const batchProgress = batchId ? progress[batchId] : null
  
  return {
    progress: batchProgress?.progress || 0,
    status: batchProgress?.status || 'unknown',
    details: batchProgress?.details || {},
    completed: batchProgress?.details?.completed || 0,
    failed: batchProgress?.details?.failed || 0,
    pending: batchProgress?.details?.pending || 0,
    total: batchProgress?.details?.total || 0,
  }
}
