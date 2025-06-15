// frontend/src/components/social/SocialAccountsManager.tsx
'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { socialService } from '@/services/social'
import { SocialAccount } from '@/types/social'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import {
  Youtube,
  Instagram,
  Music2,
  Plus,
  RefreshCw,
  Trash2,
  CheckCircle2,
  XCircle,
  Users,
  ExternalLink,
} from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

const platformIcons = {
  youtube: Youtube,
  instagram: Instagram,
  tiktok: Music2,
}

const platformColors = {
  youtube: 'bg-red-500',
  instagram: 'bg-gradient-to-br from-purple-500 to-pink-500',
  tiktok: 'bg-black',
}

export function SocialAccountsManager() {
  const { toast } = useToast()
  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isConnecting, setIsConnecting] = useState<string | null>(null)
  const [accountToDelete, setAccountToDelete] = useState<number | null>(null)

  useEffect(() => {
    loadAccounts()
  }, [])

  const loadAccounts = async () => {
    try {
      const data = await socialService.getConnectedAccounts()
      setAccounts(data)
    } catch (error) {
      toast({
        title: 'Failed to load accounts',
        description: 'Please try again',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const connectAccount = async (platform: string) => {
    setIsConnecting(platform)
    
    try {
      const { auth_url } = await socialService.getAuthUrl(platform)
      
      // Open OAuth window
      const authWindow = window.open(
        auth_url,
        `${platform}_auth`,
        'width=600,height=700'
      )
      
      // Listen for OAuth callback
      const checkInterval = setInterval(() => {
        try {
          if (authWindow?.closed) {
            clearInterval(checkInterval)
            setIsConnecting(null)
            loadAccounts() // Refresh accounts
          }
        } catch (error) {
          // Window closed
        }
      }, 1000)
      
    } catch (error) {
      toast({
        title: 'Connection failed',
        description: 'Could not connect to ' + platform,
        variant: 'destructive',
      })
      setIsConnecting(null)
    }
  }

  const refreshAccount = async (accountId: number) => {
    try {
      await socialService.refreshAccount(accountId)
      toast({
        title: 'Account refreshed',
        description: 'Account data has been updated',
      })
      loadAccounts()
    } catch (error) {
      toast({
        title: 'Refresh failed',
        description: 'Could not refresh account data',
        variant: 'destructive',
      })
    }
  }

  const disconnectAccount = async () => {
    if (!accountToDelete) return
    
    try {
      await socialService.disconnectAccount(accountToDelete)
      toast({
        title: 'Account disconnected',
        description: 'The account has been removed',
      })
      loadAccounts()
    } catch (error) {
      toast({
        title: 'Disconnect failed',
        description: 'Could not disconnect account',
        variant: 'destructive',
      })
    } finally {
      setAccountToDelete(null)
    }
  }

  const availablePlatforms = ['youtube', 'instagram', 'tiktok'].filter(
    platform => !accounts.some(acc => acc.platform === platform)
  )

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Connected Accounts</h2>
        <p className="mt-1 text-muted-foreground">
          Manage your social media connections for publishing videos
        </p>
      </div>

      {/* Connected Accounts */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {accounts.map((account) => {
          const Icon = platformIcons[account.platform as keyof typeof platformIcons]
          
          return (
            <motion.div
              key={account.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3 }}
            >
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className={`rounded-lg p-2 ${platformColors[account.platform as keyof typeof platformColors]}`}>
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-base">
                          {account.username}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground capitalize">
                          {account.platform}
                        </p>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      <CheckCircle2 className="mr-1 h-3 w-3 text-green-500" />
                      Connected
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Followers</span>
                      <span className="font-medium flex items-center">
                        <Users className="mr-1 h-3 w-3" />
                        {account.followers_count.toLocaleString()}
                      </span>
                    </div>
                    
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => refreshAccount(account.id)}
                      >
                        <RefreshCw className="mr-1 h-3 w-3" />
                        Refresh
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => setAccountToDelete(account.id)}
                      >
                        <Trash2 className="mr-1 h-3 w-3" />
                        Disconnect
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )
        })}

        {/* Add Account Cards */}
        {availablePlatforms.map((platform) => {
          const Icon = platformIcons[platform as keyof typeof platformIcons]
          
          return (
            <motion.div
              key={platform}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="border-dashed">
                <CardContent className="flex h-full flex-col items-center justify-center p-6">
                  <div className={`mb-4 rounded-lg p-3 ${platformColors[platform as keyof typeof platformColors]}`}>
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="mb-2 font-semibold capitalize">{platform}</h3>
                  <p className="mb-4 text-center text-sm text-muted-foreground">
                    Connect your {platform} account to start publishing
                  </p>
                  <Button
                    onClick={() => connectAccount(platform)}
                    disabled={isConnecting === platform}
                  >
                    {isConnecting === platform ? (
                      <>
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      <>
                        <Plus className="mr-2 h-4 w-4" />
                        Connect
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )
        })}
      </div>

      {/* Disconnect Dialog */}
      <AlertDialog open={!!accountToDelete} onOpenChange={() => setAccountToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect Account?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the connection to your social media account.
              You can reconnect it anytime.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={disconnectAccount}>
              Disconnect
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// frontend/src/components/social/PublishDialog.tsx
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { format } from 'date-fns'
import { CalendarIcon, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { socialService } from '@/services/social'
import { Project } from '@/types'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/components/ui/use-toast'
import { Badge } from '@/components/ui/badge'
import { PlatformSettings } from './PlatformSettings'

const publishSchema = z.object({
  platforms: z.array(z.string()).min(1, 'Select at least one platform'),
  title: z.string().optional(),
  description: z.string().optional(),
  hashtags: z.array(z.string()).optional(),
  publishNow: z.boolean(),
  scheduledFor: z.date().optional(),
  platformSettings: z.record(z.any()).optional(),
})

type PublishForm = z.infer<typeof publishSchema>

interface PublishDialogProps {
  project: Project
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function PublishDialog({
  project,
  open,
  onOpenChange,
  onSuccess,
}: PublishDialogProps) {
  const { toast } = useToast()
  const [isPublishing, setIsPublishing] = useState(false)
  const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>([])

  const form = useForm<PublishForm>({
    resolver: zodResolver(publishSchema),
    defaultValues: {
      platforms: [],
      title: project.title,
      description: project.description || '',
      hashtags: project.hashtags || [],
      publishNow: true,
      platformSettings: {},
    },
  })

  // Load connected accounts
  useEffect(() => {
    socialService.getConnectedAccounts().then((accounts) => {
      setConnectedPlatforms(accounts.map(acc => acc.platform))
    })
  }, [])

  const onSubmit = async (data: PublishForm) => {
    setIsPublishing(true)

    try {
      if (data.publishNow) {
        // Publish immediately
        const result = await socialService.publishVideo(project.id, {
          platforms: data.platforms,
          title: data.title,
          description: data.description,
          hashtags: data.hashtags,
          platform_settings: data.platformSettings,
        })

        const successful = result.successful.length
        const failed = result.failed.length

        toast({
          title: 'Publishing complete',
          description: `Successfully published to ${successful} platform${successful !== 1 ? 's' : ''}${
            failed > 0 ? `, ${failed} failed` : ''
          }`,
        })
      } else {
        // Schedule publication
        await socialService.schedulePublication(project.id, {
          platforms: data.platforms,
          title: data.title,
          description: data.description,
          hashtags: data.hashtags,
          scheduled_for: data.scheduledFor!,
          platform_settings: data.platformSettings,
        })

        toast({
          title: 'Publication scheduled',
          description: `Your video will be published on ${format(
            data.scheduledFor!,
            'PPP'
          )} at ${format(data.scheduledFor!, 'p')}`,
        })
      }

      onOpenChange(false)
      onSuccess?.()
    } catch (error) {
      toast({
        title: 'Publishing failed',
        description: 'Please try again',
        variant: 'destructive',
      })
    } finally {
      setIsPublishing(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Publish Video</DialogTitle>
          <DialogDescription>
            Share your video on social media platforms
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Platform Selection */}
            <FormField
              control={form.control}
              name="platforms"
              render={() => (
                <FormItem>
                  <FormLabel>Platforms</FormLabel>
                  <div className="grid grid-cols-3 gap-4">
                    {['youtube', 'instagram', 'tiktok'].map((platform) => (
                      <FormField
                        key={platform}
                        control={form.control}
                        name="platforms"
                        render={({ field }) => {
                          const isConnected = connectedPlatforms.includes(platform)
                          const isSelected = field.value?.includes(platform)

                          return (
                            <FormItem>
                              <FormControl>
                                <div
                                  className={cn(
                                    'relative rounded-lg border p-4 cursor-pointer transition-colors',
                                    isSelected && 'border-primary bg-primary/5',
                                    !isConnected && 'opacity-50 cursor-not-allowed'
                                  )}
                                  onClick={() => {
                                    if (!isConnected) return
                                    
                                    const updated = isSelected
                                      ? field.value?.filter(v => v !== platform)
                                      : [...(field.value || []), platform]
                                    field.onChange(updated)
                                  }}
                                >
                                  <Checkbox
                                    checked={isSelected}
                                    disabled={!isConnected}
                                    className="absolute right-2 top-2"
                                  />
                                  <div className="text-center">
                                    <div className="mb-2 text-2xl">
                                      {platform === 'youtube' && '📺'}
                                      {platform === 'instagram' && '📸'}
                                      {platform === 'tiktok' && '🎵'}
                                    </div>
                                    <p className="font-medium capitalize">
                                      {platform}
                                    </p>
                                    {!isConnected && (
                                      <p className="text-xs text-muted-foreground">
                                        Not connected
                                      </p>
                                    )}
                                  </div>
                                </div>
                              </FormControl>
                            </FormItem>
                          )
                        }}
                      />
                    ))}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Content Settings */}
            <Tabs defaultValue="content" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="content">Content</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
                <TabsTrigger value="schedule">Schedule</TabsTrigger>
              </TabsList>

              <TabsContent value="content" className="space-y-4">
                <FormField
                  control={form.control}
                  name="title"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Title</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormDescription>
                        Video title (platform limits apply)
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description</FormLabel>
                      <FormControl>
                        <Textarea {...field} rows={4} />
                      </FormControl>
                      <FormDescription>
                        Video description or caption
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="hashtags"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Hashtags</FormLabel>
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2">
                          {field.value?.map((tag, index) => (
                            <Badge
                              key={index}
                              variant="secondary"
                              className="cursor-pointer"
                              onClick={() => {
                                const updated = field.value?.filter((_, i) => i !== index)
                                field.onChange(updated)
                              }}
                            >
                              #{tag} ×
                            </Badge>
                          ))}
                        </div>
                        <Input
                          placeholder="Add hashtag and press Enter"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              const input = e.currentTarget
                              const tag = input.value.trim().replace('#', '')
                              if (tag && !field.value?.includes(tag)) {
                                field.onChange([...(field.value || []), tag])
                                input.value = ''
                              }
                            }
                          }}
                        />
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>

              <TabsContent value="settings" className="space-y-4">
                <PlatformSettings
                  platforms={form.watch('platforms')}
                  settings={form.watch('platformSettings') || {}}
                  onChange={(settings) => form.setValue('platformSettings', settings)}
                />
              </TabsContent>

              <TabsContent value="schedule" className="space-y-4">
                <FormField
                  control={form.control}
                  name="publishNow"
                  render={({ field }) => (
                    <FormItem className="flex items-center space-x-2">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FormLabel className="!mt-0">
                        Publish immediately
                      </FormLabel>
                    </FormItem>
                  )}
                />

                {!form.watch('publishNow') && (
                  <FormField
                    control={form.control}
                    name="scheduledFor"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Schedule for</FormLabel>
                        <Popover>
                          <PopoverTrigger asChild>
                            <FormControl>
                              <Button
                                variant="outline"
                                className={cn(
                                  'w-full justify-start text-left font-normal',
                                  !field.value && 'text-muted-foreground'
                                )}
                              >
                                <CalendarIcon className="mr-2 h-4 w-4" />
                                {field.value ? (
                                  format(field.value, 'PPP p')
                                ) : (
                                  <span>Pick a date and time</span>
                                )}
                              </Button>
                            </FormControl>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                              mode="single"
                              selected={field.value}
                              onSelect={field.onChange}
                              disabled={(date) =>
                                date < new Date()
                              }
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isPublishing}>
                {isPublishing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {form.watch('publishNow') ? 'Publish Now' : 'Schedule'}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
