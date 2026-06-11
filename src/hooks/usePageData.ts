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

  // 自动保存：数据变化后延迟保存
  const saveData = useCallback(async () => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    // 先保存到 localStorage（即时）
    localStorage.setItem(`qq_assistant_data_${pageKey}`, JSON.stringify(data));
    // 再保存到后端
    if (user) {
      try {
        await savePageData(pageKey, data);
      } catch (err) {
        console.error('Failed to save page data to server:', err);
      }
    }
  }, [data, pageKey, user, savePageData]);

  // 数据变化时自动延迟保存
  useEffect(() => {
    if (!initializedRef.current) return;
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      localStorage.setItem(`qq_assistant_data_${pageKey}`, JSON.stringify(data));
      if (user) {
        savePageData(pageKey, data).catch(err => {
          console.error('Auto-save failed:', err);
        });
      }
    }, 1000); // 1秒防抖

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [data, pageKey, user, savePageData]);

  return [data, setData, saveData];
}
