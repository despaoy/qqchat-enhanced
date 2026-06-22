'use client';

import { useState, useEffect, useCallback } from 'react';
import { api, ServiceStatus } from '@/lib/api';

export function useServices(enabled = true) {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  // useCallback：fetchServices 引用稳定，可安全放入 effect 依赖（消除 stale closure），
  // 且作为 refetch 返回时不会触发消费方不必要的重渲染。
  const fetchServices = useCallback(async () => {
    if (!enabled) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getServices();
      setServices(data.services);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取服务状态失败');
      console.error('Failed to fetch services:', err);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    fetchServices();

    // 每60秒刷新一次；页面不可见时跳过
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      fetchServices();
    }, 60000);
    return () => clearInterval(interval);
  }, [enabled, fetchServices]);

  return {
    services,
    loading,
    error,
    refetch: fetchServices,
  };
}
