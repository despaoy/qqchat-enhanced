"""
Cross-Encoder重排模块 - 优化版
基于BGE-Reranker模型的文档精排模块，作为RAG检索的第二阶段，
对粗排召回的候选文档进行精确的相关性打分和排序。
改进：分数归一化、模型预热、批量优化、降级机制、GPU显存管理
"""

import torch
import logging
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).parent


def _resolve_path(p: str) -> str:
    if os.path.isabs(p):
        return p
    return str(_BACKEND_DIR / p)


@dataclass
class RerankConfig:
    model_name: str = os.getenv("RERANKER_MODEL_PATH", _resolve_path("bge-reranker-base"))
    device: str = "cuda:0"
    batch_size: int = 8
    max_length: int = 512
    enable_quantization: bool = False
    warmup_on_init: bool = False
    score_normalize: bool = True
    fallback_to_original: bool = True


class CrossEncoderReranker:
    """Cross-Encoder重排器，使用BGE-Reranker-Base模型对候选文档进行精细化相关性评分。

    支持4bit量化、模型预热、GPU/CPU自动切换、分数归一化和降级回退（模型加载失败时返回原始排序）。
    """

    def __init__(self, config: Optional[RerankConfig] = None):
        """初始化重排器。

        Args:
            config: 重排配置，默认使用RerankConfig()
        """
        self.config = config or RerankConfig()
        self.device = self.config.device
        self.tokenizer = None
        self.model = None
        self._model_loaded = False
        self._warmup_done = False

        logger.info(f"Cross-Encoder重排器初始化完成，设备: {self.device}")

    def _check_gpu_available(self) -> bool:
        try:
            if not torch.cuda.is_available():
                return False
            torch.cuda.device_count()
            return True
        except Exception:
            return False

    def _load_model(self) -> bool:
        if self._model_loaded:
            return True

        try:
            if not self._check_gpu_available():
                logger.warning("GPU不可用，尝试使用CPU")
                self.device = "cpu"

            logger.info(f"正在加载Cross-Encoder模型: {self.config.model_name}")

            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            start_time = time.time()

            load_kwargs = {}
            if self.device != "cpu":
                load_kwargs["torch_dtype"] = torch.float16

            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.config.model_name,
                    **load_kwargs
                )
            except Exception as e:
                logger.error(f"本地模型加载失败: {e}")
                abs_path = _resolve_path(self.config.model_name)
                logger.info(f"尝试绝对路径: {abs_path}")
                self.tokenizer = AutoTokenizer.from_pretrained(abs_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    abs_path,
                    **load_kwargs
                )

            self.model.to(self.device)
            self.model.eval()

            for param in self.model.parameters():
                param.requires_grad = False

            self._model_loaded = True
            load_time = time.time() - start_time

            model_size = sum(p.numel() for p in self.model.parameters())
            model_mem = sum(p.numel() * p.element_size() for p in self.model.parameters()) / 1024**2
            logger.info(f"Cross-Encoder模型加载完成: "
                       f"参数量={model_size:,}, "
                       f"模型大小={model_mem:.1f}MB, "
                       f"设备={self.device}, "
                       f"加载时间={load_time:.2f}s")

            if self.config.warmup_on_init:
                self._warmup()

            return True

        except Exception as e:
            logger.error(f"加载Cross-Encoder模型失败: {e}")
            return False

    def _warmup(self):
        if self._warmup_done:
            return

        try:
            logger.info("Cross-Encoder模型预热中...")
            dummy_input = self.tokenizer(
                "预热查询", "预热文档内容",
                truncation=True,
                padding=True,
                max_length=self.config.max_length,
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                _ = self.model(**dummy_input)

            if self.device != "cpu":
                torch.cuda.empty_cache()

            self._warmup_done = True
            logger.info("Cross-Encoder模型预热完成")
        except Exception as e:
            logger.warning(f"模型预热失败: {e}")

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        if not scores or not self.config.score_normalize:
            return scores

        import numpy as np
        scores_arr = np.array(scores)

        min_s = scores_arr.min()
        max_s = scores_arr.max()
        score_range = max_s - min_s

        if score_range < 1e-6:
            return [1.0 if s > 0 else 0.0 for s in scores]

        normalized = (scores_arr - min_s) / score_range
        return normalized.tolist()

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """对候选文档列表进行Cross-Encoder精确相关性重排。

        将查询与每个候选文档配对输入模型打分，支持批量推理以提升效率。
        模型加载失败时根据fallback_to_original配置决定是否降级返回原始排序。

        Args:
            query: 用户查询文本
            candidates: 候选文档列表，每个文档需包含content字段
            top_k: 返回的文档数量

        Returns:
            按模型分数降序排列的前top_k个文档，每项额外包含rerank_score和rerank_normalized_score
        """
        if not candidates or len(candidates) <= 1:
            return candidates[:top_k]

        if not self._load_model():
            if self.config.fallback_to_original:
                logger.warning("模型加载失败，返回原始排序结果")
                return candidates[:top_k]
            return []

        try:
            start_time = time.time()

            candidate_texts = []
            valid_candidates = []

            for cand in candidates:
                content = cand.get("content", "")
                if not content or not isinstance(content, str):
                    continue
                candidate_texts.append(content)
                valid_candidates.append(cand)

            if len(valid_candidates) <= 1:
                return valid_candidates[:top_k]

            scores = []
            batch_size = self.config.batch_size

            for i in range(0, len(valid_candidates), batch_size):
                batch_end = min(i + batch_size, len(valid_candidates))
                batch_texts = candidate_texts[i:batch_end]

                inputs = self.tokenizer(
                    [query] * len(batch_texts),
                    batch_texts,
                    truncation=True,
                    padding=True,
                    max_length=self.config.max_length,
                    return_tensors="pt"
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    batch_scores = outputs.logits[:, 0].cpu().tolist()
                    scores.extend(batch_scores)

                if self.device != "cpu" and i + batch_size < len(valid_candidates):
                    torch.cuda.empty_cache()

            normalized_scores = self._normalize_scores(scores)

            sorted_pairs = sorted(
                zip(valid_candidates, scores, normalized_scores),
                key=lambda x: x[1],
                reverse=True
            )

            reranked = []
            for doc, raw_score, norm_score in sorted_pairs[:top_k]:
                doc["rerank_score"] = raw_score
                doc["rerank_normalized_score"] = norm_score
                reranked.append(doc)

            process_time = time.time() - start_time
            logger.info(f"重排完成: {len(candidates)} -> {len(reranked)} 文档, "
                       f"耗时={process_time:.3f}s")

            return reranked

        except Exception as e:
            logger.error(f"重排失败: {e}")
            if self.config.fallback_to_original:
                return candidates[:top_k]
            return []


_reranker_instance: Optional[CrossEncoderReranker] = None


def get_reranker(config: Optional[RerankConfig] = None) -> CrossEncoderReranker:
    """获取Cross-Encoder重排器全局单例。

    首次调用时自动初始化，后续调用返回同一实例。

    Args:
        config: 可选的配置，仅在首次初始化时生效

    Returns:
        CrossEncoderReranker: 全局唯一的重排器实例
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker(config)
    return _reranker_instance


def rerank_documents(query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
    reranker = get_reranker()
    if os.getenv("RERANKER_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return candidates[:top_k]

    return reranker.rerank(query, candidates, top_k)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Cross-Encoder重排器测试（优化版）")
    print("=" * 60)

    test_query = "原神是什么类型的游戏？"
    test_candidates = [
        {"title": "游戏介绍", "content": "原神是一款开放世界动作角色扮演游戏，由米哈游开发。"},
        {"title": "游戏类型", "content": "原神属于ARPG类型，包含探索、战斗、解谜等元素。"},
        {"title": "角色系统", "content": "玩家可以收集和使用各种角色进行战斗。"},
        {"title": "开放世界", "content": "游戏拥有广阔的世界供玩家探索。"},
        {"title": "多人游戏", "content": "原神支持多人联机合作游戏。"}
    ]

    config = RerankConfig(model_name="./bge-reranker-base")
    reranker = CrossEncoderReranker(config)

    print(f"查询: {test_query}")
    print(f"候选文档数量: {len(test_candidates)}")
    print()

    reranked = reranker.rerank(test_query, test_candidates, top_k=3)

    print("重排结果（前3个）:")
    for i, doc in enumerate(reranked, 1):
        title = doc.get("title", "无标题")
        content = doc.get("content", "")[:100]
        raw_score = doc.get("rerank_score", 0)
        norm_score = doc.get("rerank_normalized_score", 0)
        print(f"{i}. {title}: raw={raw_score:.4f}, normalized={norm_score:.4f}")
        print(f"   {content}...")

    print("=" * 60)
    print("测试完成")
