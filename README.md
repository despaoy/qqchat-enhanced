# QQ 智能助手

基于 Next.js 16 + FastAPI + vLLM 的 QQ 智能助手管理平台，提供对话管理、知识库检索、LoRA 微调训练、模型推理等功能。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | Next.js (App Router) + React + TypeScript + shadcn/ui + Tailwind CSS | 16.1.1 / 19.2.3 / 5.x / 4.x |
| 后端 | Python FastAPI + Pydantic + SQLAlchemy | 0.115.x / 2.10.x / 2.0.x |
| 推理引擎 | vLLM（OpenAI 兼容 API） | 0.7.2 |
| 训练框架 | PyTorch + PEFT + TRL + bitsandbytes | 2.4.1 / 0.14.0 / 0.12.2 / 0.44.1 |
| 数据库 | SQLite（开发）/ PostgreSQL + pgvector（生产） | 14 |
| 缓存 | Redis | 7.4 |
| 向量检索 | Faiss + sentence-transformers | 1.9.x / 3.3.x |
| 模型 | Qwen2.5-7B-Instruct（支持 AWQ 4bit 量化） | - |
| 包管理 | pnpm（前端）/ pip（后端） | 9.x |

## 环境要求

- **Python** 3.11+
- **Node.js** 20+
- **pnpm** 9+
- **NVIDIA GPU**（推荐 RTX 3090 24GB，单卡即可运行 Qwen2.5-7B-Instruct FP16）
- **CUDA** 12.1

CPU 模式运行：将 vLLM 替换为 Ollama 即可（见下文）。

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/despaoy/qqchat-enhanced.git
cd qqchat-enhanced
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

# 先安装 PyTorch (CUDA 12.1)
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 \
    --index-url https://download.pytorch.org/whl/cu121

# 再安装 vLLM
pip install vllm==0.7.2

# 最后安装其余依赖
pip install -r requirements.txt
```

### 4. 下载模型

```bash
pip install huggingface_hub

# 下载 Qwen2.5-7B-Instruct（原版 FP16，约 15GB，3090 单卡可运行）
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir /root/autodl-tmp/Qwen2.5-7B-Instruct

# 或下载 AWQ 4bit 量化版（约 5GB，显存占用更小，适合多 LoRA 并存）
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-AWQ \
    --local-dir /root/autodl-tmp/Qwen2.5-7B-Instruct-AWQ
```

LoRA 适配器模型放入 `backend/loras/` 下（可选）。

### 5. 配置环境变量

```bash
cp .env.example backend/.env
```

关键配置项：

```env
# vLLM 推理服务地址
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
# 单卡 3090 FP16 模式（推荐）
python -m vllm.entrypoints.openai.api_server \
    --model /root/autodl-tmp/Qwen2.5-7B-Instruct \
    --enable-lora \
    --max-loras 4 \
    --max-lora-rank 64 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 4096 \
    --dtype float16 \
    --host 0.0.0.0 \
    --port 8001

# AWQ 4bit 量化模式
python -m vllm.entrypoints.openai.api_server \
    --model /root/autodl-tmp/Qwen2.5-7B-Instruct-AWQ \
    --quantization awq \
    --enable-lora \
    --max-loras 8 \
    --max-lora-rank 64 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 \
    --dtype half \
    --host 0.0.0.0 \
    --port 8001

# 或使用启动脚本
python backend/scripts/launch_vllm.py                    # FP16 默认
python backend/scripts/launch_vllm.py --quant awq       # AWQ 量化
python backend/scripts/launch_vllm.py --tensor-parallel 2  # 双卡并行

# 或 CPU 模式（Ollama）
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

## AutoDL 一键部署（RTX 3090）

