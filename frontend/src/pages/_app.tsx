// frontend/src/pages/_app.tsx
import '@/styles/globals.css';
import type { AppProps } from 'next/app';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';

const publicPaths = ['/login', '/register'];

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const { isAuthenticated, fetchUser } = useAuthStore();

  useEffect(() => {
    // Fetch user on app load if authenticated
    if (isAuthenticated) {
      fetchUser();
    }
  }, []);

  useEffect(() => {
    // Redirect logic
    const isPublicPath = publicPaths.includes(router.pathname);
    
    if (!isAuthenticated && !isPublicPath) {
      router.push('/login');
    } else if (isAuthenticated && isPublicPath) {
      router.push('/');
    }
  }, [isAuthenticated, router.pathname]);

  return <Component {...pageProps} />;
}
