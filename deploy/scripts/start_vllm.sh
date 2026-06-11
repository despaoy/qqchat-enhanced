#!/bin/bash
# ============================================
# vLLM 启动脚本
# 用法: ./start_vllm.sh <GPU_ID> <PORT> <MODEL_PATH> [LORA_PATH]
# 示例: ./start_vllm.sh 0 8001 /models/Qwen2.5-7B-Instruct /loras
# ============================================

set -euo pipefail

# ------------------------------------------
# 参数解析
# ------------------------------------------
GPU_ID="${1:?错误: 缺少 GPU ID 参数}"
PORT="${2:?错误: 缺少端口参数}"
MODEL_PATH="${3:?错误: 缺少模型路径参数}"
LORA_PATH="${4:-/loras}"

# ------------------------------------------
# 颜色输出
# ------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ------------------------------------------
# 检查 GPU 可用性
# ------------------------------------------
check_gpu() {
    log_info "检查 GPU ${GPU_ID} 可用性..."

    if ! command -v nvidia-smi &>/dev/null; then
        log_error "nvidia-smi 未找到，请确认 NVIDIA 驱动已安装"
        exit 1
    fi

    local gpu_count
    gpu_count=$(nvidia-smi --list-gpus 2>/dev/null | wc -l)

    if [[ ${GPU_ID} -ge ${gpu_count} ]]; then
        log_error "GPU ID ${GPU_ID} 不存在，系统共有 ${gpu_count} 块 GPU"
        exit 1
    fi

    # 检查 GPU 显存
    local gpu_mem
    gpu_mem=$(nvidia-smi -i "${GPU_ID}" --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')

    if [[ -n "${gpu_mem}" && ${gpu_mem} -lt 6000 ]]; then
        log_warn "GPU ${GPU_ID} 可用显存仅 ${gpu_mem}MB，可能不足以运行 7B 模型"
    else
        log_info "GPU ${GPU_ID} 可用显存: ${gpu_mem}MB"
    fi

    log_info "GPU ${GPU_ID} 检查通过"
}

# ------------------------------------------
# 检查模型文件
# ------------------------------------------
check_model() {
    log_info "检查模型文件: ${MODEL_PATH}"

    if [[ ! -d "${MODEL_PATH}" ]]; then
        log_error "模型目录不存在: ${MODEL_PATH}"
        exit 1
    fi

    # 检查关键文件
    local required_files=("config.json" "tokenizer.json")
    for f in "${required_files[@]}"; do
        if [[ ! -f "${MODEL_PATH}/${f}" ]]; then
            log_error "模型缺少必要文件: ${MODEL_PATH}/${f}"
            exit 1
        fi
    done

    # 检查模型权重文件（safetensors 或 bin）
    local has_weights=false
    if ls "${MODEL_PATH}"/*.safetensors &>/dev/null || ls "${MODEL_PATH}"/model*.bin &>/dev/null; then
        has_weights=true
    fi

    if [[ "${has_weights}" == false ]]; then
        log_error "模型目录中未找到权重文件（.safetensors 或 .bin）"
        exit 1
    fi

    log_info "模型文件检查通过"
}

# ------------------------------------------
# 启动 vLLM 服务
# ------------------------------------------
start_vllm() {
    log_info "启动 vLLM 服务..."
    log_info "  GPU: ${GPU_ID}"
    log_info "  端口: ${PORT}"
    log_info "  模型: ${MODEL_PATH}"
    log_info "  LoRA: ${LORA_PATH}"

    export CUDA_VISIBLE_DEVICES="${GPU_ID}"

    # 启动 vLLM OpenAI 兼容 API 服务器
    python -m vllm.entrypoints.openai.api_server \
        --model "${MODEL_PATH}" \
        --enable-lora \
        --max-loras 4 \
        --max-lora-rank 64 \
        --gpu-memory-utilization 0.9 \
        --max-model-len 4096 \
        --dtype bfloat16 \
        --tensor-parallel-size 1 \
        --host 0.0.0.0 \
        --port "${PORT}" \
        --lora-modules-dir "${LORA_PATH}" \
        --trust-remote-code \
        &
    VLLM_PID=$!

    log_info "vLLM 进程 PID: ${VLLM_PID}"
}

# ------------------------------------------
# 健康检查等待
# ------------------------------------------
wait_for_healthy() {
    local max_retries=60
    local retry=0
    local health_url="http://localhost:${PORT}/health"

    log_info "等待 vLLM 服务就绪（最多等待 ${max_retries} x 5s）..."

    while [[ ${retry} -lt ${max_retries} ]]; do
        # 检查进程是否存活
        if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
            log_error "vLLM 进程已退出"
            exit 1
        fi

        if curl -sf "${health_url}" &>/dev/null; then
            log_info "vLLM 服务已就绪！"
            log_info "  健康检查: ${health_url}"
            log_info "  OpenAI API: http://localhost:${PORT}/v1"
            return 0
        fi

        retry=$((retry + 1))
        log_info "等待中... (${retry}/${max_retries})"
        sleep 5
    done

    log_error "vLLM 服务启动超时"
    kill "${VLLM_PID}" 2>/dev/null || true
    exit 1
}

# ------------------------------------------
# 优雅关闭
# ------------------------------------------
cleanup() {
    log_info "收到终止信号，正在关闭 vLLM 服务..."

    if [[ -n "${VLLM_PID:-}" ]] && kill -0 "${VLLM_PID}" 2>/dev/null; then
        # 先发送 SIGTERM，等待进程优雅退出
        kill -TERM "${VLLM_PID}" 2>/dev/null || true

        local wait_count=0
        while kill -0 "${VLLM_PID}" 2>/dev/null && [[ ${wait_count} -lt 30 ]]; do
            sleep 1
            wait_count=$((wait_count + 1))
        done

        # 如果进程仍在运行，强制终止
        if kill -0 "${VLLM_PID}" 2>/dev/null; then
            log_warn "vLLM 进程未在30秒内退出，强制终止"
            kill -KILL "${VLLM_PID}" 2>/dev/null || true
        fi
    fi

    log_info "vLLM 服务已关闭"
    exit 0
}

# 注册信号处理
trap cleanup SIGTERM SIGINT SIGQUIT

# ------------------------------------------
# 主流程
# ------------------------------------------
main() {
    log_info "===== vLLM 启动脚本 ====="

    check_gpu
    check_model
    start_vllm
    wait_for_healthy

    # 保持脚本运行，等待 vLLM 进程
    log_info "vLLM 服务运行中，按 Ctrl+C 停止"
    wait "${VLLM_PID}"
}

main "$@"
