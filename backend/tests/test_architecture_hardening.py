"""Regression coverage for the architecture hardening pass."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest


def test_response_cache_identity_isolated_by_lora_and_config(monkeypatch):
    from api import generate
    from db.models import MessageRequest

    config = {"temperature": 0.7, "maxTokens": 128, "useKnowledgeBase": False}
    monkeypatch.setattr(generate, "db", SimpleNamespace(config=config))
    request = MessageRequest(message="hello", sessionId="session-1", platform="qq")

    base_keys = generate._response_cache_keys(request, "default")
    lora_keys = generate._response_cache_keys(request, "kisaki")
    assert base_keys[:2] != lora_keys[:2]

    config["temperature"] = 0.2
    changed_keys = generate._response_cache_keys(request, "default")
    assert base_keys[:2] != changed_keys[:2]


@pytest.mark.asyncio
async def test_raise_degradation_never_fabricates_a_model_success():
    from infra.circuit_breaker import (
        CircuitBreaker,
        CircuitOpenError,
        DegradationMode,
    )

    breaker = CircuitBreaker(
        name="model",
        failure_threshold=1,
        recovery_timeout=60,
        degradation_mode=DegradationMode.RAISE,
    )

    async def fail():
        raise RuntimeError("model down")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    with pytest.raises(CircuitOpenError):
        await breaker.call(fail)


def test_rag_confidence_uses_absolute_score_not_rank_normalization():
    from knowledge.rag_helper import RAGHelper

    results = [
        {"score": 0.12, "normalized_score": 1.0},
        {"score": 0.08, "normalized_score": 0.5},
    ]
    confidence = RAGHelper.compute_confidence(object.__new__(RAGHelper), results)
    assert 0.0 < confidence < 0.3


def test_rag_citations_keep_knowledge_base_filters():
    from knowledge.rag_helper import RAGHelper

    helper = object.__new__(RAGHelper)
    captured = {}

    def retrieve(query, top_k=None, filters=None):
        captured["filters"] = filters
        return [{"title": "doc", "content": "evidence", "score": 0.9}]

    helper.retrieve_context = retrieve
    result = helper.retrieve_with_citations(
        "question", top_k=1, filters={"knowledge_base_id": 7}
    )
    assert captured["filters"] == {"knowledge_base_id": 7}
    assert result["abstained"] is False


def test_experiment_dataclasses_are_json_ready():
    from api.experiments import _serialize_results

    @dataclass
    class Result:
        variant: str
        score: float

    assert _serialize_results([Result("hybrid", 0.9)]) == [
        {"variant": "hybrid", "score": 0.9}
    ]


def test_training_truncation_preserves_supervised_response_tokens():
    from training.trainer import LoRATrainer

    trainer = object.__new__(LoRATrainer)
    trainer.config = SimpleNamespace(max_seq_length=5, truncation_direction="left")
    full_ids, prompt_len = trainer._truncate_preserving_response(
        [1, 2, 3, 4, 5, 90, 91, 92], [1, 2, 3, 4, 5]
    )
    labels = [-100] * prompt_len + full_ids[prompt_len:]

    assert full_ids == [4, 5, 90, 91, 92]
    assert labels[-3:] == [90, 91, 92]