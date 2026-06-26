# QQ 智能助手

基于 Next.js 16 + FastAPI + vLLM 的 QQ 智能助手管理平台，提供对话管理、知识库检索、LoRA 微调训练、模型推理等功能。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | Next.js (App Router) + React + TypeScript + shadcn/ui + Tailwind CSS | 16.2.9 / 19.2.3 / 5.9 / 4.x |
| 后端 | Python FastAPI + Pydantic + SQLAlchemy | 0.136.x / 2.13.x / 2.0.x |
| 推理引擎 | vLLM（OpenAI 兼容 API） | 0.22.1 |
| 训练框架 | PyTorch + PEFT + TRL + bitsandbytes | 2.11.0+cu130 / 0.14+ / 0.45+ |
| 数据库 | SQLite（开发）/ PostgreSQL + pgvector（生产） | 14 |
| 缓存 | Redis（可选，未配置时自动降级为 DB 直连） | 7.4+ |
| 向量检索 | Faiss + sentence-transformers | 1.9+ / 5.0+ |
| 模型 | Qwen2.5-7B-Instruct-AWQ（4bit 量化，单卡 3090 即可运行） | - |
| 包管理 | pnpm（前端）/ pip（后端） | 11.9 / 24+ |

## 环境要求

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | 3.12 | 3.12.3 | vLLM 0.22.1 + transformers v5 要求 |
| Node.js | 22 LTS | 22.23.1 | 前端构建，通过 nvm 安装 |
| pnpm | 11 | 11.9.0 | 通过 corepack 启用 |
| CUDA 驱动 | 525+ | 595.58.03 | RTX 3090 推荐 |
| CUDA Runtime | 12.1+ | 13.0 | torch 2.11.0+cu130 内置 |
| GPU 显存 | 16GB | 24GB (3090) | AWQ 4bit 需 ~14GB |
| 磁盘空间 | 20GB | 40GB | 含模型 10GB + 依赖 5GB + 缓存 |

> CPU-only 模式：将 vLLM 替换为 Ollama，设置 `MODEL_PROVIDER=ollama`。

## 服务架构

```
浏览器 ──HTTP:5000──> Next.js 前端 ──/api/*──> FastAPI 后端 ──HTTP:8001──> vLLM 推理
                         (Next.js)              (FastAPI)                  (Qwen2.5-7B-AWQ)
                         端口 5000               端口 8000                  端口 8001
                                                  │
                                                  ├── SQLite (qq_assistant.db)
                                                  ├── Faiss 向量库 (vector_db/)
                                                  └── Redis [可选]
```

- **vLLM (8001)**: 加载 Qwen2.5-7B-Instruct-AWQ，提供 OpenAI 兼容的 `/v1/chat/completions` API
- **FastAPI (8000)**: 业务后端，管理认证/对话/训练/知识库，代理 vLLM 推理请求
- **Next.js (5000)**: 前端管理面板，`/api/*` 路由反向代理到 FastAPI

## 快速部署（AutoDL / 裸机，已验证）

以下命令在 AutoDL RTX 3090 容器（Ubuntu 22.04 / CUDA 驱动 595 / miniconda3）上验证通过。

### 0. 前置条件

```bash
# SSH 免密登录（本地执行，~/.ssh/config）
Host seetacloud
    HostName connect.nmb2.seetacloud.com
    Port 16389
    User root
    IdentityFile ~/.ssh/id_rsa

# 服务器上确认 GPU 和驱动
nvidia-smi  # 应显示 RTX 3090, 驱动 525+, CUDA 13.0+
```

### 1. 克隆代码

```bash
cd /root/autodl-tmp
git clone https://github.com/despaoy/qqchat-enhanced.git
cd qqchat-enhanced
```

### 2. 安装 Python 依赖（严格按顺序）

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate base

# ① PyTorch CUDA 13.0（vllm 0.22.1 硬性依赖 torch==2.11.0）
pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 \
    --index-url https://download.pytorch.org/whl/cu130

# ② vLLM 0.22.1（勿用 0.23.0+，有 pip 元数据解析 bug）
pip install vllm==0.22.1

# ③ 其余依赖
cd backend
pip install -r requirements.txt
```

### 3. 安装 Redis（推荐，缓存加速）

```bash
# AutoDL 等无 apt 环境的机器，用 conda 安装
conda install -y -c conda-forge redis-server
redis-server --daemonize yes
redis-cli ping  # 应返回 PONG
```

> Redis 为可选组件，未安装时后端自动降级为数据库直连模式，功能不受影响但性能略低。

### 4. 安装 Node.js + pnpm

```bash
# Node.js 22 LTS（通过 nvm）
export NVM_DIR=/root/.nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source /root/.nvm/nvm.sh
nvm install 22
nvm alias default 22

