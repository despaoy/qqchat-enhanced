"""RAG 消融实验 - 对比 vector-only / BM25-only / hybrid / hybrid+reranker 四变体。

遵循路线图 guardrail：
- 控制变量：同一数据集、同一 k 值、同一检索评估指标
- 无需 GPU，直接在 CPU 运行
- 支持 --mock 模式用于无向量库时的 CPU 验证
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


@dataclass
class RAGAblationResult:
    """单变体消融结果。"""
    variant_name: str
    recall_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    avg_latency_ms: float = 0.0
    error: str = ""
    per_question_count: int = 0


class RAGAblation:
    """RAG 检索消融实验运行器。"""

    DEFAULT_VARIANTS = ["vector_only", "bm25_only", "hybrid", "hybrid_reranker"]

    def __init__(self, dataset_path: str = "", k: int = 5):
        self.dataset_path = dataset_path or str(
            _BACKEND_DIR / "evaluation" / "retrieval_eval_dataset.json"
        )
        self.k = k
        self._vector_db = None
        self._rag_helper = None

    def _get_vector_db(self):
        if self._vector_db is None:
            from knowledge.vector_db import get_vector_db
            self._vector_db = get_vector_db()
        return self._vector_db

    def _get_rag_helper(self):
        if self._rag_helper is None:
            from knowledge.rag_helper import get_rag_helper
            self._rag_helper = get_rag_helper()
        return self._rag_helper

    def variant_vector_only(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """纯向量检索变体。"""
        vdb = self._get_vector_db()
        return vdb.search(query, top_k=top_k, threshold=0.0)

    def variant_bm25_only(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """纯 BM25 检索变体。"""
        vdb = self._get_vector_db()
        results = vdb.bm25.search(query, top_k=top_k, threshold=0.0)
        # BM25 返回 (index, score) 元组，转换为 dict 列表
        return [
            {**vdb.metadata[idx], "score": score, "id": vdb.metadata[idx].get("id", str(idx))}
            for idx, score in results
            if 0 <= idx < len(vdb.metadata)
        ]

    def variant_hybrid(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """混合检索变体（向量 + BM25 融合）。"""
        vdb = self._get_vector_db()
        return vdb.hybrid_search(query, top_k=top_k, threshold=0.0, keyword_weight=0.3)

    def variant_hybrid_reranker(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """混合 + 重排器变体。"""
        helper = self._get_rag_helper()
        return helper.retrieve_context(query, top_k=top_k, enable_rerank=True, use_cache=False)

    def _get_variant_fn(self, variant_name: str) -> Callable[[str, int], List[Dict[str, Any]]]:
        """获取变体检索函数。"""
        fns = {
            "vector_only": self.variant_vector_only,
            "bm25_only": self.variant_bm25_only,
            "hybrid": self.variant_hybrid,
            "hybrid_reranker": self.variant_hybrid_reranker,
        }
        if variant_name not in fns:
            raise ValueError(f"未知变体: {variant_name}，可选: {list(fns.keys())}")
        return fns[variant_name]

    def run_variant(self, variant_name: str) -> RAGAblationResult:
        """运行单个变体并计算指标。"""
        from evaluation.retrieval_metrics import RetrievalMetrics
        metrics = RetrievalMetrics()
        variant_fn = self._get_variant_fn(variant_name)
        result = RAGAblationResult(variant_name=variant_name)

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                dataset = json.load(f)
            questions = dataset.get("questions", [])

            latencies: List[float] = []
            recall_sum = 0.0
            mrr_sum = 0.0
            ndcg_sum = 0.0
            count = 0

            for q in questions:
                query = q.get("question", "")
                expected_ids = q.get("expected_doc_ids", [])
                start = time.monotonic()
                try:
                    retrieved = variant_fn(query, self.k)
                except Exception as e:
                    logger.warning(f"变体 {variant_name} 检索失败 ({q.get('id')}): {e}")
                    retrieved = []
                latencies.append((time.monotonic() - start) * 1000)

                retrieved_ids = [str(r.get("id", r.get("chunk_id", ""))) for r in retrieved]
                recall_sum += metrics.recall_at_k(retrieved_ids, expected_ids, self.k)
                mrr_sum += metrics.mrr(retrieved_ids, expected_ids)
                ndcg_sum += metrics.ndcg(retrieved_ids, expected_ids, self.k)
                count += 1

            result.recall_at_5 = round(recall_sum / max(count, 1), 4)
            result.mrr = round(mrr_sum / max(count, 1), 4)
            result.ndcg_at_5 = round(ndcg_sum / max(count, 1), 4)
            result.avg_latency_ms = round(sum(latencies) / max(len(latencies), 1), 2)
            result.per_question_count = count

        except Exception as e:
            result.error = str(e)
            logger.error(f"变体 {variant_name} 运行失败: {e}")

        return result

    def run_all(self, variants: Optional[List[str]] = None) -> List[RAGAblationResult]:
        """运行所有变体。"""
        variants = variants or self.DEFAULT_VARIANTS
        results: List[RAGAblationResult] = []
        for v in variants:
            logger.info(f"运行 RAG 消融变体: {v}")
            results.append(self.run_variant(v))
        return results

    def run_all_mock(self) -> List[RAGAblationResult]:
        """Mock 模式：返回预置结果用于 CPU 验证。"""
        mock_data = {
            "vector_only": {"recall": 0.62, "mrr": 0.48, "ndcg": 0.55, "latency": 35},
            "bm25_only": {"recall": 0.58, "mrr": 0.45, "ndcg": 0.52, "latency": 8},
            "hybrid": {"recall": 0.72, "mrr": 0.58, "ndcg": 0.65, "latency": 42},
            "hybrid_reranker": {"recall": 0.78, "mrr": 0.65, "ndcg": 0.71, "latency": 120},
        }
        results: List[RAGAblationResult] = []
        for name, m in mock_data.items():
            results.append(RAGAblationResult(
                variant_name=name,
                recall_at_5=m["recall"],
                mrr=m["mrr"],
                ndcg_at_5=m["ndcg"],
                avg_latency_ms=m["latency"],
                per_question_count=50,
            ))
        return results

    def build_comparison_table(self, results: List[RAGAblationResult]) -> str:
        """生成 Markdown 对比表。"""
        header = "| variant | recall@5 | mrr | ndcg@5 | avg_latency_ms |"
        sep = "|---------|----------|-----|--------|----------------|"
        rows = [header, sep]
        for r in results:
            rows.append(f"| {r.variant_name} | {r.recall_at_5} | {r.mrr} | {r.ndcg_at_5} | {r.avg_latency_ms} |")
        return "\n".join(rows)

    def save_report(self, results: List[RAGAblationResult], output_dir: Path) -> Path:
        """保存 JSON + Markdown 报告。"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        report = {
            "experiment_type": "rag_ablation",
            "timestamp": ts,
            "k": self.k,
            "dataset": self.dataset_path,
            "results": [asdict(r) for r in results],
            "comparison_table": self.build_comparison_table(results),
        }
        json_path = output_dir / f"rag_ablation_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        md_path = output_dir / f"rag_ablation_{ts}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# RAG 消融实验报告\n\n")
            f.write(f"**时间**: {ts}\n")
            f.write(f"**数据集**: {self.dataset_path}\n")
            f.write(f"**k值**: {self.k}\n\n")
            f.write("## 对比结果\n\n")
            f.write(self.build_comparison_table(results))
            f.write("\n\n## 结论\n\n")
            best_recall = max(results, key=lambda r: r.recall_at_5)
            fastest = min(results, key=lambda r: r.avg_latency_ms)
            f.write(f"- 召回最高: **{best_recall.variant_name}** (recall@5={best_recall.recall_at_5})\n")
            f.write(f"- 延迟最低: **{fastest.variant_name}** ({fastest.avg_latency_ms}ms)\n")

        logger.info(f"报告已保存: {json_path}, {md_path}")
        return json_path


def main():
    parser = argparse.ArgumentParser(description="RAG 消融实验")
    parser.add_argument("--mock", action="store_true", help="Mock 模式（CPU 验证）")
    parser.add_argument("--dataset", type=str, default="", help="检索评估数据集路径")
    parser.add_argument("--output-dir", type=str, default="deploy/results", help="报告输出目录")
    parser.add_argument("--k", type=int, default=5, help="recall@k / nDCG@k 的 k 值")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    ablation = RAGAblation(dataset_path=args.dataset, k=args.k)

    if args.mock:
        results = ablation.run_all_mock()
    else:
        results = ablation.run_all()

    print("\n" + "=" * 60)
    print("  RAG 消融对比结果")
    print("=" * 60)
    print(ablation.build_comparison_table(results))

    output_dir = Path(args.output_dir)
    report_path = ablation.save_report(results, output_dir)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
