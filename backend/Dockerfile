# FastAPI Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (gcc for cryptography/bitsandbytes; asyncpg 不需要 libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Install PyTorch first (CUDA 12.1), then vLLM, then remaining deps
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir vllm==0.7.2 && \
    pip install --no-cache-dir -r requirements.txt

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
