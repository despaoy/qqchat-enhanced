'use client';

/**
 * 多 LoRA 路由 Hook
 *
 * 管理路由配置、适配器兼容性状态和路由日志。
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

export interface RouterConfig {
  enabled: boolean;
  default_adapter: string;
  mode: 'manual' | 'rule' | 'intent';
  persona_adapters: Record<string, string>;
  rag_confidence_threshold: number;
  persona_keywords: Record<string, string[]>;
}

export interface AdapterInfo {
  name: string;
  path: string;
  compatibility: {
    compatible: boolean;
    checked_at: string;
    checks: Record<string, boolean>;
    warnings: string[];
    errors: string[];
  } | null;
}

export interface RoutingLog {
  timestamp: string;
  trace_id: string;
  target: string;
  adapter_name: string;
  confidence: number;
  reason: string;
  fallback: boolean;
  requires_rag: boolean;
}

export function useRouter(enabled = true) {
  const [config, setConfig] = useState<RouterConfig | null>(null);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [logs, setLogs] = useState<RoutingLog[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    if (!enabled) return;
    try {
      setLoading(true);
      setError(null);
      const [cfg, adp, lg] = await Promise.all([
        api.getRouterConfig(),
        api.getRouterAdapters().catch(() => ({ adapters: [] })),
        api.getRouterLogs().catch(() => ({ logs: [] })),
      ]);
      setConfig(cfg.config || null);
      setAdapters(adp.adapters || []);
      setLogs(lg.logs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载路由数据失败');
      console.error('Failed to fetch router data:', err);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  const updateConfig = useCallback(async (req: Partial<RouterConfig>) => {
    try {
      setSaving(true);
      const result = await api.updateRouterConfig(req);
      setConfig(result.config || null);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新路由配置失败');
      console.error('Failed to update router config:', err);
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  const checkAdapter = useCallback(async (adapterName: string) => {
    try {
      setChecking(adapterName);
      const result = await api.checkAdapter(adapterName);
      await fetchAll();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '兼容性检查失败');
      console.error('Failed to check adapter:', err);
      throw err;
    } finally {
      setChecking(null);
    }
  }, [fetchAll]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    fetchAll();
  }, [enabled, fetchAll]);

  return {
    config,
    adapters,
    logs,
    loading,
    error,
    saving,
    checking,
    refetch: fetchAll,
    updateConfig,
    checkAdapter,
  };
}
