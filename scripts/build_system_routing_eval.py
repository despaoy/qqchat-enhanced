#!/usr/bin/env python3
"""Build deterministic S1 routing evaluation prompts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "data" / "character_dialogues" / "experiments" / "research" / "system_routing_eval_v1.json"
PERSONAS = {
    "kisaki": ["月社妃", "琉璃", "夜子", "彼方", "理央"],
    "minamo": ["神白水菜萌", "水菜萌", "Minamo", "ATRI"],
    "hutao": ["胡桃", "往生堂", "堂主", "蝶引来生"],
}
TEMPLATES = [
    "请让{keyword}回应这个场景：今天适合读书吗？",
    "我想和{keyword}聊聊刚才发生的事。",
    "切换到{keyword}的角色，再回答我的问题。",
    "如果是{keyword}，会怎样看待这个选择？",
]
rows = []
for persona, keywords in PERSONAS.items():
    for index in range(20):
        keyword = keywords[index % len(keywords)]
        rows.append({"id": f"s1-{persona}-{index+1:02d}", "query": TEMPLATES[index % len(TEMPLATES)].format(keyword=keyword), "expected_target": "persona_adapter", "expected_adapter": persona, "external_demo_only": persona != "kisaki"})
for index in range(20):
    rows.append({"id": f"s1-rag-{index+1:02d}", "query": f"请检索知识库后说明设定条目 {index+1} 的依据。", "expected_target": "rag_required", "expected_adapter": "default", "intent_result": [True, 0.95, "kisaki"]})
payload = {"schema_version": 1, "status": "frozen", "count": len(rows), "selection": "deterministic routing contract prompts; not a generation-quality set", "cases": rows}
payload["cases_sha256"] = hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(OUT)