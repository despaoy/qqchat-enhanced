#!/usr/bin/env python3
"""Freeze the human-reviewed R2 dataset without mutating its review source."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite frozen dataset: {args.output}")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    errors = []
    if len(questions) != 60:
        errors.append(f"expected 60 questions, found {len(questions)}")
    unapproved = [row.get("id") for row in questions if row.get("review_status") != "approved"]
    if unapproved:
        errors.append(f"human approval missing for {len(unapproved)} questions")
    ids = [row.get("id") for row in questions]
    if len(ids) != len(set(ids)):
        errors.append("duplicate question ids")
    if errors:
        print(json.dumps({"status": "blocked", "errors": errors, "unapproved_ids": unapproved}, ensure_ascii=False, indent=2))
        return 2
    frozen = dict(data)
    frozen.update({"status": "frozen", "formal_use_allowed": True, "frozen_at": datetime.now(timezone.utc).isoformat(), "questions_sha256": canonical_hash(questions)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())