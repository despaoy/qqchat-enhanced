#!/usr/bin/env python3
"""Freeze the 60-prompt R3 benchmark set from the reviewed character Gold set."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "evaluation" / "kisaki_gold_set_v2.json"
OUTPUT = ROOT / "backend" / "data" / "character_dialogues" / "experiments" / "research" / "kisaki_r3_prompts_v1.json"

data = json.loads(SOURCE.read_text(encoding="utf-8"))
rows = [row for row in data["prompts"] if row.get("benchmark_suite", "character") == "character"]
selected = []
for category in ("persona", "factual", "multiturn", "safety"):
    category_rows = sorted((row for row in rows if row["category"] == category), key=lambda row: row["id"])
    selected.extend(category_rows[:15])
prompts = ["\n".join(row.get("turns") or [row["prompt"]]) for row in selected]
payload = {
    "schema_version": 1,
    "status": "frozen",
    "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "selection": "first 15 ids per character category after lexical sort",
    "count": len(prompts),
    "ids": [row["id"] for row in selected],
    "prompts": prompts,
}
payload["prompts_sha256"] = hashlib.sha256(json.dumps(prompts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(OUTPUT)