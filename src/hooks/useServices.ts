'use client';

import { useState, useEffect } from 'react';
import { api, ServiceStatus } from '@/lib/api';

export function useServices(enabled = true) {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const fetchServices = async () => {
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
  };

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchServices();

    // 每60秒刷新一次
    const interval = setInterval(fetchServices, 60000);
    return () => clearInterval(interval);
  }, [enabled]);

  return {
    services,
    loading,
    error,
    refetch: fetchServices,
  };
}
