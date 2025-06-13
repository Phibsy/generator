// frontend/src/app/layout.tsx
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/providers/Providers'
import { Toaster } from '@/components/ui/toaster'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Reels Generator - AI-Powered Video Creation',
  description: 'Create viral YouTube Shorts and Instagram Reels with AI',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}

// frontend/src/app/page.tsx
import { redirect } from 'next/navigation'
import { getServerSession } from '@/lib/auth'

export default async function HomePage() {
  const session = await getServerSession()
  
  if (session) {
    redirect('/dashboard')
  } else {
    redirect('/auth/login')
  }
}
