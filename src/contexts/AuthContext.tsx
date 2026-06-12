'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { api, User } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  savePageData: (pageKey: string, data: Record<string, unknown>) => Promise<void>;
  loadPageData: (pageKey: string) => Promise<Record<string, unknown> | null>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window === 'undefined') return null;
    const cachedUser = localStorage.getItem('qq_assistant_user');
    if (cachedUser) {
      try {
        return JSON.parse(cachedUser);
      } catch {
        return null;
      }
    }
    return null;
  });
  const [loading, setLoading] = useState(true);

  // 异步验证 token 是否仍然有效（Cookie 由浏览器自动携带）
  useEffect(() => {
    fetch('/api/auth/me', {
      credentials: 'include', // 携带 httpOnly Cookie
    }).then(res => {
      if (!res.ok) {
        localStorage.removeItem('qq_assistant_user');
        setUser(null);
      }
    }).catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // 接收 httpOnly Cookie
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || '登录失败');
    }
    const data = await response.json();
    // 同时存 localStorage 作为向后兼容和用户信息缓存
    localStorage.setItem('qq_assistant_user', JSON.stringify(data.user));
    setUser(data.user);
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // 接收 httpOnly Cookie
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || '注册失败');
    }
    const data = await response.json();
    localStorage.setItem('qq_assistant_user', JSON.stringify(data.user));
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    // 调用后端清除 Cookie
    fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    localStorage.removeItem('qq_assistant_user');
    setUser(null);
  }, []);

  const savePageData = useCallback(async (pageKey: string, data: Record<string, unknown>) => {
    if (!user) return;
    localStorage.setItem(`qq_assistant_data_${pageKey}`, JSON.stringify(data));
    try {
      await api.saveUserData(pageKey, JSON.stringify(data));
    } catch (err) {
      console.error('Failed to save user data to server:', err);
    }
  }, [user]);

  const loadPageData = useCallback(async (pageKey: string): Promise<Record<string, unknown> | null> => {
    const localData = localStorage.getItem(`qq_assistant_data_${pageKey}`);
    let result = localData ? (() => { try { return JSON.parse(localData); } catch { return null; } })() : null;

    if (user) {
      try {
        const res = await api.getUserData(pageKey);
        if (res.success && res.data) {
          const serverData = 'data_json' in res.data ? JSON.parse((res.data as { data_json: string }).data_json) : null;
          if (serverData) {
            result = serverData;
            localStorage.setItem(`qq_assistant_data_${pageKey}`, JSON.stringify(serverData));
          }
        }
      } catch (err) {
        console.error('Failed to load user data from server:', err);
      }
    }

    return result;
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, savePageData, loadPageData }}>
      {children}
    </AuthContext.Provider>
  );
}
