"""检索评估指标 - recall@k / MRR / nDCG / faithfulness / answer_correctness。

遵循路线图 guardrail：
- faithfulness 和 answer_correctness 用规则版（关键词覆盖），不依赖 LLM judge
- evaluate_dataset 接受可注入的 retrieve_fn，便于测试和 ablation
"""
from __future__ import annotations

import json
import math
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """简易分词：中文按字符 + 英文按空格。"""
    return re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', text.lower())


class RetrievalMetrics:
    """检索质量评估指标。"""

    def recall_at_k(self, retrieved_ids: List[str], expected_ids: List[str], k: int = 5) -> float:
        """Recall@k：前 k 个检索结果中命中期望文档的比例。"""
        if not expected_ids:
            return 0.0
        top_k = retrieved_ids[:k]
        hits = sum(1 for eid in expected_ids if eid in top_k)
        return round(hits / len(expected_ids), 4)

    def mrr(self, retrieved_ids: List[str], expected_ids: List[str]) -> float:
        """MRR：第一个命中期望结果的倒数排名。"""
        for i, rid in enumerate(retrieved_ids, 1):
            if rid in expected_ids:
                return round(1.0 / i, 4)
        return 0.0

    def ndcg(self, retrieved_ids: List[str], expected_ids: List[str], k: int = 5) -> float:
        """nDCG@k：归一化折损累积增益。"""
        def dcg(rels: List[float]) -> float:
            return sum(r / math.log2(i + 2) for i, r in enumerate(rels))

        rels = [1.0 if rid in expected_ids else 0.0 for rid in retrieved_ids[:k]]
        ideal_rels = sorted(rels, reverse=True)
        idcg = dcg(ideal_rels)
        if idcg == 0:
            return 0.0
        return round(dcg(rels) / idcg, 4)

    def faithfulness(self, answer: str, citations: List[Dict[str, Any]]) -> float:
        """规则版 faithfulness：答案关键词被引用覆盖的比例。"""
        if not answer or not citations:
            return 0.0
        answer_tokens = set(_tokenize(answer))
        if not answer_tokens:
            return 0.0
        citation_tokens: set = set()
        for c in citations:
            excerpt = c.get("evidence_excerpt", "") or c.get("content", "")
            citation_tokens.update(_tokenize(excerpt))
        if not citation_tokens:
            return 0.0
        covered = answer_tokens & citation_tokens
        return round(len(covered) / len(answer_tokens), 4)

    def answer_correctness(self, answer: str, gold_answer: str) -> float:
        """规则版 answer_correctness：gold 答案关键词重合度。"""
        if not gold_answer or not answer:
            return 0.0
        gold_tokens = set(_tokenize(gold_answer))
        answer_tokens = set(_tokenize(answer))
        if not gold_tokens:
            return 0.0
        overlap = gold_tokens & answer_tokens
        return round(len(overlap) / len(gold_tokens), 4)

    def evaluate_dataset(self, dataset_path: str,
                         retrieve_fn: Callable[[str], List[Dict[str, Any]]],
                         k: int = 5) -> Dict[str, Any]:
        """遍历检索评估数据集，计算聚合指标。

        Args:
            dataset_path: retrieval_eval_dataset.json 路径
            retrieve_fn: 检索函数，签名 (query: str) -> List[Dict]，每个 Dict 需含 id/title 字段
            k: recall@k / nDCG@k 的 k 值

        Returns:
            {total, avg_recall@k, avg_mrr, avg_ndcg@k, per_question: [...]}
        """
        with open(dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        questions = dataset.get("questions", [])

        per_question: List[Dict[str, Any]] = []
        recall_sum = 0.0
        mrr_sum = 0.0
        ndcg_sum = 0.0
        count = 0

        for q in questions:
            qid = q.get("id", f"q{count}")
            query = q.get("question", "")
            expected_ids = q.get("expected_doc_ids", [])
            expected_titles = q.get("expected_doc_titles", [])
            gold_answer = q.get("gold_answer", "")

            try:
                results = retrieve_fn(query)
            except Exception as e:
                logger.warning(f"检索失败 ({qid}): {e}")
                results = []

            retrieved_ids = [str(r.get("id", r.get("chunk_id", ""))) for r in results]
            retrieved_titles = [r.get("title", r.get("original_title", "")) for r in results]

            # 匹配：按 id 或 title 匹配
            hit_ids = [eid for eid in expected_ids if eid in retrieved_ids]
            hit_titles = [et for et in expected_titles if et in retrieved_titles]
            matched_expected = expected_ids if hit_ids else (expected_titles if expected_titles else [])

            r_at_k = self.recall_at_k(retrieved_ids, expected_ids, k) if expected_ids else 0.0
            mrr_val = self.mrr(retrieved_ids, expected_ids) if expected_ids else 0.0
            ndcg_val = self.ndcg(retrieved_ids, expected_ids, k) if expected_ids else 0.0

            recall_sum += r_at_k
            mrr_sum += mrr_val
            ndcg_sum += ndcg_val
            count += 1

            per_question.append({
                "id": qid,
                "question": query,
                "recall_at_k": r_at_k,
                "mrr": mrr_val,
                "ndcg_at_k": ndcg_val,
                "retrieved_count": len(results),
            })

        return {
            "total": count,
            "avg_recall_at_k": round(recall_sum / max(count, 1), 4),
            "avg_mrr": round(mrr_sum / max(count, 1), 4),
            "avg_ndcg_at_k": round(ndcg_sum / max(count, 1), 4),
            "k": k,
            "per_question": per_question,
        }

    def evaluate_mock(self) -> Dict[str, Any]:
        """Mock 模式：返回预置结果用于 CPU 验证。"""
        return {
            "total": 50,
            "avg_recall_at_k": 0.72,
            "avg_mrr": 0.58,
            "avg_ndcg_at_k": 0.65,
            "k": 5,
            "mock": True,
            "per_question": [
                {"id": "q001", "question": "mock", "recall_at_k": 0.8, "mrr": 0.5, "ndcg_at_k": 0.6, "retrieved_count": 5},
            ],
        }
