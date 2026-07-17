#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/szw/lhm2
PROJECT=$ROOT/qqchat-enhanced
PYTHON=$ROOT/envs/qqchat-gpu/bin/python
CONFIG=$PROJECT/backend/data/character_dialogues/experiments/configs/tsukiyashiro_kisaki_lora_r32.json
PIDFILE=$ROOT/runtime/kisaki_lora_r32.pid
LOGFILE=$ROOT/runtime/logs/kisaki_lora_r32.log

mkdir -p "$ROOT/runtime/logs" "$ROOT/runtime/loras/kisaki"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "training_already_running pid=$(cat "$PIDFILE")"
  exit 0
fi

if pgrep -u "$(id -u)" -f 'vllm serve.*Qwen2.5-7B-Instruct-AWQ' >/dev/null; then
  echo "refusing_to_start: vLLM is still using this user's GPU" >&2
  exit 2
fi

cd "$PROJECT/backend"
nohup env CUDA_VISIBLE_DEVICES=1 PYTHONUNBUFFERED=1 \
  "$PYTHON" -m training.trainer --config "$CONFIG" \
  >"$LOGFILE" 2>&1 </dev/null &
TRAIN_PID=$!
echo "$TRAIN_PID" >"$PIDFILE"
echo "training_started pid=$TRAIN_PID log=$LOGFILE"
