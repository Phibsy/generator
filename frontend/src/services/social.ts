// frontend/src/services/social.ts
import { apiClient } from '@/lib/api-client'
import {
  SocialAccount,
  PublishRequest,
  PublishResponse,
  PlatformAnalytics,
  ConnectionStatus,
  SchedulePublishRequest,
} from '@/types/social'

export const socialService = {
  // ============================================================================
  // OAUTH & CONNECTION
  // ============================================================================
  
  async getAuthUrl(platform: string): Promise<{ auth_url: string }> {
    const { data } = await apiClient.get(`/social/connect/${platform}`)
    return data
  },

  async handleCallback(
    platform: string,
    code: string,
    state: string
  ): Promise<SocialAccount> {
    const { data } = await apiClient.post(`/social/callback/${platform}`, {
      code,
      state,
    })
    return data
  },

  async getConnectedAccounts(): Promise<SocialAccount[]> {
    const { data } = await apiClient.get('/social/accounts')
    return data
  },

  async disconnectAccount(accountId: number): Promise<void> {
    await apiClient.delete(`/social/accounts/${accountId}`)
  },

  async refreshAccount(accountId: number): Promise<{ message: string }> {
    const { data } = await apiClient.post(`/social/accounts/${accountId}/refresh`)
    return data
  },

  async getConnectionStatus(): Promise<ConnectionStatus> {
    const { data } = await apiClient.get('/social/connection-status')
    return data
  },

  // ============================================================================
  // PUBLISHING
  // ============================================================================
  
  async publishVideo(
    projectId: number,
    request: PublishRequest
  ): Promise<PublishResponse> {
    const { data } = await apiClient.post(
      `/social/publish/${projectId}`,
      request
    )
    return data
  },

  async schedulePublication(
    projectId: number,
    request: SchedulePublishRequest
  ): Promise<{
    task_id: string
    scheduled_for: string
    platforms: string[]
  }> {
    const { data } = await apiClient.post(
      `/social/schedule/${projectId}`,
      request
    )
    return data
  },

  async getPublications(projectId: number): Promise<any[]> {
    const { data } = await apiClient.get(`/social/publications/${projectId}`)
    return data
  },

  async getScheduledPosts(params?: {
    platform?: string
    start_date?: string
    end_date?: string
  }): Promise<any[]> {
    const { data } = await apiClient.get('/social/scheduled', { params })
    return data
  },

  async cancelScheduledPost(publicationId: number): Promise<void> {
    await apiClient.delete(`/social/scheduled/${publicationId}`)
  },

  // ============================================================================
  // ANALYTICS
  // ============================================================================
  
  async getProjectSocialAnalytics(projectId: number): Promise<{
    total_views: number
    total_likes: number
    total_comments: number
    total_shares: number
    platforms: Record<string, any>
  }> {
    const { data } = await apiClient.get(`/social/analytics/project/${projectId}`)
    return data
  },

  async getAccountAnalytics(
    accountId: number,
    period: '7d' | '30d' | '90d' = '30d'
  ): Promise<PlatformAnalytics> {
    const { data } = await apiClient.get(
      `/social/analytics/account/${accountId}`,
      { params: { period } }
    )
    return data
  },

  async getOverallAnalytics(period?: string): Promise<{
    total_reach: number
    total_engagement: number
    growth_rate: number
    top_performing_content: any[]
    platform_breakdown: Record<string, any>
  }> {
    const { data } = await apiClient.get('/social/analytics/overall', {
      params: { period },
    })
    return data
  },

  async getEngagementTrends(params?: {
    platform?: string
    start_date?: string
    end_date?: string
  }): Promise<{
    labels: string[]
    datasets: Array<{
      label: string
      data: number[]
    }>
  }> {
    const { data } = await apiClient.get('/social/analytics/trends', { params })
    return data
  },

  // ============================================================================
  // PLATFORM-SPECIFIC
  // ============================================================================
  
  async getYouTubeChannelInfo(accountId: number): Promise<any> {
    const { data } = await apiClient.get(`/social/youtube/channel/${accountId}`)
    return data
  },

  async getInstagramProfile(accountId: number): Promise<any> {
    const { data } = await apiClient.get(`/social/instagram/profile/${accountId}`)
    return data
  },

  async getTikTokProfile(accountId: number): Promise<any> {
    const { data } = await apiClient.get(`/social/tiktok/profile/${accountId}`)
    return data
  },

  async validatePostContent(
    platform: string,
    content: {
      title?: string
      description?: string
      hashtags?: string[]
    }
  ): Promise<{
    valid: boolean
    warnings: string[]
    suggestions: string[]
  }> {
    const { data } = await apiClient.post('/social/validate-content', {
      platform,
      ...content,
    })
    return data
  },

  // ============================================================================
  // BULK OPERATIONS
  // ============================================================================
  
  async bulkPublish(
    projectIds: number[],
    platforms: string[],
    settings?: any
  ): Promise<{
    batch_id: string
    total: number
    queued: number
  }> {
    const { data } = await apiClient.post('/social/bulk-publish', {
      project_ids: projectIds,
      platforms,
      settings,
    })
    return data
  },

  async getBulkPublishStatus(batchId: string): Promise<{
    status: string
    progress: number
    completed: number
    failed: number
    results: any[]
  }> {
    const { data } = await apiClient.get(`/social/bulk-publish/${batchId}`)
    return data
  },
}
