// frontend/src/components/projects/ProjectCard.tsx
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Project, ProjectStatus } from '@/types'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useVideoProgress } from '@/hooks/useVideoProgress'
import {
  Play,
  Download,
  Share2,
  MoreVertical,
  Eye,
  Heart,
  MessageCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import Image from 'next/image'
import { formatDate, formatDuration } from '@/utils/format'

interface ProjectCardProps {
  project: Project
  onUpdate?: () => void
}

export function ProjectCard({ project, onUpdate }: ProjectCardProps) {
  const { progress, status, isProcessing } = useVideoProgress(
    project.status === ProjectStatus.PROCESSING ? project.id.toString() : undefined
  )
  
  const getStatusIcon = () => {
    switch (project.status) {
      case ProjectStatus.COMPLETED:
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case ProjectStatus.PROCESSING:
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case ProjectStatus.FAILED:
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }
  
  const getStatusColor = () => {
    switch (project.status) {
      case ProjectStatus.COMPLETED:
        return 'bg-green-100 text-green-800'
      case ProjectStatus.PROCESSING:
        return 'bg-blue-100 text-blue-800'
      case ProjectStatus.FAILED:
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }
  
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Card className="overflow-hidden hover:shadow-lg transition-shadow">
        <div className="relative aspect-video bg-gradient-to-br from-gray-800 to-gray-900">
          {project.thumbnail_path ? (
            <Image
              src={project.thumbnail_path}
              alt={project.title}
              fill
              className="object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <Play className="h-12 w-12 text-gray-600" />
            </div>
          )}
          
          {project.duration && (
            <div className="absolute bottom-2 right-2 rounded bg-black/70 px-2 py-1 text-xs text-white">
              {formatDuration(project.duration)}
            </div>
          )}
        </div>
        
        <CardContent className="p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <h3 className="font-semibold line-clamp-1">{project.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                {project.description}
              </p>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="ml-2">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {project.status === ProjectStatus.COMPLETED && (
                  <>
                    <DropdownMenuItem>
                      <Play className="mr-2 h-4 w-4" />
                      Preview
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Download className="mr-2 h-4 w-4" />
                      Download
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Share2 className="mr-2 h-4 w-4" />
                      Share
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem className="text-red-600">
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              <Badge variant="secondary" className={getStatusColor()}>
                {project.status}
              </Badge>
            </div>
            
            <p className="text-xs text-muted-foreground">
              {formatDate(project.created_at)}
            </p>
          </div>
          
          {isProcessing && (
            <div className="mt-4">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{status}</span>
                <span>{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} className="mt-1" />
            </div>
          )}
          
          {project.status === ProjectStatus.COMPLETED && (
            <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
              <div className="flex items-center space-x-3">
                <span className="flex items-center">
                  <Eye className="mr-1 h-3 w-3" />
                  {project.analytics?.total_views || 0}
                </span>
                <span className="flex items-center">
                  <Heart className="mr-1 h-3 w-3" />
                  {project.analytics?.total_likes || 0}
                </span>
                <span className="flex items-center">
                  <MessageCircle className="mr-1 h-3 w-3" />
                  {project.analytics?.total_comments || 0}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
