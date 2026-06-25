# FastAPI Backend
# 构建参数：
#   INSTALL_GPU_DEPS=true  安装 PyTorch CUDA + vLLM（生产部署，需要 NVIDIA GPU）
#   INSTALL_GPU_DEPS=false 仅安装 CPU 版 PyTorch，跳过 vLLM（CI / 无 GPU 环境）
ARG INSTALL_GPU_DEPS=true

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc for cryptography/bitsandbytes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Re-declare ARG after FROM (ARG before FROM is only for FROM itself)
ARG INSTALL_GPU_DEPS=true

COPY requirements.txt .

# Conditional dependency installation based on GPU availability
# vllm 0.22.1 严格依赖 torch==2.11.0，必须先装 torch 再装 vllm
RUN if [ "$INSTALL_GPU_DEPS" = "true" ]; then \
        echo "Installing GPU dependencies (PyTorch CUDA 13.0 + vLLM)..." && \
        pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 \
            --index-url https://download.pytorch.org/whl/cu130 && \
        pip install --no-cache-dir vllm==0.22.1; \
    else \
        echo "Installing CPU-only dependencies (skipping vLLM)..." && \
        pip install --no-cache-dir torch torchvision torchaudio \
            --index-url https://download.pytorch.org/whl/cpu; \
    fi && \
    grep -v -E "^(torch|torchvision|torchaudio|vllm)" requirements.txt > requirements-filtered.txt && \
    pip install --no-cache-dir -r requirements-filtered.txt

# Copy application code
COPY . .

# Environment defaults (密码通过环境变量注入，不硬编码)
ENV USE_POSTGRESQL=true
ENV PG_HOST=${PG_HOST:-postgres}
ENV PG_PORT=${PG_PORT:-5432}
ENV PG_USER=${PG_USER:-qqassistant}
ENV PG_PASSWORD=${PG_PASSWORD:-changeme}
ENV PG_DATABASE=${PG_DATABASE:-qqassistant}
ENV REDIS_URL=${REDIS_URL:-redis://redis:6379/0}
ENV VLLM_ENABLED=true
ENV VLLM_BASE_URL=${VLLM_BASE_URL:-http://vllm:8001}

EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
