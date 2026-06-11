# QQ 智能助手

基于 Next.js 16 + FastAPI + vLLM 的 QQ 智能助手管理平台，提供对话管理、知识库检索、LoRA 微调训练、模型推理等功能。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16 (App Router) + React 19 + TypeScript + shadcn/ui + Tailwind CSS 4 |
| 后端 | Python FastAPI |
| 推理引擎 | vLLM（OpenAI 兼容 API） |
| 数据库 | SQLite（开发）/ 可替换为 PostgreSQL |
| 向量检索 | Faiss + sentence-transformers |
| 模型 | Qwen2.5-7B-Instruct（支持 AWQ 量化） |
| 包管理 | pnpm（前端）/ pip（后端） |

## 环境要求

- **Python** 3.10+
- **Node.js** 18+
- **pnpm** 9+
- **NVIDIA GPU**（推荐 RTX 3090 / 4090，显存 ≥16GB）
- **CUDA** 12.1+

CPU 模式运行：将 vLLM 替换为 ollama 即可（见下文）。

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/qq-assistant-enhanced.git
cd qq-assistant-enhanced
```

### 2. 安装前端依赖

```bash
pnpm install
```

### 3. 安装后端依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
pip install vllm  # GPU 推理（如需 CPU 模式则装 ollama）
```

### 4. 下载模型

```bash
# 安装 huggingface-cli
pip install huggingface_hub

# 下载 Qwen2.5-7B-Instruct（原版，约 15GB）
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir backend/models/Qwen2.5-7B-Instruct

# 或下载 AWQ 4bit 量化版（约 5GB，显存占用更小）
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-AWQ \
    --local-dir backend/models/Qwen2.5-7B-Instruct-AWQ
```

LoRA 适配器模型也放入 `backend/loras/` 下（可选）。

### 5. 配置环境变量

```bash
# 后端（创建 backend/.env）
cp .env.example backend/.env
```

关键配置项：

```env
# vLLM 推理服务地址（可多个，逗号分隔）
VLLM_BASE_URLS=http://localhost:8001
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_TIMEOUT=120
VLLM_MAX_RETRIES=3

# 数据库路径
DATABASE_PATH=./qq_assistant.db

# 向量数据库路径
VECTOR_DB_PATH=./vector_db

# CORS 允许的前端地址
CORS_ORIGINS=http://localhost:5000
```

### 6. 启动推理服务

```bash
# GPU 模式（双卡 TP=2，每卡 50% 显存）
python -m vllm.entrypoints.openai.api_server \
    --model backend/models/Qwen2.5-7B-Instruct \
    --enable-lora \
    --max-loras 4 \
    --max-lora-rank 64 \
    --gpu-memory-utilization 0.50 \
    --max-model-len 4096 \
    --dtype float16 \
    --tensor-parallel-size 2 \
    --host 0.0.0.0 \
    --port 8001 \
    --trust-remote-code

# 或 CPU 模式（ollama）
ollama pull qwen2.5:7b
ollama serve
# 然后设置环境变量 MODEL_PROVIDER=ollama
```

### 7. 启动后端

```bash
cd backend
python run.py --port 8000 --reload
```

### 8. 启动前端

```bash
pnpm dev --port 5000
```

访问 http://localhost:5000 进入管理界面。

## 目录结构

```
src/                         # 前端（Next.js 16）
├── app/                    # 页面路由 + API 代理
├── components/             # React 组件
├── contexts/               # 认证/设置上下文
├── hooks/                  # 自定义 Hooks
└── lib/                    # API 客户端 + 类型 + 国际化

backend/                     # 后端（FastAPI）
├── app/                    # 应用核心（配置/依赖注入/模块管理）
├── api/                    # API 路由（auth/knowledge/training/loras/stats...）
├── db/                     # 数据库层（SQLite + Pydantic 模型）
├── inference/              # 推理引擎（vLLM 客户端/模型管理/优化器）
├── knowledge/              # 知识检索（Faiss/RAG/重排序/文本分块）
├── training/               # 训练模块（LoRA 训练器/数据预处理）
├── bot/                    # QQ 机器人
├── middleware/              # 安全中间件（限流/认证/审计）
├── infra/                  # 基础设施（负载均衡/熔断/备份/故障转移）
├── benchmarks/             # 性能测试
└── tests/                  # 测试

deploy/                      # 部署配置
├── docker-compose.yml      # Docker Compose
├── nginx/                  # Nginx 配置
└── scripts/                # 启动脚本
```

## Docker 部署

```bash
cd deploy

# 创建数据目录
mkdir -p data/models data/loras data/app

# 下载模型
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-AWQ \
    --local-dir data/models/Qwen2.5-7B-Instruct-AWQ

# 放置 LoRA（可选）
cp -r ../backend/loras/* data/loras/ 2>/dev/null || true

# 启动
docker compose -f docker-compose.yml up -d
```

## 知识库初始化

```bash
# 知识库语料放在此目录下
mkdir -p backend/knowledge_bases

# 下载嵌入模型（首次启动自动下载，或手动下载）
pip install sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# 下载重排序模型
huggingface-cli download BAAI/bge-reranker-base \
    --local-dir backend/bge-reranker-base
```

## 常见问题

**Q: 显存不足？**  
使用 AWQ 量化模型，或降低 `--gpu-memory-utilization` 和 `--max-model-len`。

**Q: 纯 CPU 运行？**  
安装 ollama 替代 vLLM，设置 `MODEL_PROVIDER=ollama`。

**Q: 前端端口冲突？**  
修改 `pnpm dev --port 5000` 中的端口号，并同步更新后端的 `CORS_ORIGINS`。

**Q: 知识库搜索无结果？**  
确保嵌入模型已下载，向量库已建好索引。
