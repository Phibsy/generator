// frontend/src/hooks/useProjectProgress.ts
import { useEffect, useState } from 'react'
import { useWebSocket } from '@/components/providers/WebSocketProvider'
import { projectService } from '@/services/projects'
import { Project } from '@/types'

export function useProjectProgress(projectId: number) {
  const { progress } = useWebSocket()
  const [project, setProject] = useState<Project | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  
  // Find progress for this project
  const projectProgress = Object.values(progress).find(
    p => p.details?.project_id === projectId
  )
  
  useEffect(() => {
    loadProject()
  }, [projectId])
  
  useEffect(() => {
    // Reload project when processing completes
    if (projectProgress?.status === 'completed') {
      loadProject()
    }
  }, [projectProgress?.status])
  
  const loadProject = async () => {
    try {
      const data = await projectService.getProject(projectId)
      setProject(data)
    } catch (error) {
      console.error('Failed to load project:', error)
    } finally {
      setIsLoading(false)
    }
  }
  
  return {
    project,
    isLoading,
    progress: projectProgress?.progress || 0,
    status: projectProgress?.status || project?.status || 'unknown',
    isProcessing: project?.status === 'processing',
    reload: loadProject,
  }
}
