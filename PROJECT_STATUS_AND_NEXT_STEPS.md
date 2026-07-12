# 项目完成情况与下一步总指南

> 项目：QQChat Enhanced  
> 生成时间：2026-07-12  
> 使用方式：按“先恢复可控部署，再完成真实平台验收，最后补齐研究实验”的顺序推进。

## 1. 一句话现状

项目已经从单一 QQ 聊天程序扩展为具备多平台网关、LoRA、RAG、vLLM AWQ 推理、评估、偏好数据和管理台能力的 LLM 系统原型；本地测试和生产构建通过。但服务器目前无法从本机 SSH 连接，且服务器已部署版本落后于本地尚未提交的修复，因此还不能称为“完成生产部署”。

## 2. 已完成事项

以下项目已完成实现，或已经完成本地/服务器验证。

### 2.1 系统架构与多平台能力

- 已将 AstrBot 定位为消息平台网关，FastAPI 保留 LLM、RAG、LoRA、配置、历史与统计等核心能力。
- 已有 AstrBot 网关插件：`astrbot_plugins/qqchat_gateway`。
- 后端已具备统一平台消息入口、平台/会话/发送者维度、幂等去重、traceId 和会话隔离能力。
- 已规划 QQ、Telegram、企业微信、公众号和个人微信的独立开关与适配策略。
- 旧 NoneBot/NapCat 链路保留为迁移期回滚方案。

### 2.2 高并发、可靠性与安全基础

- 已实现或接入请求限流、队列、会话串行化、消息去重、熔断、超时和降级的基础设施。
- 已有 Redis 缓存、配置缓存、会话开关缓存及数据库降级路径。
- 已增加 AstrBot 内部接口 token、签名/nonce 相关配置、输入长度限制、原始事件体积限制、结构化 traceId 日志能力。
- 已有服务状态、指标、队列、模型/RAG 失败率等监控接口和管理台基础页面。

这些能力仍需在 PostgreSQL、持久 Redis 和真实平台压力下做最终验收，不能只凭代码存在就宣称完全生产可用。

### 2.3 LLM 研究与模型能力

- vLLM 已能加载 Qwen2.5-7B-Instruct-AWQ；此前服务器真实模型名为 `qwen2.5-7b-awq`。
- 已具备 LoRA 发现、管理、切换以及多 LoRA 路由的基础代码。
- 已具备 Faiss、BM25、混合检索、可选 reranker、知识库导入和意图训练基础能力。
- 已具备 Gold Set、生成指标、实验记录、量化基准接口、偏好对数据管理和 DPO/ORPO 准备能力。
- 为避免错误结论，真实量化比较已明确要求每种量化版本独立启动 vLLM。

### 2.4 已完成测试

本地已完成：

```text
后端核心测试：86 passed, 1 skipped
TypeScript：通过
ESLint：无 error，仍有既有 warning
Next.js 生产构建：通过
本地 API smoke 与 mock AstrBot 事件：通过
```

此前服务器已完成：

```text
FastAPI /health：healthy
FastAPI /ready：database=true, faiss=true
Redis：PONG
vLLM /v1/models：返回 qwen2.5-7b-awq
```

注意：这些是此前连接正常时的结果。当前 SSH 端口不可达，必须在服务器恢复后重新检查一次。

## 3. 当前未提交、未部署的本地改动

本地 `main` 与 `origin/main` 当前共同指向提交 `1082713`。以下修复尚未提交，也尚未部署到服务器：

- `backend/api/evaluation.py`：删除评估接口中已经不可达的旧逻辑，避免两套流程造成维护误判。
- `src/lib/api.ts`：为评估、实验、路由、偏好数据建立明确的前后端类型契约。
- `src/hooks/useEvaluation.ts`、`src/hooks/useExperiments.ts`、`src/hooks/usePreferences.ts`：使用统一类型，消除隐式 `any`。
- `src/app/experiments/page.tsx`、`src/app/preferences/page.tsx`：修复实验结果、筛选、导出和偏好采样的数据类型。
- `NEXT_STEPS_GUIDE.md`：部署和研究实验操作手册。
- `PROJECT_STATUS_AND_NEXT_STEPS.md`：本文件。

