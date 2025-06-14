// frontend/src/app/dashboard/create/page.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { ContentStep } from '@/components/creator/ContentStep'
import { VoiceStep } from '@/components/creator/VoiceStep'
import { VideoStep } from '@/components/creator/VideoStep'
import { ReviewStep } from '@/components/creator/ReviewStep'
import { StepIndicator } from '@/components/creator/StepIndicator'
import { useToast } from '@/components/ui/use-toast'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const steps = [
  { id: 'content', title: 'Content', description: 'Create your script' },
  { id: 'voice', title: 'Voice', description: 'Choose voice and style' },
  { id: 'video', title: 'Video', description: 'Customize video settings' },
  { id: 'review', title: 'Review', description: 'Review and generate' },
]

export default function CreatePage() {
  const router = useRouter()
  const { toast } = useToast()
  const [currentStep, setCurrentStep] = useState(0)
  const [projectData, setProjectData] = useState<any>({
    title: '',
    topic: '',
    target_audience: '',
    video_style: 'educational',
    duration: 60,
    tone: 'engaging',
    include_call_to_action: true,
    voice_id: 'rachel',
    background_video: 'minecraft',
    subtitle_style: 'modern',
    subtitle_animation: 'word_by_word',
    music_preset: 'upbeat',
    music_volume: 0.1,
    effects_enabled: true,
    effects_preset: 'dynamic',
    quality: 'medium',
  })
  
  const updateProjectData = (data: Partial<typeof projectData>) => {
    setProjectData(prev => ({ ...prev, ...data }))
  }
  
  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(prev => prev + 1)
    }
  }
  
  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }
  
  const handleCreate = async () => {
    try {
      // Create project and start generation
      const project = await projectService.createProject({
        title: projectData.title,
        description: `${projectData.topic} for ${projectData.target_audience}`,
        topic: projectData.topic,
        target_audience: projectData.target_audience,
        video_style: projectData.video_style,
        duration: projectData.duration,
      })
      
      // Start content generation
      await contentService.generateContentForProject(project.id)
      
      toast({
        title: 'Project created!',
        description: 'Your video is being generated...',
      })
      
      router.push(`/dashboard/projects/${project.id}`)
    } catch (error) {
      toast({
        title: 'Creation failed',
        description: 'Please try again',
        variant: 'destructive',
      })
    }
  }
  
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Create New Video</h1>
        <p className="mt-2 text-muted-foreground">
          Follow the steps to create your AI-powered video
        </p>
      </div>
      
      <StepIndicator steps={steps} currentStep={currentStep} />
      
      <div className="mt-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
          >
            {currentStep === 0 && (
              <ContentStep
                data={projectData}
                onUpdate={updateProjectData}
              />
            )}
            {currentStep === 1 && (
              <VoiceStep
                data={projectData}
                onUpdate={updateProjectData}
              />
            )}
            {currentStep === 2 && (
              <VideoStep
                data={projectData}
                onUpdate={updateProjectData}
              />
            )}
            {currentStep === 3 && (
              <ReviewStep
                data={projectData}
                onUpdate={updateProjectData}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      
      <div className="mt-8 flex justify-between">
        <Button
          variant="outline"
          onClick={handlePrev}
          disabled={currentStep === 0}
        >
          <ChevronLeft className="mr-2 h-4 w-4" />
          Previous
        </Button>
        
        {currentStep < steps.length - 1 ? (
          <Button onClick={handleNext}>
            Next
            <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={handleCreate}>
            Create Video
          </Button>
        )}
      </div>
    </div>
  )
}
