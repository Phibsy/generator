// frontend/src/services/projects.ts
import { apiClient } from '@/lib/api-client'
import {
  Project,
  ProjectCreate,
  ProjectUpdate,
  PaginatedResponse,
  ContentGenerationResponse,
  DashboardStats,
  VideoSettings,
  BatchJob,
  BatchProgress,
  VideoAnalytics,
} from '@/types'

export const projectService = {
  // ============================================================================
  // PROJECT CRUD OPERATIONS
  // ============================================================================
  
  async getProjects(params?: {
    page?: number
    limit?: number
    status?: string
    search?: string
    sort_by?: string
    order?: 'asc' | 'desc'
  }): Promise<PaginatedResponse<Project>> {
    const { data } = await apiClient.get<PaginatedResponse<Project>>('/projects', {
      params,
    })
    return data
  },

  async getProject(id: number): Promise<Project> {
    const { data } = await apiClient.get<Project>(`/projects/${id}`)
    return data
  },

  async createProject(project: ProjectCreate): Promise<Project> {
    const { data } = await apiClient.post<Project>('/projects', project)
    return data
  },

  async updateProject(id: number, updates: ProjectUpdate): Promise<Project> {
    const { data } = await apiClient.put<Project>(`/projects/${id}`, updates)
    return data
  },

  async deleteProject(id: number): Promise<void> {
    await apiClient.delete(`/projects/${id}`)
  },

  async duplicateProject(id: number): Promise<Project> {
    const { data } = await apiClient.post<Project>(`/projects/${id}/duplicate`)
    return data
  },

  // ============================================================================
  // CONTENT GENERATION
  // ============================================================================
  
  async generateContent(id: number): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/generate-content`
    )
    return data
  },

  async regenerateContent(id: number, settings?: {
    tone?: string
    style?: string
    include_cta?: boolean
  }): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/regenerate-content`,
      settings
    )
    return data
  },

  async optimizeContent(id: number, platform: string): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/optimize-content`,
      null,
      { params: { platform } }
    )
    return data
  },

  async analyzeContent(id: number): Promise<{
    engagement_score: number
    hook_strength: number
    clarity_score: number
    emotion_score: number
    cta_effectiveness: number
    improvement_suggestions: string[]
    viral_potential: 'low' | 'medium' | 'high'
  }> {
    const { data } = await apiClient.get(`/projects/${id}/content-analysis`)
    return data
  },

  async generateVariations(id: number, count: number = 3): Promise<{
    variations: Array<{
      id: string
      script: string
      focus: string
      tone: string
    }>
  }> {
    const { data } = await apiClient.post(
      `/projects/${id}/generate-variations`,
      { count }
    )
    return data
  },

  // ============================================================================
  // TEXT-TO-SPEECH
  // ============================================================================
  
  async generateTTS(
    id: number,
    voiceId?: string,
    speed?: number
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/generate-tts`,
      { voice_id: voiceId, speed }
    )
    return data
  },

  async regenerateTTS(
    id: number,
    voiceId: string,
    speed: number = 1.0
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/regenerate-tts`,
      { voice_id: voiceId, speed }
    )
    return data
  },

  async previewTTS(
    text: string,
    voiceId: string,
    speed: number = 1.0
  ): Promise<{ preview_url: string }> {
    const { data } = await apiClient.post('/tts/preview', {
      text: text.slice(0, 100), // First 100 chars for preview
      voice_id: voiceId,
      speed,
    })
    return data
  },

  // ============================================================================
  // VIDEO GENERATION
  // ============================================================================
  
  async generateVideo(
    id: number,
    settings?: Partial<VideoSettings>
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/generate-video`,
      settings
    )
    return data
  },

  async startVideoGeneration(
    projectId: number,
    settings: VideoSettings
  ): Promise<{
    task_id: string
    estimated_time: number
    queue_position: number
  }> {
    const { data } = await apiClient.post(
      `/projects/${projectId}/generate-video`,
      settings
    )
    return data
  },

  async generateAdvancedVideo(
    id: number,
    settings: VideoSettings
  ): Promise<{
    task_id: string
    project_id: number
    status: string
  }> {
    const { data } = await apiClient.post(
      `/projects/${id}/generate-advanced-video`,
      settings
    )
    return data
  },

  async regenerateVideo(
    id: number,
    settings: Partial<VideoSettings>
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/regenerate-video`,
      settings
    )
    return data
  },

  // ============================================================================
  // BATCH OPERATIONS
  // ============================================================================
  
  async startBatchGeneration(
    projectIds: number[],
    settings: Partial<VideoSettings>,
    priority?: 'low' | 'normal' | 'high' | 'urgent'
  ): Promise<BatchJob> {
    const { data } = await apiClient.post<BatchJob>('/batch/create', {
      project_ids: projectIds,
      settings,
      priority: priority || 'normal',
    })
    return data
  },

  async getBatchStatus(batchId: string): Promise<BatchProgress> {
    const { data } = await apiClient.get<BatchProgress>(`/batch/${batchId}/status`)
    return data
  },

  async getUserBatches(params?: {
    status?: string
    limit?: number
  }): Promise<BatchJob[]> {
    const { data } = await apiClient.get<BatchJob[]>('/batch/list', { params })
    return data
  },

  async cancelBatch(batchId: string): Promise<void> {
    await apiClient.post(`/batch/${batchId}/cancel`)
  },

  async retryBatchFailures(batchId: string): Promise<BatchJob> {
    const { data } = await apiClient.post<BatchJob>(`/batch/${batchId}/retry`)
    return data
  },

  // ============================================================================
  // PUBLISHING & SOCIAL MEDIA
  // ============================================================================
  
  async publishToSocial(
    id: number,
    platforms: string[],
    settings: {
      title?: string
      description?: string
      hashtags?: string[]
      scheduled_for?: string
    }
  ): Promise<{
    publications: Array<{
      platform: string
      status: string
      url?: string
      error?: string
    }>
  }> {
    const { data } = await apiClient.post(`/projects/${id}/publish`, {
      platforms,
      ...settings,
    })
    return data
  },

  async schedulePublication(
    id: number,
    platform: string,
    scheduledFor: Date,
    settings: any
  ): Promise<{
    publication_id: string
    scheduled_for: string
    status: string
  }> {
    const { data } = await apiClient.post(`/projects/${id}/schedule`, {
      platform,
      scheduled_for: scheduledFor.toISOString(),
      settings,
    })
    return data
  },

  async getPublications(projectId: number): Promise<Array<{
    id: number
    platform: string
    status: string
    published_at?: string
    url?: string
    views: number
    likes: number
    comments: number
    shares: number
  }>> {
    const { data } = await apiClient.get(`/projects/${projectId}/publications`)
    return data
  },

  // ============================================================================
  // ANALYTICS & STATS
  // ============================================================================
  
  async getDashboardStats(): Promise<DashboardStats> {
    const { data } = await apiClient.get<DashboardStats>('/analytics/dashboard')
    return data
  },

  async getProjectAnalytics(id: number): Promise<VideoAnalytics> {
    const { data } = await apiClient.get<VideoAnalytics>(
      `/projects/${id}/analytics`
    )
    return data
  },

  async getProjectInsights(id: number): Promise<{
    performance_score: number
    best_performing_platform: string
    peak_engagement_time: string
    audience_retention: number
    suggestions: string[]
  }> {
    const { data } = await apiClient.get(`/projects/${id}/insights`)
    return data
  },

  async getUsageStats(period: 'week' | 'month' | 'year' = 'month'): Promise<{
    videos_created: number
    total_duration: number
    ai_credits_used: number
    storage_used: number
    trend: Array<{
      date: string
      count: number
    }>
  }> {
    const { data } = await apiClient.get('/analytics/usage', {
      params: { period },
    })
    return data
  },

  // ============================================================================
  // FILE OPERATIONS
  // ============================================================================
  
  async downloadVideo(id: number): Promise<Blob> {
    const { data } = await apiClient.get(`/projects/${id}/download`, {
      responseType: 'blob',
    })
    return data
  },

  async getDownloadUrl(id: number): Promise<{
    download_url: string
    expires_at: string
  }> {
    const { data } = await apiClient.get(`/projects/${id}/download-url`)
    return data
  },

  async uploadCustomAudio(
    id: number,
    audioFile: File
  ): Promise<{
    audio_url: string
    duration: number
  }> {
    const formData = new FormData()
    formData.append('audio', audioFile)
    
    const { data } = await apiClient.post(
      `/projects/${id}/upload-audio`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
    return data
  },

  // ============================================================================
  // EXPORT & IMPORT
  // ============================================================================
  
  async exportProject(id: number): Promise<{
    export_url: string
    expires_at: string
  }> {
    const { data } = await apiClient.post(`/projects/${id}/export`)
    return data
  },

  async importProject(projectData: any): Promise<Project> {
    const { data } = await apiClient.post<Project>('/projects/import', projectData)
    return data
  },

  async exportAllProjects(): Promise<{
    export_url: string
    project_count: number
    expires_at: string
  }> {
    const { data } = await apiClient.post('/projects/export-all')
    return data
  },

  // ============================================================================
  // TASK STATUS & MONITORING
  // ============================================================================
  
  async getTaskStatus(taskId: string): Promise<{
    task_id: string
    status: string
    progress: number
    result?: any
    error?: string
    started_at?: string
    completed_at?: string
  }> {
    const { data } = await apiClient.get(`/tasks/${taskId}/status`)
    return data
  },

  async cancelTask(taskId: string): Promise<void> {
    await apiClient.post(`/tasks/${taskId}/cancel`)
  },

  async getActiveJobs(): Promise<Array<{
    task_id: string
    type: string
    status: string
    progress: number
    project_id?: number
    started_at: string
  }>> {
    const { data } = await apiClient.get('/tasks/active')
    return data
  },

  // ============================================================================
  // TEMPLATES & PRESETS
  // ============================================================================
  
  async getProjectTemplates(): Promise<Array<{
    id: string
    name: string
    description: string
    category: string
    settings: any
    preview_url?: string
  }>> {
    const { data } = await apiClient.get('/projects/templates')
    return data
  },

  async createFromTemplate(
    templateId: string,
    customizations: Partial<ProjectCreate>
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>('/projects/from-template', {
      template_id: templateId,
      ...customizations,
    })
    return data
  },

  async saveAsTemplate(
    projectId: number,
    templateName: string,
    description?: string
  ): Promise<{
    template_id: string
    name: string
  }> {
    const { data } = await apiClient.post(`/projects/${projectId}/save-template`, {
      name: templateName,
      description,
    })
    return data
  },
}