提交前复验：

```powershell
pnpm ts-check
pnpm lint
pnpm build
cd backend
py -3.12 -m pytest tests -q
```

建议提交信息：

```text
fix: tighten research API contracts and remove stale evaluation flow
```

## 4. 你现在需要亲自完成的事项

这些工作涉及账号、密码、扫码、服务器控制权或研究判断，不能安全地由代码代替。

### P0：账号与服务器安全

1. 轮换所有曾出现在聊天、终端历史或截图中的密码、token 和 SSH 凭据。
2. 服务器恢复后优先配置 SSH 密钥登录，关闭密码登录或至少禁用 root 密码远程登录。
3. 确认防火墙只放行 SSH、80、443；不要将 8000、8001、6379、5432 暴露到公网。
4. 将 `.env` 设置为仅服务器用户可读：`chmod 600 .env`。
5. 建立数据库和模型目录备份策略。

### P0：恢复并检查服务器

当前从本地连接服务器端口失败。你需要先确认 AutoDL/云平台实例处于运行状态，并检查：

```bash
nvidia-smi
uptime
df -h
free -h
ss -ltnp
```

恢复 SSH 后，先不要立即改配置；先记录当前版本、进程和日志：

```bash
cd /root/autodl-tmp/qqchat-enhanced
git rev-parse --short HEAD
git status --short
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
redis-cli -h 127.0.0.1 ping
curl -fsS http://127.0.0.1:8001/v1/models
```

### P0：提交、推送、部署本地修复

1. 在本地完成测试。
2. 提交并推送 GitHub。
3. 服务器拉取对应 commit。
4. 先备份 SQLite 数据库和 `.env`。
5. 仅重启 backend 与 frontend；不要无故重启正在工作的 vLLM。
6. 对 `/health`、`/ready`、登录、真实生成、历史查询做回归。

## 5. 从验证环境迁移到生产结构

当前的单机 `screen` 方式适合调试，不适合长期服务。目标架构是：

```text
Internet -> Nginx/Caddy -> Next.js 管理台 -> FastAPI
AstrBot -------------------------------> FastAPI 内部接口
FastAPI -> PostgreSQL + Redis + vLLM + FAISS/知识库
```

推荐依次完成：

1. 使用 `deploy/docker-compose.yml` 启动 PostgreSQL、Redis、backend、frontend、Nginx。
2. 配置 `ENVIRONMENT=production`、`DATABASE_URL`、`REDIS_URL`、`JWT_SECRET`、`ASTRBOT_INTEGRATION_TOKEN`、`ALLOWED_ORIGINS`。
3. 从 SQLite 导出并迁移可保留的数据；先做副本迁移和核对数量，不直接覆盖原库。
4. 确认 Redis 开启 AOF 持久化，PostgreSQL 有定期备份。
5. 将 vLLM、Redis、PostgreSQL 放入内部 Docker 网络，只让 Nginx 对公网开放。
6. 部署 HTTPS，并用真实域名设置 `ALLOWED_ORIGINS`。

在 PostgreSQL 迁移未完成前，不要把当前 SQLite 环境描述为生产数据库。

## 6. AstrBot 和真实平台验收

### QQ

1. 在 AstrBot 创建 OneBot/NapCat 适配器。
2. 将 NapCat 的反向 WebSocket 指向 AstrBot，而不是旧 NoneBot。
3. 配置 `qqchat_gateway` 的后端地址和共享 token。
4. 只允许 `@机器人`、`/ai`、`/chat` 触发群聊回复。
5. 依次验证私聊、群聊、重复 messageId、超长文本、缺 token 和后端超时。

### 个人微信

1. 使用测试号在 AstrBot 面板扫码登录。
2. 仅在测试成功后启用 `ASTRBOT_WECHAT_PERSONAL_ENABLED=true`。
3. 用另一个微信号做私聊，再用小群做 @ 触发测试。
4. 个人微信接入有稳定性和合规风险，不作为唯一生产渠道。