# pnpm 11（通过 corepack，Node 22 内置）
corepack enable
corepack prepare pnpm@latest --activate
pnpm --version  # 应显示 11.x
```

### 5. 构建前端

```bash
cd /root/autodl-tmp/qqchat-enhanced
pnpm install
pnpm build    # 输出 .next/standalone/
```

### 6. 下载模型

模型应放在项目目录外（如 `/root/autodl-tmp/models/`），避免重新克隆时丢失，然后符号链接到 `backend/models`：

```bash
# 创建稳定存储目录
mkdir -p /root/autodl-tmp/models

# 下载 Qwen2.5-7B-Instruct-AWQ（约 5.2GB，国内用 hf-mirror 加速）
export HF_ENDPOINT=https://hf-mirror.com
pip install huggingface_hub
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-AWQ \
    --local-dir /root/autodl-tmp/models/Qwen2.5-7B-Instruct-AWQ

# 下载嵌入模型（约 4.4GB，知识库检索用）
huggingface-cli download sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
    --local-dir /root/autodl-tmp/models/paraphrase-multilingual-MiniLM-L12-v2

# 符号链接到项目目录（如已存在 backend/models 目录，先删除）
rmdir /root/autodl-tmp/qqchat-enhanced/backend/models 2>/dev/null || true
ln -s /root/autodl-tmp/models /root/autodl-tmp/qqchat-enhanced/backend/models
```

### 7. 配置环境变量

```bash
cp .env.example backend/.env
```

编辑 `backend/.env`，关键配置项（AWQ 量化版）：

```env
ENVIRONMENT=production
VLLM_BASE_URLS=http://localhost:8001
VLLM_MODEL=/root/autodl-tmp/models/Qwen2.5-7B-Instruct-AWQ
VLLM_ENABLED=true
MODEL_PROVIDER=vllm
HF_ENDPOINT=https://hf-mirror.com
MODEL_PATH=./models/Qwen2.5-7B-Instruct-AWQ
LORA_PATH=./loras
DATABASE_PATH=./qq_assistant.db
VECTOR_DB_PATH=./vector_db
CORS_ORIGINS=http://localhost:5000,http://localhost:3000
```

创建必要目录：

```bash
mkdir -p backend/loras backend/data
```

### 8. 启动服务（三个 nohup 后台进程）

```bash
source /root/miniconda3/etc/profile.d/conda.sh && conda activate base

# ① vLLM（加载模型约 3 分钟，AWQ 用 float16，勿用 bfloat16）
cd /root/autodl-tmp/qqchat-enhanced/backend
nohup python -m vllm.entrypoints.openai.api_server \
    --model /root/autodl-tmp/models/Qwen2.5-7B-Instruct-AWQ \
    --enable-lora --max-loras 8 --max-lora-rank 64 \
    --gpu-memory-utilization 0.9 --max-model-len 4096 \
    --dtype float16 --tensor-parallel-size 1 \
    --host 0.0.0.0 --port 8001 \
    --enable-prefix-caching --trust-remote-code \
    > /root/vllm.log 2>&1 < /dev/null &

# 等待 vLLM 健康（约 175 秒）
until curl -sf http://localhost:8001/health; do sleep 5; done && echo "vLLM ready"

# ② FastAPI 后端（必须 --workers 1，训练状态为模块级变量）
# 设置 CUDA 13 库路径（解决 libnvJitLink.so.13 找不到的问题）
export LD_LIBRARY_PATH="/root/miniconda3/lib/python3.12/site-packages/nvidia/cu13/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/nvjitlink/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cublas/lib:/root/miniconda3/lib/python3.12/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH"
export PYTHONDONTWRITEBYTECODE=1
nohup python run.py --host 0.0.0.0 --port 8000 --workers 1 \
    > /root/backend.log 2>&1 < /dev/null &
sleep 5 && curl -s http://localhost:8000/health

# ③ Next.js 前端（生产模式）
export NVM_DIR=/root/.nvm && source /root/.nvm/nvm.sh && nvm use 22 >/dev/null
cd /root/autodl-tmp/qqchat-enhanced
nohup pnpm start > /root/frontend.log 2>&1 < /dev/null &
sleep 3 && curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost:5000
```

### 9. 本地访问（SSH 端口转发）

在本地终端执行：

```bash
ssh -N -L 5000:localhost:5000 -L 8000:localhost:8000 seetacloud
```

浏览器访问 http://localhost:5000 即可进入管理面板。

## 一键启动脚本

项目内置 `deploy/scripts/start_all.sh` 支持裸机/Docker 两种模式：

```bash
# 裸机模式（注意：默认启动 2 个 vLLM 实例，单 GPU 环境需手动修改为 1 个）
bash deploy/scripts/start_all.sh bare

