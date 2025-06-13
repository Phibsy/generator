// frontend/src/lib/api-client.ts
import axios, { AxiosError } from 'axios'
import { toast } from '@/components/ui/use-toast'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const { response } = error
    
    if (response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('access_token')
      window.location.href = '/auth/login'
    } else if (response?.status === 403) {
      toast({
        title: 'Access Denied',
        description: 'You do not have permission to perform this action.',
        variant: 'destructive',
      })
    } else if (response?.status === 500) {
      toast({
        title: 'Server Error',
        description: 'Something went wrong. Please try again later.',
        variant: 'destructive',
      })
    }
    
    return Promise.reject(error)
  }
)

// frontend/src/services/auth.ts
import { apiClient } from '@/lib/api-client'
import { User, LoginResponse, RegisterData } from '@/types'

export const authService = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', {
      username,
      password,
    })
    return data
  },

  async register(registerData: RegisterData): Promise<User> {
    const { data } = await apiClient.post<User>('/auth/register', registerData)
    return data
  },

  async getCurrentUser(): Promise<User> {
    const { data } = await apiClient.get<User>('/auth/me')
    return data
  },

  async updateProfile(updates: Partial<User>): Promise<User> {
    const { data } = await apiClient.put<User>('/auth/me', updates)
    return data
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout')
  },
}

// frontend/src/services/projects.ts
import { apiClient } from '@/lib/api-client'
import {
  Project,
  ProjectCreate,
  ProjectUpdate,
  PaginatedResponse,
  ContentGenerationResponse,
} from '@/types'

export const projectService = {
  async getProjects(params?: {
    page?: number
    limit?: number
    status?: string
    search?: string
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

  async generateContent(id: number): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/projects/${id}/generate-content`
    )
    return data
  },

  async optimizeContent(id: number, platform: string): Promise<any> {
    const { data } = await apiClient.post(
      `/projects/${id}/optimize-content`,
      null,
      { params: { platform } }
    )
    return data
  },

  async analyzeContent(id: number): Promise<any> {
    const { data } = await apiClient.get(`/projects/${id}/content-analysis`)
    return data
  },
}

// frontend/src/services/content.ts
import { apiClient } from '@/lib/api-client'
import { ContentGenerationRequest, ContentGenerationResponse } from '@/types'

export const contentService = {
  async generateContent(
    request: ContentGenerationRequest
  ): Promise<ContentGenerationResponse> {
    const { data } = await apiClient.post<ContentGenerationResponse>(
      '/content/generate',
      request
    )
    return data
  },

  async generateHashtags(
    topic: string,
    targetAudience: string,
    platform: string = 'instagram'
  ): Promise<string[]> {
    const { data } = await apiClient.post<string[]>('/content/generate-hashtags', {
      topic,
      target_audience: targetAudience,
      platform,
    })
    return data
  },

  async analyzeContent(script: string, topic: string): Promise<any> {
    const { data } = await apiClient.post('/content/analyze-content', {
      script,
      topic,
    })
    return data
  },

  async generateVariations(script: string, numVariations: number = 3): Promise<string[]> {
    const { data } = await apiClient.post<string[]>('/content/generate-variations', {
      script,
      num_variations: numVariations,
    })
    return data
  },

  async getTrendingTopics(category: string = 'general'): Promise<any[]> {
    const { data } = await apiClient.get('/content/trending-topics', {
      params: { category },
    })
    return data
  },

  async getTemplates(style: string): Promise<any> {
    const { data } = await apiClient.get(`/content/templates/${style}`)
    return data
  },
}

// frontend/src/services/video.ts
import { apiClient } from '@/lib/api-client'
import { Project, VideoSettings } from '@/types'

export const videoService = {
  async generateVideo(
    projectId: number,
    settings: Partial<VideoSettings>
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/video/generate/${projectId}`,
      null,
      { params: settings }
    )
    return data
  },

  async generateAdvancedVideo(
    projectId: number,
    settings: VideoSettings
  ): Promise<any> {
    const { data } = await apiClient.post(
      `/video/generate-advanced/${projectId}`,
      null,
      { params: settings }
    )
    return data
  },

  async getBackgrounds(): Promise<any[]> {
    const { data } = await apiClient.get('/video/backgrounds')
    return data
  },

  async getSubtitleStyles(): Promise<any> {
    const { data } = await apiClient.get('/video/subtitle-styles')
    return data
  },

  async getMusicLibrary(): Promise<any[]> {
    const { data } = await apiClient.get('/video/music-library')
    return data
  },

  async getEffectsPresets(): Promise<any[]> {
    const { data } = await apiClient.get('/video/effects-presets')
    return data
  },

  async getQualityPresets(): Promise<any> {
    const { data } = await apiClient.get('/video/quality-presets')
    return data
  },

  async getTaskStatus(taskId: string): Promise<any> {
    const { data } = await apiClient.get(`/video/task-status/${taskId}`)
    return data
  },
}

// frontend/src/services/tts.ts
import { apiClient } from '@/lib/api-client'
import { TTSRequest, TTSResponse, VoiceInfo } from '@/types'

export const ttsService = {
  async generateTTS(request: TTSRequest): Promise<TTSResponse> {
    const { data } = await apiClient.post<TTSResponse>('/tts/generate', request)
    return data
  },

  async generateProjectTTS(
    projectId: number,
    voiceId?: string,
    speed?: number
  ): Promise<Project> {
    const { data } = await apiClient.post<Project>(
      `/tts/generate-for-project/${projectId}`,
      null,
      { params: { voice_id: voiceId, speed } }
    )
    return data
  },

  async getVoices(): Promise<VoiceInfo[]> {
    const { data } = await apiClient.get<VoiceInfo[]>('/tts/voices')
    return data
  },

  async previewVoice(voiceId: string, text?: string): Promise<any> {
    const { data } = await apiClient.get(`/tts/voice/${voiceId}/preview`, {
      params: { text },
    })
    return data
  },

  async recommendVoice(
    topic: string,
    targetAudience: string,
    style: string = 'general'
  ): Promise<any> {
    const { data } = await apiClient.post('/tts/voice/recommend', {
      topic,
      target_audience: targetAudience,
      style,
    })
    return data
  },

  async getUsage(): Promise<any> {
    const { data } = await apiClient.get('/tts/usage')
    return data
  },
}