```bash
# 1. 选择镜像：PyTorch 2.4.0 / CUDA 12.1 / Python 3.11
# 2. 执行初始化
cd /root/autodl-tmp
git clone https://github.com/despaoy/qqchat-enhanced.git
cd qqchat-enhanced/backend

python -m venv /root/autodl-tmp/qqchat-env
source /root/autodl-tmp/qqchat-env/bin/activate

pip install torch==2.4.1+cu121 torchvision==0.19.1+cu121 torchaudio==2.4.1+cu121 \
    --index-url https://download.pytorch.org/whl/cu121
pip install vllm==0.7.2
pip install -r requirements.txt

# 3. 下载模型
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir /root/autodl-tmp/Qwen2.5-7B-Instruct

# 4. 启动 vLLM（后台）
nohup python -m vllm.entrypoints.openai.api_server \
    --model /root/autodl-tmp/Qwen2.5-7B-Instruct \
    --dtype float16 --max-model-len 4096 \
    --gpu-memory-utilization 0.90 --enable-lora \
    --max-loras 4 --max-lora-rank 64 \
    --host 0.0.0.0 --port 8001 \
    > /root/autodl-tmp/vllm.log 2>&1 &

# 5. 启动后端
export VLLM_BASE_URLS=http://localhost:8001
python run.py --port 8000
```

## 目录结构

```
src/                         # 前端（Next.js 16）
├── app/                    # 页面路由 + API 代理
├── components/             # React 组件 (shadcn/ui)
├── contexts/               # 认证/设置上下文
├── hooks/                  # 自定义 Hooks
└── lib/                    # API 客户端 + 类型

backend/                     # 后端（FastAPI）
├── app/                    # 应用核心（配置/依赖注入/模块管理）
├── api/                    # API 路由（auth/knowledge/training/loras/stats...）
├── db/                     # 数据库层（SQLite + PostgreSQL + Pydantic 模型）
├── inference/              # 推理引擎（vLLM 客户端/模型管理/优化器）
├── knowledge/              # 知识检索（Faiss/RAG/重排序/文本分块）
├── training/               # 训练模块（LoRA 训练器/数据预处理）
├── bot/                    # QQ 机器人（NoneBot2）
├── cache/                  # 缓存层（Redis/语义缓存/消息队列）
├── middleware/              # 安全中间件（限流/认证/审计）
├── infra/                  # 基础设施（负载均衡/熔断/备份/故障转移）
├── scripts/                # 部署与启动脚本
└── tests/                  # 测试

deploy/                      # 部署配置
├── docker-compose.yml      # Docker Compose（PostgreSQL + Redis + vLLM + Nginx）
└── nginx/                  # Nginx 反向代理配置
```

## Docker 部署

```bash
cd deploy

# 配置环境变量
cp ../.env.example .env
# 编辑 .env 设置 PG_PASSWORD 等敏感信息

# 下载模型
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir /root/autodl-tmp/Qwen2.5-7B-Instruct

# 启动
docker compose up -d
```

## RTX 3090 性能参考

| 模式 | 显存占用 | 首 token 延迟 | 输出速度 | 最大并发 |
|------|---------|--------------|---------|---------|
| FP16 全量 | ~21GB | ~1.8s | ~115 tok/s | 3 |
| AWQ 4bit | ~14GB | ~1.2s | ~78 tok/s | 5-6 |

## 知识库初始化

```bash
mkdir -p backend/knowledge_bases

# 下载嵌入模型（首次启动自动下载）
pip install sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# 下载重排序模型
huggingface-cli download BAAI/bge-reranker-base \
    --local-dir backend/bge-reranker-base
```

## 常见问题

**Q: 显存不足？**
使用 AWQ 量化模型，或降低 `--gpu-memory-utilization` 和 `--max-model-len`。

**Q: 纯 CPU 运行？**
安装 Ollama 替代 vLLM，设置 `MODEL_PROVIDER=ollama`。

**Q: 前端端口冲突？**
修改 `pnpm dev --port 5000` 中的端口号，并同步更新后端的 `CORS_ORIGINS`。

**Q: 知识库搜索无结果？**
确保嵌入模型已下载，向量库已建好索引。

**Q: RTX 3090 不支持 bfloat16？**
正确，请使用 `--dtype float16` 或 `--dtype half`，不要使用 `--dtype bfloat16`。

## License

MIT
