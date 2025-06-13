// frontend/src/components/providers/Providers.tsx
'use client'

import { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ThemeProvider } from './ThemeProvider'
import { AuthProvider } from './AuthProvider'
import { WebSocketProvider } from './WebSocketProvider'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

interface ProvidersProps {
  children: ReactNode
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem
        disableTransitionOnChange
      >
        <AuthProvider>
          <WebSocketProvider>
            {children}
          </WebSocketProvider>
        </AuthProvider>
      </ThemeProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}

// frontend/src/components/providers/AuthProvider.tsx
'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { User } from '@/types'
import { authService } from '@/services/auth'
import { useAuthStore } from '@/stores/authStore'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  register: (data: RegisterData) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, setUser, clearUser } = useAuthStore()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (token) {
        const userData = await authService.getCurrentUser()
        setUser(userData)
      }
    } catch (error) {
      clearUser()
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string, password: string) => {
    const response = await authService.login(email, password)
    setUser(response.user)
    localStorage.setItem('access_token', response.access_token)
    router.push('/dashboard')
  }

  const logout = async () => {
    await authService.logout()
    clearUser()
    localStorage.removeItem('access_token')
    router.push('/auth/login')
  }

  const register = async (data: RegisterData) => {
    const user = await authService.register(data)
    setUser(user)
    router.push('/auth/login')
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// frontend/src/components/providers/WebSocketProvider.tsx
'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthProvider'
import { VideoProcessingWebSocket } from '@/services/websocket'
import { ProgressUpdate } from '@/types'

interface WebSocketContextType {
  progress: Record<string, ProgressUpdate>
  isConnected: boolean
  requestStatus: (taskId: string) => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const [progress, setProgress] = useState<Record<string, ProgressUpdate>>({})
  const [isConnected, setIsConnected] = useState(false)
  const [wsClient, setWsClient] = useState<VideoProcessingWebSocket | null>(null)

  useEffect(() => {
    if (user) {
      const client = new VideoProcessingWebSocket(
        user.id.toString(),
        (update) => {
          setProgress(prev => ({
            ...prev,
            [update.task_id]: update
          }))
        },
        (error) => {
          console.error('WebSocket error:', error)
          setIsConnected(false)
        }
      )

      client.connect()
      setWsClient(client)
      setIsConnected(true)

      return () => {
        client.disconnect()
        setIsConnected(false)
      }
    }
  }, [user])

  const requestStatus = (taskId: string) => {
    wsClient?.requestStatus(taskId)
  }

  return (
    <WebSocketContext.Provider value={{ progress, isConnected, requestStatus }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useWebSocket = () => {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

// frontend/src/components/providers/ThemeProvider.tsx
'use client'

import * as React from 'react'
import { ThemeProvider as NextThemesProvider } from 'next-themes'
import { type ThemeProviderProps } from 'next-themes/dist/types'

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}
