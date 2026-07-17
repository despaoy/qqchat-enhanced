#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/szw/lhm2
MODEL=$ROOT/runtime/models/Qwen3-8B-Instruct-AWQ
ENV_DIR=$ROOT/envs/qqchat-gpu-qwen3

# ⚠️ LoRA 适配器（hutao/minamo/kisaki）基于 Qwen2.5-7B-Instruct 训练，
#    与 Qwen3-8B 架构不兼容，已暂时禁用。旧文件保留在 $ROOT/runtime/loras/backup_qwen25/。
#    如需启用角色 LoRA，请在 Qwen3-8B-Instruct 上重新训练。
# HUTAO=$ROOT/runtime/loras/hutao/hutao_lora_7b/final
# MINAMO=$ROOT/runtime/loras/minamo/minamo_lora
# KISAKI=$ROOT/runtime/loras/kisaki/lora_r32/final
# LORA_MODULES=(hutao="$HUTAO" minamo="$MINAMO")
# MAX_LORAS=2
# if [[ -f "$KISAKI/adapter_config.json" ]]; then
#   LORA_MODULES+=(kisaki="$KISAKI")
#   MAX_LORAS=3
# fi

# 新环境优先（qqchat-gpu-qwen3），回退到旧环境
if [[ -x "$ENV_DIR/bin/vllm" ]]; then
    VLLM_BIN="$ENV_DIR/bin/vllm"
else
    VLLM_BIN="$ROOT/envs/qqchat-gpu/bin/vllm"
fi

exec env CUDA_VISIBLE_DEVICES=1 "$VLLM_BIN" serve "$MODEL" \
  --served-model-name qwen3-8b-instruct-awq \
  --host 127.0.0.1 --port 8001 \
  --gpu-memory-utilization 0.85 --max-model-len 8192 \
  --quantization awq_marlin \
  --guided-decoding-backend lm-format-enforcer \
  --enforce-eager
  # LoRA 暂时禁用（见上方说明）
  # --chat-template "$HUTAO/chat_template.jinja" \
  # --enable-lora --max-loras "$MAX_LORAS" --max-lora-rank 64 \
  # --lora-modules "${LORA_MODULES[@]}"