### 每个平台都必须留下的证据

- 一张平台侧收发截图。
- 一条对应的 `traceId`。
- 后端历史中的 `platform`、`adapter`、`conversationId`、`senderId`。
- 一次重复事件去重结果。
- 一次失败降级结果。

## 7. 保研展示最值得优先做的研究任务

不要同时开十个大坑。按下面顺序完成，得到可量化的证据。

### 阶段 A：数据与评测（第 1 周）

- 写 `dataset-card.md`。
- 清洗训练数据：去重、长度过滤、格式检查、对话级切分。
- 建立至少 100 条 Gold Set，覆盖角色一致性、RAG、拒答、安全、长对话。
- 定义人工评分 rubric。

交付物：数据卡、Gold Set、版本号、固定随机种子。

### 阶段 B：LoRA 对照实验（第 2 至 3 周）

- 用同一数据、同一 seed、同一 rank 比较 LoRA、DoRA、RSLoRA。
- 可选比较 NEFTune 和 sequence packing。
- 记录 loss、困惑度、吞吐、显存、adapter 大小、人工盲评。

交付物：配置 JSON、TensorBoard 曲线、对照表、失败案例。

### 阶段 C：RAG 可信性（第 4 至 5 周）

- 为 chunk 保存文档、章节、版本、导入时间和 hash。
- 在回答中展示引用和证据片段。
- 比较 vector、BM25、hybrid、hybrid+rereanker。
- 记录 Recall@5、MRR、nDCG、延迟、引用正确率和拒答率。

交付物：检索评测集、RAG 对照表、带引用的页面截图。

### 阶段 D：AWQ 与服务性能（第 6 周）

- 用独立 vLLM 进程比较 FP16/BF16、AWQ，以及可用的 8-bit/NF4 基线。
- 测量 VRAM、TTFT、tokens/s、P50/P95、并发下的错误率。
- 比较动态 LoRA 加载与 adapter merge。

交付物：版本化命令、硬件信息、性能表和结论。

### 阶段 E：偏好对齐与在线反馈（第 7 至 8 周）

- 人工构造 20 至 50 组 chosen/rejected 偏好对。
- 小规模尝试 DPO 或 ORPO。
- 用相同 Gold Set 对比 SFT-only 和偏好优化模型。
- 将负反馈放进人工审核队列，不自动拿生产对话训练。

交付物：偏好数据卡、评测表、人工盲评结论。

## 8. 最终验收标准

完成以下全部项目后，才可以写“可部署的多平台 LLM 系统”：

- PostgreSQL、持久 Redis、Nginx/HTTPS 和服务自动重启已部署。
- vLLM、Redis、PostgreSQL 不对公网暴露。
- QQ 至少一个真实平台已实现稳定收发；个人微信仅作为可选测试能力。
- 任意消息能通过 traceId 在 AstrBot、FastAPI、数据库记录中关联。
- LoRA、RAG、AWQ 至少各有一组真实、可复现、可解释的实验结果。
- 完成备份恢复演练。
- 真实用户流的登录、生成、历史、知识库、LoRA、监控、平台接入均通过。

## 9. 文档分工

- `README.md`：项目总说明、安装和接口文档。
- `OPTIMIZATION_STRATEGY.md`：高并发、高可靠、高安全、观测与部署原则。
- `LLM_RESEARCH_ENHANCEMENT_ROADMAP.md`：研究方向、实验设计和 10 周路线图。
- `NEXT_STEPS_GUIDE.md`：部署、AstrBot、数据和验收的具体操作步骤。
- `PROJECT_STATUS_AND_NEXT_STEPS.md`：本文件，记录当前完成状态和下一步优先级。

## 10. 建议你今天就做的顺序

1. 确认服务器实例和 SSH 服务恢复。
2. 轮换敏感凭据。
3. 提交本地已测试修复与两份指南文档。
4. 在服务器拉取新提交并做一次回归。
5. 开始准备数据卡和 100 条 Gold Set。
6. 再启动第一组 LoRA 对照实验。

这个顺序会先保证系统可控，再积累最能证明 LLM 能力的实验成果。