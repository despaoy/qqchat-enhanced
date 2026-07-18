"""纠正性 RAG - 低置信度时重写查询并重试检索，仍低则弃答。

遵循路线图 guardrail：
- 重试次数限制为 1 次（max_retries=1）
- 由环境变量 CORRECTIVE_RAG_ENABLED 控制（默认 false，生产/实验分离）
- 复用 RAGHelper 的 retrieve_with_citations / compute_confidence / should_abstain
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 简易中文停用词表（用于查询重写时去停用词）
_STOPWORDS = {
    "的", "了", "是", "在", "我", "你", "他", "她", "它", "们", "这", "那",
    "怎么", "什么", "为什么", "哪里", "哪个", "请问", "一下", "可能", "应该",
    "the", "a", "an", "is", "are", "was", "were", "what", "how", "why",
}


def _tokenize(text: str) -> List[str]:
    """简易分词：中文按字符，英文按空格。"""
    return re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', text)


class CorrectiveRAG:
    """纠正性 RAG：retrieve → confidence check → reformulate → re-retrieve → abstain。

    流程：
    1. 首次检索 retrieve_with_citations
    2. 若置信度低于阈值，从 top 结果提取关键词重写查询
    3. 用重写查询重新检索
    4. 若仍低于阈值，弃答
    """

    def __init__(self, rag_helper, threshold: float = 0.3, max_retries: int = 1):
        self.rag_helper = rag_helper
        self.threshold = threshold
        self.max_retries = max_retries

    def reformulate_query(self, query: str, top_results: List[Dict[str, Any]]) -> str:
        """从 top 结果提取关键词，追加到原查询形成重写查询。"""
        keywords: List[str] = []
        for result in top_results[:3]:
            content = result.get("content", "")
            title = result.get("title", "")
            text = f"{title} {content}"
            tokens = _tokenize(text)
            for tok in tokens:
                if len(tok) > 1 and tok not in keywords and tok not in _STOPWORDS:
                    keywords.append(tok)
            if len(keywords) >= 8:
                break

        if not keywords:
            return query

        # 追加最多 5 个关键词到原查询
        extra = " ".join(keywords[:5])
        return f"{query} {extra}"

    def retrieve_with_correction(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """纠正性检索：首次检索 → 低置信度则重写重试 → 仍低则弃答。

        Returns:
            {results, citations, confidence, abstained, reformulated,
             original_query, reformulated_query}
        """
        # 首次检索
        first = self.rag_helper.retrieve_with_citations(
            query, top_k=top_k, threshold=self.threshold, filters=filters
        )
        confidence = first.get("confidence", 0.0)

        if not first.get("abstained", False):
            # 置信度足够，直接返回
            return {
                **first,
                "reformulated": False,
                "original_query": query,
                "reformulated_query": None,
            }

        # 低置信度，尝试重写查询
        logger.info(f"纠正性RAG: 首次置信度 {confidence} < {self.threshold}，尝试查询重写")
        reformulated_query = self.reformulate_query(query, first.get("results", []))
        logger.info(f"纠正性RAG: 重写查询 -> {reformulated_query}")

        second = self.rag_helper.retrieve_with_citations(
            reformulated_query, top_k=top_k, threshold=self.threshold, filters=filters
        )
        second_confidence = second.get("confidence", 0.0)

        if not second.get("abstained", False):
            logger.info(f"纠正性RAG: 重写后置信度 {second_confidence} >= {self.threshold}，成功")
            return {
                **second,
                "reformulated": True,
                "original_query": query,
                "reformulated_query": reformulated_query,
            }

        # 仍低置信度，弃答
        logger.info(f"纠正性RAG: 重写后置信度 {second_confidence} 仍低，弃答")
        return {
            "results": [],
            "citations": [],
            "confidence": second_confidence,
            "abstained": True,
            "reformulated": True,
            "original_query": query,
            "reformulated_query": reformulated_query,
        }


_corrective_rag: Optional[CorrectiveRAG] = None


def get_corrective_rag(threshold: float = 0.3) -> CorrectiveRAG:
    """获取 CorrectiveRAG 单例。"""
    global _corrective_rag
    if _corrective_rag is None:
        from .rag_helper import get_rag_helper
        _corrective_rag = CorrectiveRAG(get_rag_helper(), threshold=threshold)
    return _corrective_rag