# Docker 模式（需 NVIDIA Container Toolkit）
bash deploy/scripts/start_all.sh docker
```

> ⚠️ `start_all.sh` 默认启动 2 个 vLLM 实例（双 GPU），单卡环境请参考上方手动启动命令。

## 日志与进程管理

```bash
# 查看日志
tail -f /root/vllm.log       # vLLM
tail -f /root/backend.log    # FastAPI
tail -f /root/frontend.log   # Next.js

# 查看进程
ps aux | grep -E "vllm.entrypoints|uvicorn|next start" | grep -v grep

# 停止服务
pkill -f vllm.entrypoints
pkill -f "uvicorn app.main"
pkill -f "next start"
```

## 目录结构

```
qqchat-enhanced/
├── src/                         # 前端（Next.js 16）
│   ├── app/                      # 页面路由 + API 代理
│   ├── components/               # React 组件 (shadcn/ui)
│   ├── contexts/                 # 认证/设置上下文
│   ├── hooks/                    # 自定义 Hooks
│   └── lib/                      # API 客户端 + 类型
├── backend/                      # 后端（FastAPI）
│   ├── app/                      # 应用核心（配置/依赖注入）
│   ├── api/                      # API 路由
│   ├── db/                       # 数据库层（SQLite + PostgreSQL）
│   ├── inference/                # 推理引擎（vLLM 客户端）
│   ├── knowledge/                # 知识检索（Faiss/RAG）
│   ├── training/                 # LoRA 训练
│   ├── bot/                      # QQ 机器人（NoneBot2）
│   ├── cache/                    # 缓存层（Redis/语义缓存）
│   ├── infra/                    # 基础设施（熔断/备份/故障转移）
│   ├── models -> /root/autodl-tmp/models  # 符号链接（模型）
│   └── requirements.txt
├── deploy/
│   ├── scripts/
│   │   ├── start_all.sh          # 一键启动（Docker/Bare-metal）
│   │   └── start_vllm.sh         # vLLM 单实例启动
│   └── docker-compose.yml
├── Dockerfile                    # 前端 Docker 镜像
├── .env.example                  # 环境变量模板
└── package.json
```

## Docker 部署

```bash
cd deploy
cp ../.env.example .env
# 编辑 .env 设置 PG_PASSWORD 等敏感信息

docker compose up -d
```

## RTX 3090 性能参考

| 模式 | 显存占用 | 模型加载 | 首 token 延迟 | 输出速度 | 最大并发 |
|------|---------|---------|--------------|---------|---------|
| AWQ 4bit (float16) | ~14GB | ~175s | ~1.2s | ~78 tok/s | 5-6 |
| FP16 全量 | ~21GB | ~120s | ~1.8s | ~115 tok/s | 3 |

## 常见问题

### vLLM 安装报 `TypeError: expected string or bytes-like object, got 'NoneType'`

vLLM 0.23.0+ 在 pip 依赖解析阶段有元数据解析 bug。**必须使用 `vllm==0.22.1`**：

```bash
pip install vllm==0.22.1  # 不要用 pip install vllm（会装 0.23.0）
```

### vLLM 报 `unrecognized arguments: --lora-modules-dir`

vLLM 0.22.1 已移除 `--lora-modules-dir` 参数。LoRA 适配器通过 API 动态加载，只需 `--enable-lora` 即可，无需指定目录。

### vLLM 启动报 CUDA / dtype 相关错误

AWQ 量化模型必须使用 `--dtype float16`（或 `auto`），**不要用 `--dtype bfloat16`**。RTX 3090 的 Ampere 架构对 bfloat16 + AWQ 组合支持有限。

### bitsandbytes 报 `libnvJitLink.so.13: cannot open shared object file`

PyTorch 2.11.0+cu130 需要 CUDA 13 运行时库，但系统可能只安装了 CUDA 12。CUDA 13 库已随 pip 包安装，需手动加入 `LD_LIBRARY_PATH`：

```bash
# 查找 CUDA 13 库路径
CUDA13_LIB=$(python -c "import nvidia.cuda13; print(nvidia.cuda13.lib_dir)" 2>/dev/null || \
    echo "/root/miniconda3/lib/python3.12/site-packages/nvidia/cu13/lib")
