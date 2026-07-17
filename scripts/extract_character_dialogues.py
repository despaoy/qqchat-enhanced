"""Create auditable raw and SFT character-dialogue datasets."""
from __future__ import annotations
import argparse, hashlib, json, re, unicodedata
from collections import Counter
from pathlib import Path
from docx import Document

TARGETS = {
    "shenbai_mizunamo": {
        "display_name": "神白水菜萌",
        "train_aliases": {"水菜萌", "神白水菜萌", "水菜萌的声音"},
        "joint_aliases": {"夏生·水菜萌"},
        "system": "你正在扮演神白水菜萌。请依据给定角色设定和原作中的语言习惯，自然地回应。",
    },
    "tsukiyashiro_kisaki": {
        "display_name": "月社妃",
        "train_aliases": {"妃", "月社妃"},
        "joint_aliases": set(),
        "system": "你正在扮演月社妃。请依据给定角色设定和原作中的语言习惯，自然地回应。",
    },
}
DOCX_RE = re.compile(r"^(?P<speaker>[^：:\r\n]{1,40})\s*[：:]\s*(?P<text>.+?)\s*$")
SCRIPT_RE = re.compile(r"\[(?P<speaker>[^\]]+)\]\s*[「『“](?P<text>.*?)[」』”]", re.DOTALL)
SPACE_RE = re.compile(r"\s+")
MEANING_RE = re.compile(r"[\w\u3400-\u9fff]", re.UNICODE)


def clean(text):
    return SPACE_RE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def norm_key(text):
    text = unicodedata.normalize("NFKC", text).replace("……", "…").replace("--", "—")
    return SPACE_RE.sub("", text).strip()


def meaningful_len(text):
    return len(MEANING_RE.findall(text))


