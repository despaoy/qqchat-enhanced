"""数据集卡片 Schema - 数据来源/许可证/语言/规模/风险/预期用途。"""
from __future__ import annotations

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DatasetCard(BaseModel):
    """数据集卡片：记录数据集的来源、许可、规模、风险与预期用途。"""
    schema_version: int = 1
    name: str
    source: str = ""
    license: str = "unknown"
    language: List[str] = Field(default_factory=lambda: ["zh-CN"])
    size: int = 0
    persona: Optional[str] = None
    domain: str = ""
    risks: List[str] = Field(default_factory=list)
    intended_use: str = ""
    preprocessing: List[str] = Field(default_factory=list)
    train_val_test_split: Dict[str, int] = Field(default_factory=dict)
    content_hash: str = ""
    created_at: str = ""
    tags: List[str] = Field(default_factory=list)
