// frontend/src/pages/index.tsx
import React from 'react';
import { Layout } from '@/components/Layout/Layout';
import { useAuthStore } from '@/stores/authStore';
import { 
  Video, 
  Clock, 
  TrendingUp, 
  Zap,
  ArrowRight
} from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
  const { user } = useAuthStore();

  const stats = [
    { 
      name: 'Videos Created', 
      value: user?.videosGenerated || 0, 
      change: '+12%',
      icon: Video 
    },
    { 
      name: 'Processing Time', 
      value: '2.5 min', 
      change: '-18%',
      icon: Clock 
    },
    { 
      name: 'Engagement Rate', 
      value: '4.8%', 
      change: '+7%',
      icon: TrendingUp 
    },
    { 
      name: 'Videos Left', 
      value: `${(user?.monthlyLimit || 10) - (user?.videosGenerated || 0)}`, 
      change: 'This month',
      icon: Zap 
    },
  ];

  const recentProjects = [
    {
      id: 1,
      title: '5 Mind-Blowing Psychology Facts',
      status: 'completed',
      views: '12.5K',
      engagement: '6.2%',
      createdAt: '2 hours ago',
    },
    {
      id: 2,
      title: 'How to Learn Any Skill Fast',
      status: 'processing',
      views: '-',
      engagement: '-',
      createdAt: '30 minutes ago',
    },
    {
      id: 3,
      title: 'The Science of Productivity',
      status: 'completed',
      views: '8.3K',
      engagement: '5.1%',
      createdAt: 'Yesterday',
    },
  ];

  return (
    <Layout>
      <div className="space-y-8">
        {/* Welcome Section */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.firstName || user?.username}!
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Here's what's happening with your videos today.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <div
              key={stat.name}
              className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6"
            >
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <stat.icon className="h-8 w-8 text-gray-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="truncate text-sm font-medium text-gray-500">
                      {stat.name}
                    </dt>
                    <dd className="flex items-baseline">
                      <div className="text-2xl font-semibold text-gray-900">
                        {stat.value}
                      </div>
                      <div className="ml-2 flex items-baseline text-sm font-semibold text-green-600">
                        {stat.change}
                      </div>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Recent Projects */}
        <div className="bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
            <h2 className="text-lg font-medium text-gray-900">Recent Projects</h2>
            <Link
              href="/projects"
              className="text-sm font-medium text-primary-600 hover:text-primary-500 flex items-center"
            >
              View all
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </div>
          <div className="border-t border-gray-200">
            <ul role="list" className="divide-y divide-gray-200">
              {recentProjects.map((project) => (
                <li key={project.id} className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        {project.title}
                      </p>
                      <div className="mt-1 flex items-center text-sm text-gray-500">
                        <span>{project.createdAt}</span>
                        {project.status === 'completed' && (
                          <>
                            <span className="mx-2">•</span>
                            <span>{project.views} views</span>
                            <span className="mx-2">•</span>
                            <span>{project.engagement} engagement</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="ml-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          project.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {project.status}
                      </span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-primary-50 rounded-lg p-6">
          <h3 className="text-lg font-medium text-primary-900">
            Ready to create your next viral video?
          </h3>
          <p className="mt-1 text-sm text-primary-700">
            Use AI to generate engaging content in minutes
          </p>
          <div className="mt-4">
            <Link
              href="/projects/new"
              className="inline-flex items-center rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
            >
              Create New Video
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </Layout>
  );
}
