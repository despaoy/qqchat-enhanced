'use client';

/**
 * LoRA 模型管理 Hook
 *
 * 管理 LoRA 微调模型的获取、状态切换和删除操作。
 * 在挂载时自动获取 LoRA 列表，提供手动刷新、状态切换和删除功能。
 *
 * @returns {{ loras: LoraModel[], total: number, loading: boolean, error: string | null, refetch: () => Promise<void>, toggleLoraStatus: (id: string) => Promise<LoraModel>, deleteLora: (id: string) => Promise<void> }}
 *   - loras: LoRA 模型列表
 *   - total: 模型总数
 *   - loading: 是否正在加载
 *   - error: 错误信息（如有）
 *   - refetch: 手动刷新列表
 *   - toggleLoraStatus: 切换指定 LoRA 的激活/停用状态
 *   - deleteLora: 删除指定 LoRA 模型
 */

import { useState, useEffect } from 'react';
import { api, LoraModel } from '@/lib/api';

export function useLoras(enabled = true) {
  const [loras, setLoras] = useState<LoraModel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const fetchLoras = async () => {
    if (!enabled) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getLoras();
      setLoras(data.loras);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取LoRA模型失败');
      console.error('Failed to fetch loras:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleLoraStatus = async (id: string) => {
    try {
      const currentLora = loras.find(l => l.id === id);
      if (!currentLora) {
        throw new Error('LoRA模型不存在');
      }
      // 如果当前已激活，则停用；否则激活（后端会自动停用其他）
      const newStatus = currentLora.status === 'active' ? 'inactive' : 'active';
      const updatedLora = await api.toggleLoraStatus(id, currentLora.status);
      // 同步前端状态：激活时自动停用其他，停用时只更新自己
      setLoras(prev => prev.map(lora => {
        if (lora.id === id) return updatedLora;
        if (newStatus === 'active') return { ...lora, status: 'inactive' };
        return lora;
      }));
      return updatedLora;
    } catch (err) {
      setError(err instanceof Error ? err.message : '切换LoRA状态失败');
      console.error('Failed to toggle lora status:', err);
      throw err;
    }
  };

  const deleteLora = async (id: string) => {
    try {
      await api.deleteLora(id);
      setLoras(prev => prev.filter(lora => lora.id !== id));
      setTotal(prev => prev - 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除LoRA模型失败');
      console.error('Failed to delete lora:', err);
      throw err;
    }
  };

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchLoras();
  }, [enabled]);

  return {
    loras,
    total,
    loading,
    error,
    refetch: fetchLoras,
    toggleLoraStatus,
    deleteLora,
  };
}
