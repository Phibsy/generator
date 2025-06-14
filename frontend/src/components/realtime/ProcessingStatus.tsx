// frontend/src/components/realtime/ProcessingStatus.tsx
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useWebSocket } from '@/components/providers/WebSocketProvider'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, XCircle, Loader2, Sparkles } from 'lucide-react'

interface ProcessingTask {
  id: string
  title: string
  type: string
  progress: number
  status: string
  startedAt: string
}

export function ProcessingStatus() {
  const { progress: progressUpdates, isConnected } = useWebSocket()
  const [activeTasks, setActiveTasks] = useState<ProcessingTask[]>([])
  
  useEffect(() => {
    // Update active tasks from progress updates
    const tasks = Object.entries(progressUpdates)
      .filter(([_, update]) => update.status !== 'completed' && update.status !== 'failed')
      .map(([taskId, update]) => ({
        id: taskId,
        title: update.details?.project_title || 'Processing...',
        type: update.details?.task_type || 'video',
        progress: update.progress,
        status: update.status,
        startedAt: update.timestamp || new Date().toISOString(),
      }))
    
    setActiveTasks(tasks)
  }, [progressUpdates])
  
  if (activeTasks.length === 0) {
    return null
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 50 }}
      className="fixed bottom-4 right-4 z-50 w-96"
    >
      <Card className="shadow-xl">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">
              Processing Tasks
            </CardTitle>
            <Badge variant={isConnected ? 'default' : 'secondary'}>
              {isConnected ? 'Connected' : 'Offline'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <AnimatePresence>
            {activeTasks.map((task) => (
              <motion.div
                key={task.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-sm font-medium">{task.title}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(task.progress)}%
                  </span>
                </div>
                <Progress value={task.progress} className="h-2" />
                <p className="text-xs text-muted-foreground">{task.status}</p>
              </motion.div>
            ))}
          </AnimatePresence>
        </CardContent>
      </Card>
    </motion.div>
  )
}
