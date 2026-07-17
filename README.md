# QQChat Enhanced

QQChat Enhanced 是一个多平台 LLM 系统，专注于角色对话、知识接地回答、LoRA 适配和可复现的 LLM 实验。

系统以 AstrBot 作为平台网关，FastAPI 作为核心服务。支持 QQ/NapCat 和可扩展的 IM 平台、vLLM AWQ 推理、RAG、LoRA 训练与切换、实验追踪，以及 Next.js 管理控制台。

## 当前状态

- **基础模型**：`Qwen3-8B-Instruct`（含 AWQ 量化版本，已从 Qwen2.5-7B 迁移）
- **vLLM 服务**：`qwen3-8b-instruct-awq`，端口 8001，`--enforce-eager` 模式
- **后端**：FastAPI，端口 8000，回归测试 86 passed
- **前端**：Next.js 16，TypeScript 编译 0 错误，28 条路由
- **数据库**：26 张表（含 6 张 Phase A 评测表）
- **LoRA**：旧适配器（hutao/minamo/kisaki）已备份至 `loras/backup_qwen25/`，需基于 Qwen3-8B 重新训练

本项目是一个已验证的单服务器研究原型。PostgreSQL 迁移、持久化服务监督、真实 IM 账号接入在生产部署前仍需完成。

## 架构

```text
QQ / WeChat / Telegram
          |
       AstrBot
          |
  qqchat_gateway plugin
          |
      FastAPI core
   /       |        \
vLLM     RAG      PostgreSQL/Redis
          |
     Next.js console
```

技术栈：FastAPI v2.0.0 + Next.js 16 + vLLM 0.10.2 + FAISS 混合 RAG + 多 LoRA 路由 + DPO/ORPO + Gold Set 评估。

## 快速开始

### 本地验证

```powershell
pnpm ts-check
pnpm build
cd backend
py -3.12 -m pytest tests -q
py -3.12 -m scripts.local_smoke
```

