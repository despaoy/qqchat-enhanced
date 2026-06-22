'use client';

import { useState, useEffect, useCallback } from 'react';
import { api, ActivityData } from '@/lib/api';

export function useActivity() {
  const [activity, setActivity] = useState<ActivityData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // useCallback 保证 fetchActivity 引用稳定：
  // 1. 作为 refetch 返回时不会触发消费方不必要的重渲染
  // 2. 可安全放入下方 effect 依赖，消除 stale closure 隐患
  const fetchActivity = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getActivity();
      setActivity(data.activity);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取活动趋势失败');
      console.error('Failed to fetch activity:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActivity();

    // 每60秒刷新一次；页面不可见时跳过，避免后台无谓请求
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      fetchActivity();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchActivity]);

  return {
    activity,
    loading,
    error,
    refetch: fetchActivity,
  };
}
