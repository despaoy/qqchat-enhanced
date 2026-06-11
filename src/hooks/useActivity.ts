'use client';

import { useState, useEffect } from 'react';
import { api, ActivityData } from '@/lib/api';

export function useActivity() {
  const [activity, setActivity] = useState<ActivityData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchActivity = async () => {
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
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchActivity();
    
    // 每60秒刷新一次
    const interval = setInterval(fetchActivity, 60000);
    return () => clearInterval(interval);
  }, []);

  return {
    activity,
    loading,
    error,
    refetch: fetchActivity,
  };
}
