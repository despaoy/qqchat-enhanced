# 下一阶段实施与验收指南

> 项目：QQChat Enhanced  
> 更新：2026-07-12  
> 目标：把当前可运行的 LLM 应用，推进为可复现、可演示、可长期维护的多平台系统。

## 一、当前状态

已经通过验证：

- FastAPI、Next.js、FAISS、Redis 与 vLLM AWQ 模型可联动。
- 服务器正在运行真实模型 `qwen2.5-7b-awq`。
- 后端核心测试：`86 passed, 1 skipped`。
- 前端 TypeScript 与 Next.js 生产构建通过。
- AstrBot 网关接口、评估任务、LoRA、RAG、偏好数据管理页面均已具备基础能力。

仍需完成：

- 服务器当前仍是 SQLite 开发配置，生产环境应迁移到 PostgreSQL。
- Redis 目前由手动进程启动，服务器重启后不能保证自动恢复。
- QQ、个人微信等真实平台需要在 AstrBot 面板由你扫码、授权和验收。
- 本地已经有一轮经过测试的修复，需提交、推送并部署到服务器。

## 二、最优先做的三件事

### 1. 提交本轮修复

提交前在项目根目录执行：

```powershell
pnpm ts-check
pnpm lint
pnpm build
cd backend
py -3.12 -m pytest tests -q
```

本轮修复包括：评估接口死代码清理，以及评估、实验、路由、偏好数据的前端 API 类型补齐。当前 `pnpm lint` 只剩既有的未使用变量警告，没有阻断错误。

### 2. 立即轮换敏感凭据

曾出现在聊天、截图、终端历史中的密码、token 和 SSH 密码都应视为泄露。

1. 修改 QQ 密码，并检查设备登录记录。
2. 修改服务器 SSH 密码；推荐改用 SSH 密钥登录并关闭密码登录。
3. 重新生成 AstrBot token、JWT secret、数据库密码。
4. 不把真实密钥写进 Git、README、前端代码或截图。
5. 使用 `ASTRBOT_INTEGRATION_TOKENS` 做短期 token 轮换，确认新 token 生效后删除旧 token。

生成随机密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. 保留可回滚版本

部署前在服务器执行：

```bash
cd /root/autodl-tmp/qqchat-enhanced
git rev-parse HEAD
cp backend/qq_assistant.db backups/qq_assistant.db.before-production
```

只有在健康检查、登录、真实推理和历史查询都通过后，才清理旧备份。

## 三、服务器生产化

### 1. 使用 Docker Compose 管理服务

推荐使用 `deploy/docker-compose.yml` 管理 PostgreSQL、Redis、vLLM、FastAPI、Next.js 和 Nginx，而不是长期依赖多个 `screen` 进程。

准备环境：

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

最后一条命令失败时，应先安装或修复 NVIDIA Container Toolkit，不要继续启动 vLLM 容器。

### 2. 创建生产环境变量

```bash
cp .env.example .env
chmod 600 .env
```

最小生产配置：

```dotenv
ENVIRONMENT=production
PG_USER=qqassistant
PG_PASSWORD=<long-random-password>
PG_DATABASE=qqassistant
DATABASE_URL=postgresql+asyncpg://qqassistant:<url-encoded-password>@postgres:5432/qqassistant
REDIS_URL=redis://redis:6379/0
VLLM_BASE_URL=http://vllm:8001
VLLM_SERVED_MODEL_NAME=qwen2.5-7b-awq
ASTRBOT_INTEGRATION_TOKEN=<long-random-shared-secret>
JWT_SECRET=<at-least-32-random-characters>
ALLOWED_ORIGINS=https://<your-domain>
LOG_LEVEL=INFO
BACKEND_WORKERS=1
CLAW_CODE_EXECUTION_ENABLED=false
```

当前建议保持 `BACKEND_WORKERS=1`。等 PostgreSQL、Redis 队列和并发压测完善后，再评估多 worker。

### 3. 统一文件位置

```text
deploy/data/
  models/Qwen2.5-7B-Instruct-AWQ/
  loras/<adapter-name>/
  knowledge_bases/<kb-name>/
  datasets/<dataset-name>/
  reports/<experiment-id>/
backups/
logs/
```

- LoRA 目录应包含 `adapter_config.json` 与权重文件。
- RAG 文档要保存来源、导入日期、内容 hash 与索引版本。
- 每个训练数据集要有 `dataset-card.md`，记录来源、许可证、样本数、清洗规则和风险。

### 4. 启动后验收

```bash
cd deploy
docker compose --env-file ../.env up -d --build
docker compose ps
curl -fsS http://127.0.0.1/health
curl -fsS http://127.0.0.1/api/health
```

必须确认：

1. 所有容器是 running 或 healthy，没有 restarting。
2. PostgreSQL、Redis、backend、frontend、vLLM 都有健康检查。
3. 只对公网暴露 Nginx 的 80/443；不要暴露 PostgreSQL、Redis、FastAPI、vLLM 端口。
4. 做一次数据库备份恢复演练。

## 四、AstrBot、QQ 与个人微信

扫码、短信验证和设备确认必须由你本人在 AstrBot WebUI 完成；账号密码不应写入插件配置或仓库。

### 1. 安装网关插件

在 AstrBot 插件管理中安装仓库里的 `astrbot_plugins/qqchat_gateway`，并配置：