NVJITLINK_LIB=$(python -c "import nvidia.nvjitlink; print(nvidia.nvjitlink.lib_dir)" 2>/dev/null || \
    echo "/root/miniconda3/lib/python3.12/site-packages/nvidia/nvjitlink/lib")
CUBLAS_LIB=$(python -c "import nvidia.cublas; print(nvidia.cublas.lib_dir)" 2>/dev/null || \
    echo "/root/miniconda3/lib/python3.12/site-packages/nvidia/cublas/lib")
CUDNN_LIB=$(python -c "import nvidia.cudnn; print(nvidia.cudnn.lib_dir)" 2>/dev/null || \
    echo "/root/miniconda3/lib/python3.12/site-packages/nvidia/cudnn/lib")
export LD_LIBRARY_PATH="$CUDA13_LIB:$NVJITLINK_LIB:$CUBLAS_LIB:$CUDNN_LIB:$LD_LIBRARY_PATH"
```

> 建议将上述路径写入 `~/.bashrc` 或后端启动脚本中。

### 后端多 worker 导致训练状态丢失

训练状态（`_training_status`、`_generation_status`）是模块级变量，多 worker 间不共享。**必须以 `--workers 1` 启动后端**：

```bash
python run.py --host 0.0.0.0 --port 8000 --workers 1
```

### scikit-learn 1.9.0 报 `multi_class` 参数不支持

scikit-learn 1.9.0 移除了 `LogisticRegression` 的 `multi_class` 参数。已修复，无需手动处理。

### gptqmodel >=7.x 报 `AwqGEMMQuantLinear` 不存在

gptqmodel 7.x 将 `AwqGEMMQuantLinear` 重命名为 `AwqGEMMLinear`。已内置兼容性补丁，无需手动处理。

### .pyc 缓存导致代码修改不生效

Python 缓存的 `.pyc` 文件可能导致修改不生效。清除缓存并禁止写入：

```bash
find backend -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
export PYTHONDONTWRITEBYTECODE=1
```

### `pnpm start` 报 `output: standalone` 警告

Next.js 16 在 `output: 'standalone'` 模式下推荐用 `node .next/standalone/server.js` 启动。`pnpm start` 仍可工作，但会有警告。生产环境可用：

```bash
PORT=5000 HOSTNAME=0.0.0.0 node .next/standalone/server.js
```

### Redis 连接失败

后端启动时显示 `Redis 缓存连接失败，将使用数据库直连模式` 是正常的——未配置 Redis 时自动降级。如需启用：

```bash
# AutoDL 等无 apt 环境的机器，用 conda 安装 Redis
conda install -y -c conda-forge redis-server
redis-server --daemonize yes

# .env 中添加
REDIS_URL=redis://localhost:6379/0
```

### JWT_SECRET 自动生成

首次启动后端会自动生成 JWT 密钥并写入 `.env`。多实例部署时需手动统一 `JWT_SECRET` 值。

### 前端端口冲突

修改 `package.json` 中 `"start": "next start -p 5000"` 的端口号，并同步更新后端 `.env` 的 `CORS_ORIGINS`。

### 显存不足

- 使用 AWQ 4bit 量化模型（默认推荐）
- 降低 `--gpu-memory-utilization`（如 0.85）
- 降低 `--max-model-len`（如 2048）
- 减少 `--max-loras` 数量

### vLLM LoRA 多适配器加载

vLLM 启动时通过 `--lora-modules` 预注册 LoRA 适配器，格式为 `名称=路径`：

```bash
nohup python -m vllm.entrypoints.openai.api_server \
    --model /root/autodl-tmp/models/Qwen2.5-7B-Instruct-AWQ \
    --enable-lora --max-loras 4 --max-lora-rank 32 \
    --lora-modules \
        hutao=/path/to/hutao_lora/final \
        minamo=/path/to/minamo_lora \
    --gpu-memory-utilization 0.85 --max-model-len 4096 \
    --quantization awq --tensor-parallel-size 1 \
    --host 0.0.0.0 --port 8001 \
    --enable-prefix-caching --trust-remote-code \
    > /root/vllm.log 2>&1 &
```

后端 `/api/loras/scan` 扫描 `backend/loras/` 目录自动注册到数据库，vLLM 侧通过 `--lora-modules` 预加载。

## 知识库初始化

```bash
# 嵌入模型已通过符号链接包含在 backend/models/ 中
# 首次使用知识库功能时自动加载

# 如需重新下载嵌入模型
huggingface-cli download sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
    --local-dir /root/autodl-tmp/models/paraphrase-multilingual-MiniLM-L12-v2
```

## License

MIT
