'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { authApi, getTokens, clearTokens } from '@/lib/api';
import { ROUTES } from '@/lib/constants';
import type { User } from '@/lib/types';

// =============================================================================
// AUTH CONTEXT TYPES
// =============================================================================
interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// =============================================================================
// PUBLIC ROUTES (no auth required)
// =============================================================================
const PUBLIC_ROUTES = [ROUTES.LOGIN, ROUTES.REGISTER, '/auth/callback'];

// =============================================================================
// AUTH PROVIDER
// =============================================================================
interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!user;

  // Check if current route is public
  const isPublicRoute = PUBLIC_ROUTES.some(route => pathname?.startsWith(route));

  // Fetch current user
  const refreshUser = useCallback(async () => {
    try {
      const tokens = getTokens();
      if (!tokens) {
        setUser(null);
        return;
      }

      const userData = await authApi.me();
      setUser(userData);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      clearTokens();
      setUser(null);
    }
  }, []);

  // Login
  const login = useCallback(async (email: string, password: string) => {
    await authApi.login(email, password);
    await refreshUser();
    router.push(ROUTES.HOME);
  }, [refreshUser, router]);

  // Register
  const register = useCallback(async (email: string, password: string, name: string) => {
    await authApi.register(email, password, name);
    await refreshUser();
    router.push(ROUTES.HOME);
  }, [refreshUser, router]);

  // Google OAuth
  const loginWithGoogle = useCallback(async () => {
    const { auth_url } = await authApi.getGoogleAuthUrl();
    window.location.href = auth_url;
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      router.push(ROUTES.LOGIN);
    }
  }, [router]);

  // Initial auth check
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      await refreshUser();
      setIsLoading(false);
    };
    initAuth();
  }, [refreshUser]);

  // Redirect logic
  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated && !isPublicRoute) {
      // Not logged in on protected route -> redirect to login
      router.push(ROUTES.LOGIN);
    } else if (isAuthenticated && isPublicRoute) {
      // Logged in on public route -> redirect to home
      router.push(ROUTES.HOME);
    }
  }, [isAuthenticated, isPublicRoute, isLoading, router]);

  // Show loading spinner during initial auth check
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render children on protected routes if not authenticated
  if (!isAuthenticated && !isPublicRoute) {
    return null;
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated,
        login,
        register,
        loginWithGoogle,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// =============================================================================
// USE AUTH HOOK
// =============================================================================
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
