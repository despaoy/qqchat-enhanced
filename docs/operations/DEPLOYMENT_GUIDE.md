# 部署与验收指南

本指南面向个人研究展示和单机 RTX 3090 部署。Kubernetes、服务网格和多机高可用不属于当前必要范围。

## 1. 前置条件

- Linux x86_64，NVIDIA 驱动能够运行 CUDA 12.x 应用。
- RTX 3090 24GB；启动前至少预留 20GB 显存。
- Python 3.12、Node.js 22、pnpm 10。
- 代码和全部运行数据位于当前用户有权限的目录。

## 2. 获取源码

```bash
cd /home/szw/lhm2
git clone https://github.com/despaoy/qqchat-enhanced.git
cd qqchat-enhanced
git status -sb
```

服务器工作区非干净时，不要直接执行 `git pull`。先保存实验文件，再同步。

## 3. 激活环境

```bash
source /home/szw/lhm2/activate_qqchat.sh
python --version
python -m pip check
node --version
pnpm --version
```

预期至少满足 Python 3.12、Node.js 22，且 `pip check` 不报告冲突。

## 4. 配置

```bash
cd /home/szw/lhm2/qqchat-enhanced
cp .env.example .env
chmod 600 .env
```

必须修改：

- `JWT_SECRET`
- `ASTRBOT_INTEGRATION_TOKEN`
- `ALLOWED_ORIGINS`
- `MODEL_PROVIDER=vllm`
- `VLLM_BASE_URL=http://127.0.0.1:8001`
- `BASE_MODEL_PATH=/home/szw/lhm2/runtime/models/Qwen3-8B-Instruct`
- `LORA_PATH=/home/szw/lhm2/runtime/loras`
- `EMBEDDING_MODEL_PATH=/home/szw/lhm2/runtime/models/bge-m3`
- `RERANKER_MODEL_PATH=/home/szw/lhm2/runtime/models/bge-reranker-v2-m3`

生产或公开网络禁止空 token、默认 JWT 密钥和宽泛 CORS。

## 5. 验证源码

```bash
cd /home/szw/lhm2/qqchat-enhanced
python -m pytest backend/tests -q
pnpm install --frozen-lockfile
pnpm ts-check
pnpm build
```

## 6. 启动顺序

1. PostgreSQL/Redis（如启用）。
2. vLLM。
3. FastAPI。
4. Next.js。
5. AstrBot。

vLLM 示例：

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve \
  /home/szw/lhm2/runtime/models/Qwen3-8B-Instruct-AWQ \
  --served-model-name qwen3-8b-instruct-awq \
  --host 127.0.0.1 \
  --port 8001 \
  --quantization awq_marlin \
  --gpu-memory-utilization 0.88 \
  --max-model-len 8192 \
  --enable-lora \
  --max-lora-rank 64
```

后端：

```bash
cd /home/szw/lhm2/qqchat-enhanced
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

SQLite 只使用一个 worker。切换 PostgreSQL并确认共享限流、队列和缓存后，才考虑增加 worker。

前端：

```bash
cd /home/szw/lhm2/qqchat-enhanced
pnpm build
pnpm start
```

## 7. 健康检查

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8001/v1/models
curl -fsS http://127.0.0.1:5000/api/health
```

真实验收还应覆盖：登录、生成、历史入库、LoRA 扫描/切换、知识库导入/检索、AstrBot 鉴权与幂等、监控指标。

## 8. SSH 映射

在个人电脑执行：

```bash
ssh -L 5000:127.0.0.1:5000 \
    -L 8000:127.0.0.1:8000 \
    -L 8001:127.0.0.1:8001 \
    -L 6185:127.0.0.1:6185 \
    <lab-user>@<lab-host>
```

浏览器访问 `http://127.0.0.1:5000`，AstrBot 面板访问 `http://127.0.0.1:6185`。