```dotenv
QQCHAT_BACKEND_URL=http://backend:8000
ASTRBOT_INTEGRATION_TOKEN=<same-as-backend>
QQCHAT_TRIGGER_PREFIXES=/ai,/chat,@bot
QQCHAT_REPLY_GROUP_ALL=false
QQCHAT_BACKEND_TIMEOUT=60
QQCHAT_DEDUP_TTL=300
QQCHAT_QQ_ADAPTER=napcat
QQCHAT_WECHAT_ADAPTER=gewechat
```

同机非 Docker 部署时使用 `http://127.0.0.1:8000`；容器内部使用 `http://backend:8000`。

### 2. QQ 验收

1. 在 AstrBot 新建 OneBot 适配器。
2. 在 NapCat 将反向 WebSocket 指向 AstrBot，不再直连旧 NoneBot。
3. 默认关闭群全量回复，只允许 @、`/ai` 或 `/chat` 触发。
4. 私聊发送唯一测试消息，例如 `codex_e2e_qq_20260712`。
5. 后台历史应出现 `platform=qq`、`adapter=napcat`、`conversationId` 和 `traceId`。
6. 重复发送同一消息 ID，只应回复和入库一次。

### 3. 个人微信验收

1. 在 AstrBot 个人微信适配器中扫码登录，登录状态只留在服务器。
2. 设置 `ASTRBOT_WECHAT_PERSONAL_ENABLED=true` 并重启后端。
3. 先用另一个微信号私聊测试自动回复、历史记录和 traceId。
4. 再用小群验证“未 @ 不回复，@ 后回复”。
5. 个人微信适配器有掉线、封号和合规风险，只建议测试号小范围使用。

一次只启用一个新平台。完成私聊、群聊、重复消息、无 token、超长文本五项测试后，再启用下一个。

## 五、LoRA、RAG 与研究实验

### 1. LoRA

每次训练必须记录：基础模型、数据版本、随机种子、rank、alpha、dropout、学习率、epoch、batch size，以及 CUDA、PyTorch、PEFT、transformers 版本。

建议顺序：基线 LoRA，DoRA，RSLoRA，可选 NEFTune 与 packing。每组保存训练配置 JSON、日志、adapter、验证集指标和固定 prompt 输出。不要把 mock 消融表当作真实实验结论。

### 2. RAG

建立 50 至 100 条问题的评估集，每条包括期望文档 ID、标准答案或评分 rubric。对比 vector-only、BM25-only、hybrid、hybrid + reranker，并记录 Recall@5、MRR、nDCG、检索延迟、回答正确率和引用正确率。低置信度时应拒答，不要编造答案。

### 3. AWQ 与 vLLM

真实量化对比必须为每种量化版本独立启动 vLLM，不能在同一个 AWQ 服务上冒充 FP16、NF4 或 INT8 结果。使用：

```bash
bash deploy/compare_quantization.sh
```

每轮记录模型、量化方式、vLLM 命令、GPU、驱动、CUDA、上下文长度、并发、VRAM、TTFT、tokens/s、P50/P95 和固定 prompt 质量评分。

### 4. 偏好数据与 DPO/ORPO

从历史中采样候选回答，人工标注 chosen/rejected 和 rubric，只导出已审核样本。先小规模做 DPO 或 ORPO，对比 SFT-only 与偏好优化模型。未经脱敏、同意和人工审核的生产对话不能自动进入训练集。

## 六、最小验收矩阵

| 模块 | 必须通过的真实测试 |
| --- | --- |
| 登录与安全 | 注册、登录、登出、未登录管理 API 被拒绝 |
| 模型 | 真实 Qwen 回复、历史入库、traceId 可查询 |
| LoRA | 发现 adapter、切换、加载失败回退、恢复基础模型 |
| RAG | 导入文档、检索、引用展示、低置信度拒答 |
| AstrBot | QQ 或微信真实私聊、群触发策略、重复事件去重 |
| 队列与限流 | 同会话顺序、突发消息不产生 500、满队列有降级 |
| 观测 | traceId 串起网关和后端日志，面板有延迟和错误率 |
| 备份恢复 | PostgreSQL 备份可恢复，Redis 重启不丢核心数据 |

## 七、两周行动计划

### 第 1 至 2 天：稳定部署

- 提交当前修复。
- 轮换密码和 token。
- 用 Docker Compose 启动 PostgreSQL、持久 Redis、backend、frontend、Nginx。
- 关闭 vLLM、Redis、PostgreSQL 的公网端口。

### 第 3 至 4 天：真实平台链路

- 完成 AstrBot + QQ 的私聊、群聊、去重和 traceId 验收。
- 用测试号完成个人微信小范围验证。
- 保存一条跨平台链路截图和对应日志。

### 第 5 至 8 天：研究证据

- 完成 dataset card 和至少 100 条 Gold Set。
- 完成 LoRA、DoRA、RSLoRA 至少两个对照实验。
- 完成 vector、BM25、hybrid 三种 RAG 对照实验。

### 第 9 至 14 天：展示材料

- 完成 AWQ 与基线的显存、TTFT、吞吐对比。
- 准备 20 至 50 组人工偏好对，做小型 DPO/ORPO 验证。
- 整理系统架构、三张实验表与 8 分钟演示。

最终展示应按“真实消息链路、管理台 traceId、LoRA/RAG/AWQ 对照实验、可靠性与安全设计”展开。这样呈现的是完整的 LLM 系统工程与研究能力，而不仅是聊天机器人。