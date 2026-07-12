'use client';

/**
 * 评估管理 Hook
 *
 * 管理 Gold 评估集、评估运行历史和用户反馈的获取与操作。
 */

import { useState, useEffect, useCallback } from 'react';
import { api, type EvaluationRunRecord, type FeedbackRecord, type GoldPromptRecord } from '@/lib/api';

export type GoldPrompt = GoldPromptRecord;

export type EvalRun = EvaluationRunRecord;

export type Feedback = FeedbackRecord;

export function useEvaluation(enabled = true) {
  const [goldSet, setGoldSet] = useState<{ total: number; category_breakdown: Record<string, number>; prompts: GoldPrompt[] }>({
    total: 0,
    category_breakdown: {},
    prompts: [],
  });
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const fetchAll = useCallback(async () => {
    if (!enabled) return;
    try {
      setLoading(true);
      setError(null);
      const [gold, runsResp, fbResp] = await Promise.all([
        api.getGoldSet(),
        api.getEvaluationRuns(),
        api.getFeedback().catch(() => ({ feedbacks: [], total: 0 })),
      ]);
      setGoldSet({
        total: gold.total,
        category_breakdown: gold.category_breakdown || {},
        prompts: gold.prompts || [],
      });
      setRuns(runsResp.runs || []);
      setFeedbacks(fbResp.feedbacks || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载评估数据失败');
      console.error('Failed to fetch evaluation data:', err);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  const runEvaluation = useCallback(async (req: { adapter_name?: string; categories?: string[]; mock?: boolean }) => {
    try {
      setRunning(true);
      const result = await api.runEvaluation(req);
      await fetchAll();
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '运行评估失败');
      console.error('Failed to run evaluation:', err);
      throw err;
    } finally {
      setRunning(false);
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
    goldSet,
    runs,
    feedbacks,
    loading,
    error,
    running,
    refetch: fetchAll,
    runEvaluation,
  };
}
