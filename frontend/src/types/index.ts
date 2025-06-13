// frontend/src/types/index.ts

// ============================================================================
// USER & AUTH TYPES
// ============================================================================

export interface User {
  id: number
  email: string
  username: string
  first_name?: string
  last_name?: string
  avatar_url?: string
  bio?: string
  is_active: boolean
  is_verified: boolean
  role: 'admin' | 'user' | 'premium'
  subscription_plan: string
  videos_generated: number
  monthly_limit: number
  last_login?: string
  created_at: string
  updated_at?: string
  full_name: string
  can_generate_video: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface RegisterData {
  email: string
  username: string
  password: string
  first_name?: string
  last_name?: string
}

// ============================================================================
// PROJECT TYPES
// ============================================================================

export enum ProjectStatus {
  DRAFT = 'draft',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  PUBLISHED = 'published',
}

export interface Project {
  id: number
  user_id: number
  title: string
  description?: string
  status: ProjectStatus
  topic?: string
  target_audience?: string
  video_style?: string
  duration: number
  script?: string
  hashtags?: string[]
  audio_file_path?: string
  video_file_path?: string
  thumbnail_path?: string
  processing_started_at?: string
  processing_completed_at?: string
  processing_duration?: number
  error_message?: string
  voice_id?: string
  background_music?: string
  subtitle_style?: any
  is_processing: boolean
  is_completed: boolean
  created_at: string
  updated_at?: string
}

export interface ProjectCreate {
  title: string
  description?: string
  topic?: string
  target_audience?: string
  video_style?: string
  duration?: number
  voice_id?: string
  background_music?: string
  subtitle_style?: any
}

export interface ProjectUpdate {
  title?: string
  description?: string
  topic?: string
  target_audience?: string
  video_style?: string
  duration?: number
  voice_id?: string
  background_music?: string
  subtitle_style?: any
}

// ============================================================================
// CONTENT GENERATION TYPES
// ============================================================================

export interface ContentGenerationRequest {
  topic: string
  target_audience: string
  video_style?: string
  duration?: number
  tone?: string
  include_call_to_action?: boolean
}

export interface ContentGenerationResponse {
  script: string
  hashtags: string[]
  suggested_title: string
  estimated_duration: number
  content_score: number
}

// ============================================================================
// TEXT-TO-SPEECH TYPES
// ============================================================================

export interface TTSRequest {
  text: string
  voice_id?: string
  speed?: number
}

export interface TTSResponse {
  audio_url: string
  duration: number
  provider: string
  voice_id: string
  file_key: string
}

export interface VoiceInfo {
  voice_id: string
  name: string
  description: string
  provider: 'elevenlabs' | 'aws_polly' | 'both'
  preview_url: string
}

// ============================================================================
// VIDEO PROCESSING TYPES
// ============================================================================

export interface VideoSettings {
  voice_id: string
  background_video: string
  subtitle_style: string
  subtitle_animation: string
  music_preset?: string
  music_volume: number
  effects_enabled: boolean
  effects_preset: string
  quality: string
  platform?: string
}

export interface VideoBackground {
  id: string
  name: string
  description: string
  category: string
  preview_url: string
}

export interface SubtitleStyle {
  name: string
  description: string
  preview: string
  settings: any
}

export interface MusicPreset {
  id: string
  name: string
  description: string
  bpm: number
  mood: string
  genres: string[]
  preview_url: string
}

export interface EffectsPreset {
  id: string
  name: string
  description: string
  effects: string[]
  intensity: string
  best_for: string[]
}

export interface QualityPreset {
  name: string
  description: string
  resolution: string
  fps: number
  bitrate: string
  estimated_size_per_minute: string
  processing_speed: string
  warning?: string
}

// ============================================================================
// PROGRESS & TASK TYPES
// ============================================================================

export interface ProgressUpdate {
  task_id: string
  progress: number
  status: string
  details?: any
  timestamp?: string
}

export interface TaskStatus {
  task_id: string
  state: string
  progress: number
  status: string
  result?: any
  error?: string
  started_at?: string
  completed_at?: string
  execution_time?: string
}

// ============================================================================
// BATCH PROCESSING TYPES
// ============================================================================

export interface BatchJob {
  batch_id: string
  status: string
  total_projects: number
  valid_projects: number
  priority: string
  estimated_completion_time: string
  created_at: string
}

export interface BatchProgress {
  batch_id: string
  total: number
  completed: number
  failed: number
  pending: number
  progress_percentage: number
}

// ============================================================================
// ANALYTICS TYPES
// ============================================================================

export interface VideoAnalytics {
  id: number
  project_id: number
  generation_time?: number
  content_score?: number
  total_views: number
  total_likes: number
  total_comments: number
  total_shares: number
  avg_engagement_rate: number
  best_performing_platform?: string
  script_length?: number
  hashtag_count?: number
  sentiment_score?: number
  created_at: string
  updated_at?: string
}

export interface DashboardStats {
  total_projects: number
  completed_projects: number
  processing_projects: number
  total_views: number
  total_likes: number
  avg_engagement_rate: number
  videos_this_month: number
  remaining_videos: number
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
  has_next: boolean
  has_prev: boolean
}

export interface ErrorResponse {
  error: boolean
  message: string
  status_code: number
  timestamp: number
  details?: any
}

export interface ValidationError {
  field: string
  message: string
  invalid_value: any
}
