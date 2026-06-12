# FastAPI Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment defaults
ENV USE_POSTGRESQL=true
ENV PG_HOST=postgres
ENV PG_PORT=5432
ENV PG_USER=qqassistant
ENV PG_PASSWORD=qqassistant2026
ENV PG_DATABASE=qqassistant
ENV REDIS_URL=redis://redis:6379/0
ENV VLLM_ENABLED=true
ENV VLLM_BASE_URL=http://vllm:8001

EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
