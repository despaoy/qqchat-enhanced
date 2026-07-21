"""Build the reviewable 60-question Kisaki RAG v2 candidate set."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "backend" / "data" / "character_dialogues" / "experiments" / "research"
SOURCE = RESEARCH / "character_rag_retrieval_eval.json"
DOCUMENTS = RESEARCH / "character_rag_seed_documents.json"
OUTPUT = RESEARCH / "kisaki_rag_eval_v2_candidates.json"

NEGATIVES = [
    "月社妃最喜欢的现实品牌是什么？",
    "月社妃的手机号码是多少？",
    "月社妃在现实世界的家庭住址在哪里？",
    "月社妃最常使用哪一种社交软件？",
    "月社妃的身份证号码是什么？",
    "月社妃具体出生于哪家医院？",
    "月社妃最喜欢哪支现实乐队？",
    "月社妃平时使用什么型号的电脑？",
    "月社妃的银行账户信息是什么？",
    "月社妃最喜欢哪一家现实餐厅？",
    "月社妃在大学选择了什么专业？",
    "月社妃现实中的电子邮箱是什么？",
    "月社妃参加过哪些现实世界比赛？",
    "月社妃最喜欢的现代电子游戏是什么？",
    "月社妃现在居住在哪座现实城市？",
]


def canonical_hash(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    documents = json.loads(DOCUMENTS.read_text(encoding="utf-8"))
    singles = []
    for item in source["questions"]:
        row = dict(item)
        row["question_type"] = "single_evidence"
        row["expected_action"] = "answer"
        singles.append(row)
    if len(singles) != 30:
        raise SystemExit(f"expected 30 source questions, found {len(singles)}")

    multi = []
    for index in range(15):
        left, right = singles[index * 2], singles[index * 2 + 1]
        multi.append({
            "id": f"kisaki_rag_v2_multi_{index + 1:03d}",
            "question": f"请结合两个片段分别回应：一、{left['question']} 二、{right['question']}",
            "expected_doc_ids": left["expected_doc_ids"] + right["expected_doc_ids"],
            "gold_answer": f"{left['gold_answer']}\n{right['gold_answer']}",
            "persona": "tsukiyashiro_kisaki",
            "question_type": "multi_evidence",
            "expected_action": "answer",
            "review_status": "pending_human_review",
        })
    negatives = [
        {
            "id": f"kisaki_rag_v2_unanswerable_{index + 1:03d}",
            "question": question,
            "expected_doc_ids": [],
            "gold_answer": "",
            "persona": "tsukiyashiro_kisaki",
            "question_type": "unanswerable",
            "expected_action": "abstain",
            "review_status": "pending_human_review",
        }
        for index, question in enumerate(NEGATIVES)
    ]
    questions = singles + multi + negatives
    payload = {
        "schema_version": 2,
        "status": "pending_human_review",
        "formal_use_allowed": False,
        "description": "Held-out RAG v2 candidates. Never use for SFT or formal evaluation before review and freeze.",
        "source_documents_sha256": canonical_hash(documents["documents"]),
        "category_counts": {"single_evidence": 30, "multi_evidence": 15, "unanswerable": 15},
        "questions_sha256": canonical_hash(questions),
        "questions": questions,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "count": len(questions), "sha256": payload["questions_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
