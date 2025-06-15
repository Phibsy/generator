// frontend/src/app/dashboard/social/page.tsx
'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SocialAccountsManager } from '@/components/social/SocialAccountsManager'
import { PublishedContent } from '@/components/social/PublishedContent'
import { SocialAnalytics } from '@/components/social/SocialAnalytics'
import { ScheduledPosts } from '@/components/social/ScheduledPosts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Share2, Calendar, BarChart3, Settings } from 'lucide-react'

export default function SocialMediaPage() {
  const [activeTab, setActiveTab] = useState('accounts')

  return (
    <div className="space-y-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Social Media</h1>
            <p className="mt-2 text-muted-foreground">
              Manage your social media presence and track performance
            </p>
          </div>
          
          <Button>
            <Share2 className="mr-2 h-4 w-4" />
            Quick Share
          </Button>
        </div>
      </motion.div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 max-w-2xl">
          <TabsTrigger value="accounts" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Accounts
          </TabsTrigger>
          <TabsTrigger value="published" className="flex items-center gap-2">
            <Share2 className="h-4 w-4" />
            Published
          </TabsTrigger>
          <TabsTrigger value="scheduled" className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Scheduled
          </TabsTrigger>
          <TabsTrigger value="analytics" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Analytics
          </TabsTrigger>
        </TabsList>

        <TabsContent value="accounts" className="space-y-6">
          <SocialAccountsManager />
        </TabsContent>

        <TabsContent value="published" className="space-y-6">
          <PublishedContent />
        </TabsContent>

        <TabsContent value="scheduled" className="space-y-6">
          <ScheduledPosts />
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <SocialAnalytics />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// frontend/src/app/dashboard/social/callback/[platform]/page.tsx
'use client'

import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { socialService } from '@/services/social'
import { useToast } from '@/components/ui/use-toast'
import { Loader2 } from 'lucide-react'

export default function SocialCallbackPage({
  params,
}: {
  params: { platform: string }
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  
  useEffect(() => {
    handleCallback()
  }, [])
  
  const handleCallback = async () => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const error = searchParams.get('error')
    
    if (error) {
      toast({
        title: 'Connection failed',
        description: error,
        variant: 'destructive',
      })
      
      // Close window if opened as popup
      if (window.opener) {
        window.close()
      } else {
        router.push('/dashboard/social')
      }
      return
    }
    
    if (!code || !state) {
      toast({
        title: 'Invalid callback',
        description: 'Missing required parameters',
        variant: 'destructive',
      })
      
      if (window.opener) {
        window.close()
      } else {
        router.push('/dashboard/social')
      }
      return
    }
    
    try {
      await socialService.handleCallback(params.platform, code, state)
      
      toast({
        title: 'Account connected!',
        description: `Your ${params.platform} account has been connected successfully`,
      })
      
      // Close popup or redirect
      if (window.opener) {
        window.close()
      } else {
        router.push('/dashboard/social')
      }
      
    } catch (error) {
      toast({
        title: 'Connection failed',
        description: 'Could not complete the connection',
        variant: 'destructive',
      })
      
      if (window.opener) {
        window.close()
      } else {
        router.push('/dashboard/social')
      }
    }
  }
  
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
        <p className="mt-4 text-lg">Connecting your account...</p>
      </div>
    </div>
  )
}
