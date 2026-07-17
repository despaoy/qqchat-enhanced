#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/szw/lhm2/qqchat-enhanced}"
PYTHON_BIN="${PYTHON_BIN:-/home/szw/lhm2/envs/qqchat-gpu/bin/python}"
VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8001}"
RESULT_DIR="${RESULT_DIR:-/home/szw/lhm2/runtime/results/character_eval}"
GPU_INDEX="${GPU_INDEX:-1}"
MAX_TOKENS="${MAX_TOKENS:-256}"

cd "$PROJECT_ROOT"
mkdir -p "$RESULT_DIR"

curl -fsS --max-time 10 "$VLLM_BASE_URL/v1/models" >/dev/null

run_eval() {
  local dataset="$1"
  local documents="$2"
  local model="$3"
  local output="$4"

  "$PYTHON_BIN" backend/evaluation/character_benchmark.py \
    --dataset "$dataset" \
    --rag-documents "$documents" \
    --model "$model" \
    --output "$RESULT_DIR/$output" \
    --base-url "$VLLM_BASE_URL" \
    --max-tokens "$MAX_TOKENS" \
    --timeout 120 \
    --gpu "$GPU_INDEX"
}

run_eval \
  backend/data/character_dialogues/experiments/shenbai_mizunamo_eval.json \
  backend/data/character_dialogues/experiments/shenbai_mizunamo_rag_documents.json \
  qwen2.5-7b-instruct-awq \
  shenbai_mizunamo_base_awq.json

run_eval \
  backend/data/character_dialogues/experiments/shenbai_mizunamo_eval.json \
  backend/data/character_dialogues/experiments/shenbai_mizunamo_rag_documents.json \
  minamo \
  shenbai_mizunamo_lora.json

run_eval \
  backend/data/character_dialogues/experiments/tsukiyashiro_kisaki_eval.json \
  backend/data/character_dialogues/experiments/tsukiyashiro_kisaki_rag_documents.json \
  qwen2.5-7b-instruct-awq \
  tsukiyashiro_kisaki_base_awq.json

"$PYTHON_BIN" scripts/build_blind_ab_review.py \
  --a "$RESULT_DIR/shenbai_mizunamo_base_awq.json" \
  --b "$RESULT_DIR/shenbai_mizunamo_lora.json" \
  --output-dir "$RESULT_DIR/shenbai_mizunamo_blind_ab" \
  --seed 42

echo "Character benchmark completed: $RESULT_DIR"
