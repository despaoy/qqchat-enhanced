"""生成评估指标 - Distinct-N / 重复率 / 平均长度。"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Dict, Any, Callable, Optional


def _ngrams(tokens: List[str], n: int) -> List[tuple]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _tokenize(text: str) -> List[str]:
    """简易中文分词：按字符切分 + 英文按空格。"""
    tokens = []
    for chunk in re.findall(r'[\u4e00-\u9fff]|[a-zA-Z0-9]+', text):
        tokens.append(chunk)
    return tokens


class GenerationMetrics:
    """生成质量评估指标。"""

    def distinct_n(self, texts: List[str], n: int = 1) -> float:
        """Distinct-N：唯一 n-gram 数 / 总 n-gram 数。"""
        all_ngrams: List[tuple] = []
        for text in texts:
            all_ngrams.extend(_ngrams(_tokenize(text), n))
        if not all_ngrams:
            return 0.0
        unique = len(set(all_ngrams))
        return round(unique / len(all_ngrams), 4)

    def repetition_rate(self, text: str) -> float:
        """重复率：重复 4-gram 比例。"""
        tokens = _tokenize(text)
        ngrams = _ngrams(tokens, 4)
        if not ngrams:
            return 0.0
        counts = Counter(ngrams)
        repeated = sum(c - 1 for c in counts.values() if c > 1)
        return round(repeated / len(ngrams), 4)

    def avg_length(self, texts: List[str]) -> float:
        """平均生成长度（字符数）。"""
        if not texts:
            return 0.0
        return round(sum(len(t) for t in texts) / len(texts), 2)

    def max_repetition_ratio(self, text: str) -> float:
        """最大连续重复比例：检测退化重复。"""
        tokens = _tokenize(text)
        if len(tokens) < 4:
            return 0.0
        max_run = 1
        current_run = 1
        for i in range(1, len(tokens)):
            if tokens[i] == tokens[i - 1]:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
        return round(max_run / len(tokens), 4)

    def evaluate(self, prompts: List[str], generate_fn: Callable[[str], str],
                 max_tokens: int = 256) -> Dict[str, Any]:
        """对 gold set 的 prompt 批量生成，计算所有指标。

        Args:
            prompts: 提示词列表
            generate_fn: 生成函数，签名 (prompt: str) -> str
            max_tokens: 最大生成 token 数（传递给 generate_fn 的参考值）

        Returns:
            {"distinct_1": float, "distinct_2": float,
             "repetition_rate": float, "avg_length": float, "samples": [...]}
        """
        samples: List[Dict[str, str]] = []
        responses: List[str] = []
        for prompt in prompts:
            try:
                resp = generate_fn(prompt)
            except Exception as e:
                resp = f"[GENERATION_ERROR] {e}"
            responses.append(resp)
            samples.append({"prompt": prompt, "response": resp})

        return {
            "total_prompts": len(prompts),
            "distinct_1": self.distinct_n(responses, 1),
            "distinct_2": self.distinct_n(responses, 2),
            "avg_repetition_rate": round(
                sum(self.repetition_rate(r) for r in responses) / max(len(responses), 1), 4
            ),
            "avg_length": self.avg_length(responses),
            "max_repetition_ratio": round(
                sum(self.max_repetition_ratio(r) for r in responses) / max(len(responses), 1), 4
            ),
            "samples": samples,
        }

    def evaluate_mock(self, prompts: List[str]) -> Dict[str, Any]:
        """Mock 模式：用固定文本验证脚本逻辑。"""
        mock_responses = [
            f"这是对「{p[:20]}」的模拟回复。保持角色风格很重要。" for p in prompts
        ]
        return {
            "total_prompts": len(prompts),
            "distinct_1": self.distinct_n(mock_responses, 1),
            "distinct_2": self.distinct_n(mock_responses, 2),
            "avg_repetition_rate": 0.0,
            "avg_length": self.avg_length(mock_responses),
            "max_repetition_ratio": 0.0,
            "mock": True,
            "samples": [{"prompt": p, "response": r} for p, r in zip(prompts, mock_responses)],
        }
