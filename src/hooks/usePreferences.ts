'use client';

/**
 * 偏好数据管理 Hook
 *
 * 管理 DPO/ORPO 训练偏好对的 CRUD、导出和历史采样。
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

export interface PreferencePair {
  id: string;
  prompt: string;
  chosen: string;
  rejected: string;
  rubric: Record<string, any>;
  annotator: string;
  metadata: Record<string, any>;
  review_status: 'pending' | 'approved' | 'rejected';
  created_at: string;
}

export function usePreferences(enabled = true) {
  const [preferences, setPreferences] = useState<PreferencePair[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [exporting, setExporting] = useState(false);
  const [sampling, setSampling] = useState(false);

  const fetchPreferences = useCallback(async (status?: string) => {
    if (!enabled) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getPreferences(status || undefined);
      setPreferences(data.preferences || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取偏好对失败');
      console.error('Failed to fetch preferences:', err);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  const createPreference = useCallback(async (req: {
    prompt: string;
    chosen: string;
    rejected: string;
    annotator?: string;
    rubric?: Record<string, any>;
  }) => {
    try {
      const result = await api.createPreference(req);
      await fetchPreferences(filterStatus);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建偏好对失败');
      console.error('Failed to create preference:', err);
      throw err;
    }
  }, [fetchPreferences, filterStatus]);

  const updatePreference = useCallback(async (id: string, req: { review_status?: 'pending' | 'approved' | 'rejected'; rubric?: Record<string, any>; annotator?: string }) => {
    try {
      await api.updatePreference(id, req);
      setPreferences(prev => prev.map(p => p.id === id ? { ...p, ...req } : p));
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新偏好对失败');
      console.error('Failed to update preference:', err);
      throw err;
    }
  }, []);

  const exportPreferences = useCallback(async (req: { review_status?: string; format?: string }) => {
    try {
      setExporting(true);
      return await api.exportPreferences(req);
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败');
      console.error('Failed to export preferences:', err);
      throw err;
    } finally {
      setExporting(false);
    }
  }, []);

  const sampleFromHistory = useCallback(async (req: { limit?: number; session_id?: string }) => {
    try {
      setSampling(true);
      return await api.sampleFromHistory(req);
    } catch (err) {
      setError(err instanceof Error ? err.message : '采样失败');
      console.error('Failed to sample from history:', err);
      throw err;
    } finally {
      setSampling(false);
    }
  }, []);

  const changeFilter = useCallback((status: string) => {
    setFilterStatus(status);
    fetchPreferences(status);
  }, [fetchPreferences]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    fetchPreferences();
  }, [enabled, fetchPreferences]);

  return {
    preferences,
    total,
    loading,
    error,
    filterStatus,
    exporting,
    sampling,
    refetch: () => fetchPreferences(filterStatus),
    fetchPreferences,
    createPreference,
    updatePreference,
    exportPreferences,
    sampleFromHistory,
    setFilterStatus: changeFilter,
  };
}
