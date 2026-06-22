'use client';

/**
 * 统计数据 Hook
 *
 * 获取系统统计数据（今日回复数、平均响应时间、活跃会话数、CPU/内存/GPU 使用率等），
 * 自动每 30 秒刷新一次，支持手动刷新。
 *
 * @returns {{ stats: StatsResponse | null, loading: boolean, error: string | null, refetch: () => Promise<void> }}
 *   - stats: 统计数据对象
 *   - loading: 是否正在加载
 *   - error: 错误信息（如有）
 *   - refetch: 手动刷新数据的函数
 */

import { useState, useEffect, useCallback } from 'react';
import { api, StatsResponse } from '@/lib/api';

export function useStats(enabled = true) {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  // useCallback：fetchStats 引用稳定，可安全放入 effect 依赖（消除 stale closure），
  // 且作为 refetch 返回时不会触发消费方不必要的重渲染。
  const fetchStats = useCallback(async () => {
    if (!enabled) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取统计数据失败');
      console.error('Failed to fetch stats:', err);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    fetchStats();

    // 每30秒刷新一次；页面不可见时跳过，避免后台无谓请求
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      fetchStats();
    }, 30000);
    return () => clearInterval(interval);
  }, [enabled, fetchStats]);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats,
  };
}