### 服务器验证

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
redis-cli -h 127.0.0.1 ping
curl -fsS http://127.0.0.1:8001/v1/models
```

### 启动 vLLM 服务

```bash
# 使用 Qwen3-8B-AWQ（需 GPU 1 空闲）
bash scripts/lab-start-vllm-daemon.sh
```

## 文档导航

所有文档集中在 `docs/` 目录，按类别分目录组织：

### 核心文档（docs/architecture/）

| 文档 | 用途 |
| --- | --- |
| [Code Wiki](docs/architecture/CODE_WIKI.md) | **权威技术文档**：项目整体架构、模块职责、关键类与函数、依赖关系（1300+ 行结构化知识库） |
| [Optimization Strategy](docs/architecture/OPTIMIZATION_STRATEGY.md) | 性能、可靠性、安全、部署的工程优化执行基线（P0-P3 优先级原则） |

### 研究与实验（docs/research/）

| 文档 | 用途 |
| --- | --- |
| [Research and Learning Roadmap](docs/research/RESEARCH_AND_LEARNING_ROADMAP.md) | **合并文档**：项目定位、当前状态、9 项研究方向、10 周实施计划（含 Learn/Do/Deliver/Pass）、部署验收、学习资源、研究诚信 Guardrails |
| [Real vLLM Benchmark Report](docs/research/REAL_VLLM_BENCHMARK_REPORT.md) | 2026-07-14 RTX 3090 真实实验报告：Minamo/月社妃 LoRA 训练与评测、质量门禁、根因分析 |
| [Beginner Real LLM Experiment Guide](docs/research/BEGINNER_REAL_LLM_EXPERIMENT_GUIDE.md) | 面向初学者的实验操作指南：盲评、偏好审核、训练、挂载 vLLM、真实评测 |

### 数据与评测（docs/data/）

| 文档 | 用途 |
| --- | --- |
| [Dataset Card](docs/data/dataset-card.md) | QQChat Persona SFT 训练数据集卡片 v1.0：来源、预处理、分割、角色定义、版权 |
| [Human Scoring Rubric](docs/data/human-scoring-rubric.md) | Gold Set 105 条 prompt 的人工评分标准（5 分制，5 类别） |

### 子目录文档

| 文档 | 用途 |
| --- | --- |
| [AstrBot Gateway Plugin](astrbot_plugins/qqchat_gateway/README.md) | AstrBot 插件安装与环境变量配置 |
| [Character Dialogues](backend/data/character_dialogues/README.md) | 角色对话训练数据目录结构说明 |
| [Preference Review Guide](backend/data/character_dialogues/experiments/research/PREFERENCE_REVIEW_GUIDE.md) | 偏好数据人工审核操作指南（chosen/rejected 判定） |

## 仓库结构

```text
backend/                 FastAPI, 训练, RAG, 评测, 数据库（26 张表）
├── api/                 18 个 API 路由模块
├── inference/           vLLM 客户端 + LoRA 路由 + 适配器检查
├── training/            LoRA 训练器 + 任务管理 + 评估器
├── knowledge/           FAISS 向量库 + 重排序 + 纠正性 RAG
├── experiments/         消融实验 + 量化基准 + RAG 消融
├── evaluation/          Gold Set + 安全测试 + 角色基准
└── data/                训练数据 + 偏好对 + KB 种子
src/                     Next.js 管理控制台（14 页面, 12 Hook）
astrbot_plugins/         AstrBot 网关插件
deploy/                  Compose, Nginx, 服务器脚本, 实验运行器
scripts/                 vLLM 启动 + 实验脚本 + 盲评工具
gametext/                角色语料（纸上魔法使系列）
```

## LoRA 子系统

本项目包含完整的 LoRA 训练-推理-管理闭环：

- **训练**：PEFT/DoRA/RSLoRA/NEFTune/Packing 全栈微调，GPU 温度监控，异步任务管理，DB 持久化
- **推理**：双后端（vLLM + Transformers PEFT），熔断器、负载均衡、KV Cache 复用、语义缓存
- **路由**：基于关键词的 LoRA 路由器（BASE_CHAT / RAG / PERSONA 三态切换）
- **管理**：完整 REST API（CRUD + 扫描 + 激活 + 训练启停查）+ 前端可视化界面
- **兼容性**：adapter_checker 在加载前校验 7 项（config/base_model/target_modules/rank/peft_version/weights/tokenizer）

详见 [Code Wiki](docs/architecture/CODE_WIKI.md) 第十二章。

## 研究诚信规则

- **不得**将 mock 输出当作真实实验结果
- **不得**声称 `eval_accuracy=0.65`（历史占位值，非真实测量）
- 生成的偏好对以 `pending` 状态开始，需人工审核后才能用于 DPO/ORPO 训练
- 真实量化对比需为每个模型变体使用隔离的 vLLM 进程
- 每次实验必须同时保留：数据版本、种子、模型版本、命令、硬件、报告
- 至少 50 条 approved 偏好对才可进行 DPO pilot
- DPO/ORPO 不是 RLHF（基于参考模型的对比学习，非强化学习）

## 关键设计要点

- **单 GPU 单 vLLM 进程**：避免显存竞争
- **BACKEND_WORKERS=1**：避免 SQLite 并发问题
- **LoRA 单一 LORA_PATH**：所有 adapter 在同一根目录下管理
- **PostgreSQL 生产默认**：SQLite 仅用于开发
- **JWT/token 不入日志**：敏感信息脱敏
- **所有外部边界视为不可靠**：AstrBot、vLLM、IM 平台均需熔断与重试

## 模型迁移说明（2026-07-15）

项目已从 Qwen2.5-7B-Instruct 迁移到 Qwen3-8B-Instruct：

- 服务器路径：`/home/szw/lhm2/runtime/models/Qwen3-8B-Instruct-AWQ`
- vLLM 环境：`/home/szw/lhm2/envs/qqchat-gpu-qwen3/`（Python 3.11 + vLLM 0.10.2 + PyTorch 2.8.0+cu128 + transformers 4.57.6）
- 启动参数添加 `--enforce-eager`（绕过 Triton 编译 `-lcuda` 问题）
- 旧 LoRA 已备份，需基于 Qwen3-8B 重新训练

## License

详见 [LICENSE](LICENSE)。
