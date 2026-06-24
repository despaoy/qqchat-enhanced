'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '@/contexts/AuthContext';

/**
 * 页面表单数据持久化 Hook
 * 自动保存和恢复页面表单数据，刷新后不丢失
 *
 * @param pageKey 页面唯一标识（如 'training', 'settings'）
 * @param defaultData 默认数据
 * @returns [data, setData, saveData] 数据、设置函数、手动保存函数
 */
export function usePageData<T extends Record<string, unknown>>(
  pageKey: string,
  defaultData: T
): [T, (data: T | ((prev: T) => T)) => void, () => Promise<void>] {
  const { user, loadPageData, savePageData } = useAuth();
  const [data, setData] = useState<T>(defaultData);
  const initializedRef = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 用 ref 保存最新的 savePageData，避免其引用变化触发自动保存 effect 重跑
  // （savePageData 依赖 user/loading，若进入 effect 依赖会形成潜在循环）
  const savePageDataRef = useRef(savePageData);
  useEffect(() => {
    savePageDataRef.current = savePageData;
  }, [savePageData]);

  // 初始化：从 localStorage 或后端加载数据
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const loadData = async () => {
      try {
        // 先尝试 localStorage（快速）
        const localData = localStorage.getItem(`qq_assistant_data_${pageKey}`);
        if (localData) {
          const parsed = JSON.parse(localData);
          setData({ ...defaultData, ...parsed });
        }

        // 再尝试后端数据（更可靠）
        const serverData = await loadPageData(pageKey);
        if (serverData) {
          setData({ ...defaultData, ...serverData as Partial<T> });
        }
      } catch (err) {
        console.error('Failed to load page data:', err);
      }
    };

    loadData();
  }, [pageKey, defaultData, loadPageData]);

  // 手动保存：先 localStorage 再后端
  const saveData = useCallback(async () => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    localStorage.setItem(`qq_assistant_data_${pageKey}`, JSON.stringify(data));
    if (user) {
      try {
        await savePageDataRef.current(pageKey, data);
      } catch (err) {
        console.error('Failed to save page data to server:', err);
      }
    }
  }, [data, pageKey, user]);

  // 数据变化时自动延迟保存（1秒防抖）
  useEffect(() => {
    if (!initializedRef.current) return;
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      localStorage.setItem(`qq_assistant_data_${pageKey}`, JSON.stringify(data));
      if (user) {
        savePageDataRef.current(pageKey, data).catch(err => {
          console.error('Auto-save failed:', err);
        });
      }
    }, 1000);

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [data, pageKey, user]);

  return [data, setData, saveData];
}
