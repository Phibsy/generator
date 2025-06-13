// frontend/src/components/Layout/Layout.tsx
import React from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuthStore } from '@/stores/authStore';
import { 
  Home, 
  Video, 
  Settings, 
  LogOut, 
  Menu, 
  X,
  Plus,
  BarChart3,
  Sparkles
} from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const router = useRouter();
  const { user, logout } = useAuthStore();

  const navigation = [
    { name: 'Dashboard', href: '/', icon: Home },
    { name: 'Projects', href: '/projects', icon: Video },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar */}
      <div className={`fixed inset-0 z-50 lg:hidden ${sidebarOpen ? '' : 'hidden'}`}>
        <div className="fixed inset-0 bg-gray-900/80" onClick={() => setSidebarOpen(false)} />
        <nav className="fixed top-0 left-0 bottom-0 flex w-full max-w-xs flex-col bg-white">
          <div className="flex h-16 items-center justify-between px-6">
            <span className="text-xl font-bold text-gray-900">Reels Generator</span>
            <button
              onClick={() => setSidebarOpen(false)}
              className="text-gray-500 hover:text-gray-900"
            >
              <X className="h-6 w-6" />
            </button>
          </div>
          <SidebarContent
            navigation={navigation}
            currentPath={router.pathname}
            onLogout={handleLogout}
          />
        </nav>
      </div>

      {/* Desktop sidebar */}
      <nav className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-72 lg:flex-col">
        <div className="flex grow flex-col gap-y-5 overflow-y-auto bg-gray-900 px-6 pb-4">
          <div className="flex h-16 shrink-0 items-center">
            <Sparkles className="h-8 w-8 text-primary-500" />
            <span className="ml-2 text-xl font-bold text-white">Reels Generator</span>
          </div>
          <SidebarContent
            navigation={navigation}
            currentPath={router.pathname}
            onLogout={handleLogout}
            dark
          />
        </div>
      </nav>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar */}
        <div className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 bg-white px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
          <button
            type="button"
            className="-m-2.5 p-2.5 text-gray-700 lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>

          <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
            <div className="flex flex-1 items-center justify-between">
              <h1 className="text-lg font-semibold text-gray-900">
                {navigation.find(item => item.href === router.pathname)?.name || 'Dashboard'}
              </h1>
              
              <div className="flex items-center gap-x-4">
                <Link
                  href="/projects/new"
                  className="inline-flex items-center gap-x-2 rounded-md bg-primary-600 px-3.5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
                >
                  <Plus className="h-4 w-4" />
                  New Project
                </Link>
                
                <div className="flex items-center gap-x-2">
                  <span className="text-sm text-gray-700">{user?.username}</span>
                  <div className="h-8 w-8 rounded-full bg-primary-500 flex items-center justify-center text-white font-medium">
                    {user?.username?.[0]?.toUpperCase()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="py-10">
          <div className="px-4 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  );
};

interface SidebarContentProps {
  navigation: Array<{ name: string; href: string; icon: any }>;
  currentPath: string;
  onLogout: () => void;
  dark?: boolean;
}

const SidebarContent: React.FC<SidebarContentProps> = ({
  navigation,
  currentPath,
  onLogout,
  dark = false,
}) => {
  const textColor = dark ? 'text-gray-300' : 'text-gray-700';
  const hoverBg = dark ? 'hover:bg-gray-800' : 'hover:bg-gray-50';
  const activeBg = dark ? 'bg-gray-800' : 'bg-gray-50';
  const activeText = dark ? 'text-white' : 'text-primary-600';

  return (
    <nav className="flex flex-1 flex-col">
      <ul role="list" className="flex flex-1 flex-col gap-y-7">
        <li>
          <ul role="list" className="-mx-2 space-y-1">
            {navigation.map((item) => {
              const isActive = currentPath === item.href;
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    className={`
                      group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold
                      ${isActive ? `${activeBg} ${activeText}` : `${textColor} ${hoverBg}`}
                    `}
                  >
                    <item.icon className={`h-6 w-6 shrink-0 ${isActive ? activeText : textColor}`} />
                    {item.name}
                  </Link>
                </li>
              );
            })}
          </ul>
        </li>
        <li className="mt-auto">
          <button
            onClick={onLogout}
            className={`
              group -mx-2 flex gap-x-3 rounded-md p-2 text-sm font-semibold leading-6
              ${textColor} ${hoverBg} w-full
            `}
          >
            <LogOut className={`h-6 w-6 shrink-0 ${textColor}`} />
            Log out
          </button>
        </li>
      </ul>
    </nav>
  );
};
