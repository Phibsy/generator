// frontend/src/types/social.ts
export interface SocialAccount {
  id: number
  platform: 'youtube' | 'instagram' | 'tiktok'
  platform_user_id: string
  username: string
  is_active: boolean
  followers_count: number
  created_at: string
  updated_at?: string
}

export interface PublishRequest {
  platforms: string[]
  title?: string
  description?: string
  hashtags?: string[]
  platform_settings?: Record<string, any>
}

export interface SchedulePublishRequest extends PublishRequest {
  scheduled_for: Date
}

export interface PublishResponse {
  successful: Array<{
    platform: string
    url: string
    post_id: string
  }>
  failed: Array<{
    platform: string
    error: string
  }>
  scheduled: Array<{
    platform: string
    scheduled_for: string
  }>
}

export interface Publication {
  id: number
  project_id: number
  social_account_id: number
  platform: string
  platform_post_id?: string
  url?: string
  title?: string
  description?: string
  is_published: boolean
  published_at?: string
  scheduled_for?: string
  views: number
  likes: number
  comments: number
  shares: number
  engagement_rate: number
  created_at: string
  updated_at?: string
}

export interface PlatformAnalytics {
  platform: string
  account_id: number
  period: string
  metrics: Record<string, any>
}

export interface ConnectionStatus {
  platforms: Array<{
    platform: string
    connected: boolean
    account?: SocialAccount
    features: string[]
    limits: Record<string, any>
  }>
  total_connected: number
  available_platforms: string[]
}
