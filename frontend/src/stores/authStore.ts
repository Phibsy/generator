// frontend/src/stores/authStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthState, User, LoginCredentials, RegisterData } from '@/types';
import { apiClient } from '@/services/api';

interface AuthStore extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (credentials: LoginCredentials) => {
        set({ isLoading: true });
        try {
          const response = await apiClient.login(credentials);
          const { access_token, user } = response;
          
          set({
            user,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
          });

          // Set token in API client
          apiClient.setAuthStore(useAuthStore);
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      register: async (data: RegisterData) => {
        set({ isLoading: true });
        try {
          const user = await apiClient.register(data);
          set({ isLoading: false });
          
          // Auto-login after registration
          await get().login({
            username: data.username,
            password: data.password,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });
      },

      fetchUser: async () => {
        if (!get().token) return;
        
        set({ isLoading: true });
        try {
          const user = await apiClient.getMe();
          set({ user, isLoading: false });
        } catch (error) {
          set({ isLoading: false });
          get().logout();
        }
      },

      setUser: (user) => set({ user }),
      setToken: (token) => set({ token, isAuthenticated: !!token }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Initialize API client with auth store
apiClient.setAuthStore(useAuthStore);
