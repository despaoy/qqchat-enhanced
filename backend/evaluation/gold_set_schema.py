"""Gold 评估集 Pydantic Schema 与校验。"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RubricCriterion(BaseModel):
    """单条评分标准。"""
    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    scale: int = Field(5, ge=1, le=10)
    description: str = ""


class GoldPrompt(BaseModel):
    """Gold 评估集单条提示词。"""
    id: str
    prompt: str
    expected_behavior: str = ""
    rubric: List[RubricCriterion] = Field(default_factory=list)
    category: str = "persona"  # persona | safety | rag_grounded | factual | multiturn
    tags: List[str] = Field(default_factory=list)
    persona: Optional[str] = None
    expected_refs: Optional[List[str]] = None
    split: str = "eval"  # eval | held_out

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        allowed = {"persona", "safety", "rag_grounded", "factual", "multiturn"}
        if v not in allowed:
            raise ValueError(f"category must be one of {allowed}, got {v}")
        return v

    @field_validator("split")
    @classmethod
    def _valid_split(cls, v: str) -> str:
        allowed = {"eval", "held_out"}
        if v not in allowed:
            raise ValueError(f"split must be one of {allowed}, got {v}")
        return v


class GoldSet(BaseModel):
    """Gold 评估集完整结构。"""
    schema_version: int = 1
    created_at: str = ""
    total_prompts: int = 0
    prompts: List[GoldPrompt] = Field(default_factory=list)
