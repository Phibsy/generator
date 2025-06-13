// frontend/src/services/api.ts
import axios, { AxiosInstance, AxiosError } from 'axios';
import { AuthState } from '@/types';

class ApiClient {
  private client: AxiosInstance;
  private authStore: any; // Will be set from store

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  setAuthStore(store: any) {
    this.authStore = store;
  }

  private setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        const token = this.authStore?.getState().token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Token expired or invalid
          this.authStore?.getState().logout();
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async login(credentials: LoginCredentials) {
    const response = await this.client.post('/api/v1/auth/login', credentials);
    return response.data;
  }

  async register(data: RegisterData) {
    const response = await this.client.post('/api/v1/auth/register', data);
    return response.data;
  }

  async getMe() {
    const response = await this.client.get('/api/v1/auth/me');
    return response.data;
  }

  // Projects endpoints
  async getProjects(params?: { page?: number; limit?: number; status?: string }) {
    const response = await this.client.get('/api/v1/projects', { params });
    return response.data;
  }

  async getProject(id: number) {
    const response = await this.client.get(`/api/v1/projects/${id}`);
    return response.data;
  }

  async createProject(data: any) {
    const response = await this.client.post('/api/v1/projects', data);
    return response.data;
  }

  async updateProject(id: number, data: any) {
    const response = await this.client.put(`/api/v1/projects/${id}`, data);
    return response.data;
  }

  async deleteProject(id: number) {
    const response = await this.client.delete(`/api/v1/projects/${id}`);
    return response.data;
  }

  // Content generation
  async generateContent(data: ContentGenerationRequest) {
    const response = await this.client.post('/api/v1/content/generate', data);
    return response.data;
  }

  async generateContentForProject(projectId: number) {
    const response = await this.client.post(`/api/v1/projects/${projectId}/generate-content`);
    return response.data;
  }

  // TTS endpoints
  async generateTTS(projectId: number, voiceId?: string) {
    const response = await this.client.post(`/api/v1/tts/generate-for-project/${projectId}`, {
      voice_id: voiceId,
    });
    return response.data;
  }

  async getVoices() {
    const response = await this.client.get('/api/v1/tts/voices');
    return response.data;
  }

  // Video generation
  async generateVideo(projectId: number, settings?: any) {
    const response = await this.client.post(`/api/v1/video/generate/${projectId}`, settings);
    return response.data;
  }

  async getVideoTemplates() {
    const response = await this.client.get('/api/v1/video/templates');
    return response.data;
  }

  // Analytics
  async getDashboardStats() {
    const response = await this.client.get('/api/v1/analytics/dashboard');
    return response.data;
  }
}

export const apiClient = new ApiClient();