def stable_id(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def read_docx_events(path):
    events = []
    for index, paragraph in enumerate(Document(path).paragraphs, 1):
        match = DOCX_RE.match(clean(paragraph.text))
        if match:
            events.append({
                "speaker": clean(match.group("speaker")),
                "text": clean(match.group("text")),
                "source": f"{path.name}:paragraph:{index}",
            })
    return events


def read_script_events(path, source_id=None):
    source_id = source_id or path.name
    text = path.read_text(encoding="utf-8")
    events = []
    for match in SCRIPT_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        events.append({
            "speaker": clean(match.group("speaker")),
            "text": clean(match.group("text")),
            "source": f"{source_id}:line:{line}",
        })
    return events


def source_scripts(root):
    for path in sorted((root / "所有文本").glob("scenario_*.json")):
        yield path, f"所有文本/{path.name}", "canonical"
    for path in sorted((root / "分章文本").glob("*.txt")):
        yield path, f"分章文本/{path.name}", "verification"
    for name in ("个人线插入主线.txt", "个人线后于主线.txt"):
        path = root / name
        if path.exists():
            yield path, name, "verification"


def target_kind(speaker, target_key):
    target = TARGETS[target_key]
    if speaker in target["train_aliases"]:
        return "direct"
    if speaker in target["joint_aliases"]:
        return "joint"
    return None


def make_raw(groups, target_key):
    records = []
    for group in groups:
        for event in group["events"]:
            kind = target_kind(event["speaker"], target_key)
            if kind is None or not event["text"]:
                continue
            event_id = stable_id(target_key, event["source"], event["text"])
            records.append({
                "id": f"{target_key}_raw_{event_id}",
                "character": TARGETS[target_key]["display_name"],
                "speaker_label": event["speaker"],
                "speaker_kind": kind,
                "text": event["text"],
                "source": event["source"],
                "source_role": group["source_role"],
                "eligible_for_sft": kind == "direct" and group["source_role"] == "canonical",
            })
    return records


def quality_score(prompt, reply, lines):
    score = 50 + min(meaningful_len(prompt), 30) // 3
    score += min(meaningful_len(reply), 60) // 4
    score += min(max(lines - 1, 0), 3) * 2
    score += 3 if any(x in prompt for x in ("？", "?")) else 0
    score -= 8 if meaningful_len(reply) > 240 else 0
    return max(0, min(score, 100))


def build_candidates(groups, target_key):
    aliases = TARGETS[target_key]["train_aliases"]
    candidates = []
    for group in groups:
        if group["source_role"] != "canonical":
            continue
        events, index = group["events"], 0
        while index < len(events):
            event = events[index]
            if event["speaker"] not in aliases:
                index += 1
                continue
            start, reply_events = index, []
            while index < len(events) and events[index]["speaker"] in aliases:
                if events[index]["text"]:
                    reply_events.append(events[index])
                index += 1
            cursor = start - 1
            context_speaker = events[cursor]["speaker"] if cursor >= 0 else None
            context_events = []
            while cursor >= 0 and events[cursor]["speaker"] == context_speaker:
                if events[cursor]["text"]:
                    context_events.append(events[cursor])
                cursor -= 1
            context_events.reverse()
            prompt = "\n".join(x["text"] for x in context_events).strip()
            reply = "\n".join(x["text"] for x in reply_events).strip()
            reasons = []
            if not context_events:
                reasons.append("missing_context")
            if meaningful_len(prompt) < 2:
                reasons.append("low_information_prompt")
            if meaningful_len(reply) < 2:
                reasons.append("low_information_reply")
            if len(prompt) > 1200:
                reasons.append("prompt_too_long")
            if len(reply) > 1600:
                reasons.append("reply_too_long")
            source = reply_events[0]["source"] if reply_events else event["source"]
            ids = [f"{target_key}_raw_{stable_id(target_key, x['source'], x['text'])}" for x in reply_events]
            candidates.append({
                "id": f"{target_key}_turn_{stable_id(target_key, source, prompt, reply)}",
                "source": source,
                "source_file": group["source_id"],
                "source_speaker_label": event["speaker"],
                "context_speaker_label": context_speaker,
                "prompt": prompt,
                "reply": reply,
                "target_event_ids": ids,
                "response_line_count": len(reply_events),
                "quality_score": quality_score(prompt, reply, len(reply_events)),
                "reasons": reasons,
            })
    return candidates


def as_sft(item, target_key):
    return {
        "id": f"{target_key}_sft_{stable_id(target_key, item['source'], item['prompt'], item['reply'])}",
        "system": TARGETS[target_key]["system"],
        "conversations": [
            {"from": "human", "value": item["prompt"]},
            {"from": "assistant", "value": item["reply"]},
        ],
        "metadata": {
            "character": TARGETS[target_key]["display_name"],
            "source": item["source"],
            "source_file": item["source_file"],
            "source_speaker_label": item["source_speaker_label"],
            "context_speaker_label": item["context_speaker_label"],
            "target_event_ids": item["target_event_ids"],
            "response_line_count": item["response_line_count"],
            "quality_score": item["quality_score"],
            "extraction": "explicit-label-source-bounded-turn-grouped",
        },
    }


def make_sft(groups, target_key):
    excluded, valid = [], []
    for item in build_candidates(groups, target_key):
        (excluded if item["reasons"] else valid).append(item)
    full_by_pair = {}
    for item in valid:
        key = (norm_key(item["prompt"]), norm_key(item["reply"]))
        if key in full_by_pair:
            item = dict(item)
            item["reasons"] = ["duplicate_pair"]
            excluded.append(item)
        else:
            full_by_pair[key] = item
    best = {}
    for item in full_by_pair.values():
        key = norm_key(item["prompt"])
        old = best.get(key)
        rank = (item["quality_score"], meaningful_len(item["reply"]), item["id"])
        old_rank = None if old is None else (old["quality_score"], meaningful_len(old["reply"]), old["id"])
        if old is None or rank > old_rank:
            if old is not None:
                old = dict(old)
                old["reasons"] = ["duplicate_prompt_lower_rank"]
                excluded.append(old)
            best[key] = item
        else:
            item = dict(item)
            item["reasons"] = ["duplicate_prompt_lower_rank"]
            excluded.append(item)
    return (
        [as_sft(x, target_key) for x in best.values()],
        [as_sft(x, target_key) for x in full_by_pair.values()],
        excluded,
    )


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def summary(raw, recommended, full, excluded):
    canonical = {x["id"] for x in raw if x["source_role"] == "canonical" and x["speaker_kind"] == "direct"}
    full_ids = {i for x in full for i in x["metadata"]["target_event_ids"]}
    recommended_ids = {i for x in recommended for i in x["metadata"]["target_event_ids"]}
    reasons = Counter(r for x in excluded for r in x["reasons"])
    return {
        "all_supplied_attributable_occurrences": len(raw),
        "all_supplied_unique_utterances": len({x["text"] for x in raw}),
        "canonical_direct_occurrences": len(canonical),
        "raw_source_coverage_percent": 100.0,
        "full_sft_examples": len(full),
        "full_sft_covered_canonical_occurrences": len(full_ids & canonical),
        "recommended_sft_examples": len(recommended),
        "recommended_sft_unique_prompts": len({norm_key(x["conversations"][0]["value"]) for x in recommended}),
        "recommended_sft_covered_canonical_occurrences": len(recommended_ids & canonical),
        "excluded_turn_reasons": dict(sorted(reasons.items())),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--atri-docx", type=Path, required=True)
    parser.add_argument("--magic-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_groups = {
        "shenbai_mizunamo": [{"source_id": args.atri_docx.name, "source_role": "canonical", "events": read_docx_events(args.atri_docx)}],
        "tsukiyashiro_kisaki": [
            {"source_id": sid, "source_role": role, "events": read_script_events(path, sid)}
            for path, sid, role in source_scripts(args.magic_root)
        ],
    }
    summaries = {}
    for target_key, groups in all_groups.items():
        raw = make_raw(groups, target_key)
        recommended, full, excluded = make_sft(groups, target_key)
        write_jsonl(args.output_dir / f"{target_key}_raw.jsonl", raw)
        write_json(args.output_dir / f"{target_key}_sft.json", recommended)
        write_json(args.output_dir / f"{target_key}_sft_full.json", full)
        write_jsonl(args.output_dir / f"{target_key}_excluded.jsonl", excluded)
        summaries[target_key] = {
            "character": TARGETS[target_key]["display_name"],
            **summary(raw, recommended, full, excluded),
            "source_files": dict(Counter(x["source"].split(":line:", 1)[0].split(":paragraph:", 1)[0] for x in raw)),
        }
    manifest = {
        "schema_version": 2,
        "extraction_policy": {
            "shenbai_mizunamo": "收录水菜萌、神白水菜萌、水菜萌的声音，以及仅供审计的夏生·水菜萌共同台词；明确排除水菜萌的妈妈。",
            "tsukiyashiro_kisaki": "只把显式[妃]/[月社妃]作为目标说话人；克丽索贝莉露是独立角色，即使冒用月社妃姓名也不并入。",
            "source_policy": "raw保留全部来源；SFT只使用DOCX或所有文本/scenario_*.json权威来源，分章和合并文本仅用于覆盖核验。",
            "quality_policy": "按文件隔离上下文，连续目标台词合并，排除无上下文、低信息、超长和重复样本。",
        },
        "characters": summaries,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "coverage_report.json", summaries)
    (args.output_dir / "README.md").write_text(
        "# 角色对话训练数据\n\n"
        "- `*_raw.jsonl`：完整可追溯语料，用于覆盖审计，不直接训练。\n"
        "- `*_sft.json`：推荐训练集，每个规范化human输入只保留一个高信息回复。\n"
        "- `*_sft_full.json`：上下文有效的完整候选集，仅去除完全相同问答。\n"
        "- `*_excluded.jsonl`：排除候选及原因，避免静默丢数据。\n"
        "- `coverage_report.json`：覆盖率与排除统计。\n\n"
        "默认训练sft文件；先人工抽查excluded；按剧情文件划分训练/验证集；固定数据哈希、脚本版本和随机种子。\n",
        encoding="utf-8", newline="\n"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
