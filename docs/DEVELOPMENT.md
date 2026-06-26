# 开发说明（DEVELOPMENT）

本文档面向 `qqchat-enhanced` 项目的开发者，介绍开发环境搭建、项目架构、核心模块实现、配置系统、数据库结构、代码规范、测试与部署注意事项。所有内容均基于仓库实际代码编写，不涉及未实现的功能。

---

## 目录

1. [概述与技术栈](#1-概述与技术栈)
2. [开发环境搭建](#2-开发环境搭建)
3. [项目架构](#3-项目架构)
4. [核心模块说明](#4-核心模块说明)
5. [配置系统](#5-配置系统)
6. [数据库表结构概览](#6-数据库表结构概览)
7. [代码规范](#7-代码规范)
8. [测试](#8-测试)
9. [部署注意事项](#9-部署注意事项)

---

## 1. 概述与技术栈

`qqchat-enhanced` 是一个以 Qwen2.5-7B-Instruct-AWQ（4bit 量化）为基础模型、支持 LoRA 多适配器热切换、RAG 知识库增强、NoneBot2 QQ 机器人接入的一体化对话系统，前端为 Next.js 管理面板，后端为 FastAPI 服务。

### 1.1 前端技术栈

- **Next.js 16（App Router）** + **React 19** + **TypeScript**
- **Tailwind CSS v4** + **shadcn/ui** 组件库
- 开发端口 `5000`，生产构建后通过 `next start -p 5000` 启动
- 前端通过 `/api/*` 路径代理到后端 `:8000`

### 1.2 后端技术栈

- **Python 3.12** + **FastAPI** + **Pydantic**（请求/响应模型定义在 `backend/db/models.py`）
- **vLLM** OpenAI 兼容 API 推理（`backend/inference/vllm_client.py`），支持多实例负载均衡、熔断与 LoRA 动态切换
- **NoneBot2** QQ 机器人框架（`backend/bot/bot.py`）
- **SQLite（WAL 模式）** 作为默认持久化（`backend/db/database.py`），支持线程本地连接复用
- **Redis 缓存**（可选，`backend/cache/`）：系统配置缓存、知识库统计缓存、语义缓存、消息队列
- **Faiss 向量检索** + **BM25** 混合检索 + **Cross-Encoder 精排**（`backend/knowledge/rag_helper.py`）
- **PEFT / TRL / bitsandbytes** LoRA 训练（`backend/training/trainer.py`）

### 1.3 认证与安全

- **JWT（HS256，24 小时有效期）** + **X-API-Key** 双模式认证
- 密码使用 **bcrypt** 哈希存储
- JWT 携带 `jti`，登出时加入吊销黑名单
- 登录成功后通过 **httpOnly Cookie** 下发 Token
- 安全中间件 `backend/middleware/security.py`：白名单放行、限流、Prompt 注入检测

---

## 2. 开发环境搭建

### 2.1 前端开发环境

依赖 **Node.js 22** 与 **pnpm**（CI 中使用 `pnpm/action-setup@v4` + `actions/setup-node@v4` node-version 22）。

```bash
# 在项目根目录
pnpm install
pnpm dev        # 等价于 next dev -p 5000，开发服务器监听 http://localhost:5000
```

`package.json` 中关键脚本：

| 脚本 | 命令 | 说明 |
| --- | --- | --- |
| `dev` | `next dev -p 5000` | 启动开发服务器（端口 5000） |
| `build` | `next build` | 生产构建 |
| `start` | `next start -p 5000` | 启动生产服务器 |
| `lint` | `next lint` | ESLint 检查 |
| `ts-check` | `tsc --noEmit` | TypeScript 类型检查 |

### 2.2 后端开发环境

依赖 **Python 3.12**。在 `backend/` 目录下：

```bash
# 安装依赖（GPU 环境）
pip install -r requirements.txt

# 启动 FastAPI 服务（默认 :8000）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **注意**：CI 环境无 GPU，需先安装 CPU 版 PyTorch：
> ```bash
> pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
> ```
> 并从 `requirements.txt` 中剔除 `vllm/torch/torchvision/torchaudio` 后再安装其余依赖。

### 2.3 vLLM 推理服务

vLLM 作为独立进程运行，提供 OpenAI 兼容 API（默认端口 `:8001`）。后端通过 `VLLMClient`（`backend/inference/vllm_client.py`）以 httpx 异步客户端访问，**不依赖 openai SDK**。

- 基础模型：`Qwen2.5-7B-Instruct-AWQ`（4bit 量化，需 `--quantization awq`）
- 量化推理需 `--dtype float16`
- 多 LoRA 适配器通过 `--enable-lora` 与 `--lora-modules` 注册，运行时通过请求中的 `model` 字段切换

### 2.4 NoneBot2 机器人

机器人由 `backend/bot/bot.py` 实现，独立于 FastAPI 进程运行。机器人读取 SQLite 配置表中的配置项（通过 `Config` 类的 `@property` 动态读取，30 秒缓存），因此设置页修改后约 30 秒内自动生效，无需重启。

### 2.5 Redis（可选）

Redis 用于缓存与黑名单。若未启用 Redis，相关缓存逻辑会优雅降级（`backend/cache/redis_client.py` 提供降级实现）。本地开发可不部署 Redis。

---

## 3. 项目架构

### 3.1 顶层目录结构

```
qqchat-enhanced/
├── src/                    # 前端 Next.js App Router 源码
│   └── app/                # 路由页面（page.tsx / DashboardClient.tsx 等）
├── backend/                # 后端 Python 源码
│   ├── api/                # FastAPI 路由层（auth/generate/messages/knowledge/...）
│   ├── app/                # 应用入口与依赖（main.py / dependencies.py / config.py）
│   ├── bot/                # NoneBot2 机器人（bot.py）
│   ├── cache/              # 缓存层（redis_client / config_cache / semantic_cache / message_queue）
│   ├── db/                 # 数据层（database.py / models.py / adapter.py / pg_database.py）
│   ├── inference/          # 推理客户端（vllm_client.py）
│   ├── infra/              # 基础设施（circuit_breaker.py 熔断器）
│   ├── interfaces/         # 接口抽象（InferenceInterface 等）
│   ├── knowledge/          # RAG 知识库（rag_helper.py / vector_db.py / reranker.py）
│   ├── middleware/         # 中间件（security.py）
│   ├── training/           # LoRA 训练（trainer.py）
│   ├── loras/              # LoRA 适配器目录（自动扫描）
│   └── qq_assistant.db     # SQLite 数据库文件
├── docs/                   # 文档目录
├── .github/workflows/ci.yml # CI 流水线
├── package.json            # 前端依赖与脚本
└── README.md
```

### 3.2 分层说明

| 层 | 目录 | 职责 |
| --- | --- | --- |
| 路由层 | `backend/api/` | FastAPI 路由，处理 HTTP 请求与响应 |
| 应用层 | `backend/app/` | 应用入口（`main.py` 注册路由、CORS、安全中间件、`/health` `/ready`）、依赖注入（`dependencies.py` 的 `get_current_user`）、JWT 配置（`config.py`） |
| 业务/机器人 | `backend/bot/` | NoneBot2 机器人，动态配置、消息去重、LoRA 系统提示词 |
| 缓存层 | `backend/cache/` | Redis 客户端、配置/知识库统计缓存、语义缓存、消息队列 |
| 数据层 | `backend/db/` | SQLite 访问（`database.py`）、Pydantic 模型（`models.py`）、PostgreSQL 适配（`pg_database.py`）与统一适配器（`adapter.py`） |
| 推理层 | `backend/inference/` | vLLM OpenAI 兼容客户端，多实例负载均衡与熔断 |
| 基础设施 | `backend/infra/` | 熔断器（`CircuitBreaker` / `DegradationMode`） |
| 接口抽象 | `backend/interfaces/` | 推理等模块的抽象接口，便于替换实现 |
| 知识库 | `backend/knowledge/` | RAG 两阶段检索（向量+BM25 粗排 → Cross-Encoder 精排） |
| 中间件 | `backend/middleware/` | 安全中间件（认证、限流、Prompt 注入检测） |
| 训练 | `backend/training/` | LoRA 训练（PEFT/TRL）与进度/温度回调 |

### 3.3 请求链路

前端请求 → Next.js `/api/*` 代理 → FastAPI（`backend/app/main.py`）→ `SecurityMiddleware`（认证/限流/注入检测）→ 路由层（`backend/api/*`）→ 业务逻辑 → 数据层 / 推理层 / 知识库 → 响应。

---

## 4. 核心模块说明

### 4.1 机器人动态配置（`backend/bot/bot.py`）

`Config` 类采用**环境变量为静态属性、数据库项为 `@property` 动态读取**的设计：

- **环境变量**：作为静态类属性读取，进程启动时确定，修改需重启。
- **数据库配置项**：通过 `@property` 装饰器动态读取 `db.config` 表，配合模块级缓存实现 30 秒刷新：

```python
_db_cfg_cache: Dict[str, Any] = {}
_db_cfg_cache_ts: float = 0.0

def _get_db_cfg() -> Dict[str, Any]:
    global _db_cfg_cache, _db_cfg_cache_ts
    now = time.time()
    if not _db_cfg_cache or now - _db_cfg_cache_ts > 30:
        _db_cfg_cache = _load_db_config()
        _db_cfg_cache_ts = now
    return _db_cfg_cache

class Config:
    """机器人配置 - 环境变量项为静态属性，数据库项通过 @property 动态读取（30秒缓存）"""
    @property
    def some_db_item(self): ...
```

这样设置页修改配置后，**约 30 秒内自动生效，无需重启机器人**。

**LORA_REGISTRY** 是角色系统提示词与 LoRA 路径的注册表，定义在 `bot.py` 中：

```python
LORA_REGISTRY = { ... }  # 每项含 system_prompt 与 path
LORA_NAMES = list(LORA_REGISTRY.keys())
```

机器人通过 `LORA_REGISTRY` 查找当前 LoRA 对应的系统提示词，并支持前缀匹配（数据库中名称可能是 `hutao_lora_7b`，而注册表中为 `hutao`）。消息去重采用 **Redis + 内存**双重机制。

> **注意缓存时长区分**：机器人侧内存缓存为 **30 秒**（`bot.py` 的 `_db_cfg_cache`），FastAPI 侧 Redis 配置缓存为 **60 秒**（`backend/cache/config_cache.py` 的 `CONFIG_CACHE_TTL`）。二者职责不同，请勿混淆。

### 4.2 RAG 注入（`backend/api/generate.py` + `backend/knowledge/rag_helper.py`）

生成接口 `/api/generate` 在调用 vLLM 前会通过 `RAGHelper` 检索知识库上下文，并将其拼接到用户消息中。当 vLLM 不可用时，回退到本地模型管理器。

`RAGHelper.retrieve_context()` 实现**两阶段检索**：

1. **第一阶段（粗排）**：`QueryExpander` 对查询进行扩展（原神领域同义词、区域关键词、领域关键词），生成最多 5 个变体查询；每个变体调用 `vector_db.hybrid_search()`（向量 + BM25 混合，`keyword_weight=0.3`）召回 `top_k * recall_multiplier` 个候选；多查询结果融合（取最大分）并叠加 `query_count` 加权与区域加权。
2. **第二阶段（精排）**：使用 Cross-Encoder 重排器（`get_reranker()`）对候选重新打分，取 `final_top_k`，最后做分数归一化。

`QueryExpander` 内置原神领域同义词表（胡桃/钟离/七七/魈等）、区域关键词表（璃月/蒙德/稻妻/须弥）与领域关键词表（角色/武器/玩法/剧情/系统）。检索结果带查询缓存（最大 100 条）。

### 4.3 vLLM 多 LoRA 与多实例（`backend/inference/vllm_client.py`）

- **多实例负载均衡**：`VLLMInstance` 数据类记录每个实例的 `base_url`、`weight`、连接数、成功率、平均响应时间等。支持两种策略：
  - `WEIGHTED_ROUND_ROBIN`：Nginx 平滑加权轮询，动态权重 = `基础权重 * 成功率 / (1 + 平均响应时间)`
  - `LEAST_CONNECTION`：最少连接数优先
- **熔断与健康检查**：实例连续失败 **3 次**标记为 `UNHEALTHY`，进入 **30 秒冷却**，冷却结束后自动尝试恢复（`try_recover()`）。成功请求会重置连续失败计数。
- **LoRA 动态切换**：通过 OpenAI 兼容请求中的 `model` 字段指定 LoRA 适配器名称，vLLM 侧通过 `--lora-modules` 注册的适配器热切换，无需重新加载模型。

底层依赖 `infra/circuit_breaker.py` 的 `CircuitBreaker` 与 `DegradationMode` 实现熔断降级。

### 4.4 LoRA 训练回调（`backend/training/trainer.py`）

训练基于 PEFT/TRL/bitsandbytes，使用两个自定义 `TrainerCallback`：

**ProgressCallback**（训练进度上报）：

```python
class ProgressCallback(TrainerCallback):
    """训练进度报告回调，将训练进度实时更新到任务管理器
    （基于 global_step/max_steps 计算 0-100 百分比）。"""

    def on_step_end(self, args, state, control, **kwargs):
        if self.progress_fn and state.max_steps > 0:
            progress = min(100, int(state.global_step / state.max_steps * 100))
            self.progress_fn(progress, state.global_step, state.max_steps)
        return control
```

进度通过 `progress_fn` 回调实时更新到训练任务记录，前端可轮询获取 0–100% 进度。

**GpuTemperatureCallback**（GPU 温度监控，防 BSOD）：

```python
class GpuTemperatureCallback(TrainerCallback):
    def __init__(self, max_temp=82.0, cooldown_temp=72.0,
                 cooldown_seconds=30, check_interval_steps=20):
        ...
```

- 每 `check_interval_steps`（默认 20）步检查一次 GPU 温度
- 当温度超过 `max_temp`（默认 82°C）时，暂停训练 `cooldown_seconds`（默认 30 秒）散热
- 当温度降至 `cooldown_temp`（默认 72°C）以下且已等待至少 15 秒时，提前恢复训练
- 主要用于防止笔记本 GPU 过热导致系统蓝屏

训练任务通过 `training_tasks` 表（见 [第 6 节](#6-数据库表结构概览)）记录 `task_id`、`status`、`progress`、`error_message` 等。

---

## 5. 配置系统

### 5.1 三级配置来源

1. **环境变量**：静态配置（如 JWT 密钥、模型路径），进程启动时读取，修改需重启。
2. **SQLite `config` 表**：运行时可修改的配置，通过设置页（`/api/config`）写入。
3. **缓存层**：减少高频读取的数据库压力。

### 5.2 JWT 配置（`backend/app/config.py`）

- `JWT_SECRET`：未设置环境变量时**自动生成**（每次重启变化，会导致旧 Token 失效，生产环境务必显式设置）
- `create_access_token()`：生成 JWT，24 小时有效期，携带 `jti`
- `verify_token()`：校验 JWT，并检查 `jti` 是否在吊销黑名单中

### 5.3 缓存策略（`backend/cache/config_cache.py`）

| 缓存键 | TTL | 说明 |
| --- | --- | --- |
| `cache:config` | **60 秒** | 系统配置缓存（FastAPI 侧） |
| `cache:knowledge_stats` | **30 秒** | 知识库统计缓存 |
| `cache:kb:*` | — | 知识库列表缓存（失效时批量清理） |

所有 TTL 均添加 **±10% 随机抖动**（`_ttl_with_jitter()`），防止大量缓存同时过期导致雪崩：

```python
def _ttl_with_jitter(ttl: int) -> int:
    jitter = int(ttl * random.uniform(-0.1, 0.1))
    return max(1, ttl + jitter)
```

配置更新后调用 `invalidate_config_cache()` 主动失效；知识库变更调用 `invalidate_knowledge_cache()`（同时清理 `cache:kb:*`）。

### 5.4 机器人侧缓存（`backend/bot/bot.py`）

机器人侧使用**进程内内存缓存**（非 Redis），TTL **30 秒**（`_db_cfg_cache`）。由于机器人是独立进程，无法直接共享 FastAPI 的 Redis 缓存，因此采用内存缓存 + 30 秒刷新的策略，使设置页修改在 30 秒内对机器人生效。

---

## 6. 数据库表结构概览

数据库初始化逻辑位于 `backend/db/database.py` 的 `SQLiteDB._init_database()`。SQLite 连接采用**线程本地复用**，并开启以下 PRAGMA 优化：

```python
PRAGMA journal_mode=WAL          # WAL 模式，提升并发读写
PRAGMA busy_timeout=5000         # 锁等待 5 秒
PRAGMA synchronous=NORMAL        # 平衡安全与性能
PRAGMA cache_size=-8000          # 8MB 缓存
PRAGMA foreign_keys=ON           # 开启外键约束
PRAGMA temp_store=MEMORY         # 临时表存内存
```

并为高频查询建立索引：`idx_messages_sessionId_createdAt ON messages(sessionId, createdAt)`。

### 6.1 表清单（共 13 张表）

| 表名 | 主要用途 | 主键 |
| --- | --- | --- |
| `messages` | 消息记录（含 sessionType/SessionId/UserId/message/reply/modelName/loraName/costTime/createdAt） | `id` (AUTOINCREMENT) |
| `loras` | LoRA 适配器元信息（name/description/status/style/trainedSteps/totalSteps） | `id` (TEXT) |
| `config` | 系统配置键值对（key/value） | `key` |
| `knowledge_bases` | 知识库（name/description/created_at/updated_at） | `id` (AUTOINCREMENT) |
| `knowledge_folders` | 知识库文件夹（knowledge_base_id/name，外键级联删除） | `id` |
| `knowledge_documents` | 知识库文档（title/content/category/knowledge_base_id/folder_id/sourceType/fileType/chunkCount） | `id` |
| `knowledge_chunks` | 知识库向量分块（documentId/chunkIndex/content/embedding，外键级联删除） | `id` |
| `users` | 用户表（username/password_hash/created_at，username 唯一） | `id` |
| `user_data` | 用户表单数据持久化（user_id/page_key/data_json，UNIQUE(user_id, page_key)） | `id` |
| `saved_dialogues` | 已保存对话（name/character_desc/style/dialogue_count/dialogues_json/turn_stats/scene_stats） | `id` |
| `session_settings` | 会话设置（sessionId/sessionType/sessionName/bot_enabled，bot_enabled 默认 1） | `sessionId` |
| `training_tasks` | 训练任务（task_id/lora_name/status/progress/error_message/config_json） | `task_id` |
| `claw_tools` | Claw 自定义工具（name/description/code/enabled，name 唯一） | `id` |

### 6.2 LoRA 自动扫描

`database.py` 模块加载时通过 `_scan_lora_dirs()` 扫描 `backend/loras/` 目录，将包含 `adapter_config.json` 的子目录（或其 `final/` 子目录）自动注册到 `LORA_DIR_MAP`。数据库初始化时：

- 若 `loras` 表为空，调用 `_init_default_loras()` 从磁盘扫描并写入（第一个默认 `active`，其余 `inactive`）
- 若已有数据，调用 `_cleanup_stale_loras()` 清理无对应文件的旧记录，并调用 `_sync_loras_from_disk()` 同步新增 LoRA

`_read_lora_metadata()` 从 `adapter_config.json` 读取 `rank`/`alpha`/训练步数等元信息，`adapter_model.safetensors` 文件大小用于计算 size 字段。

### 6.3 迁移兼容

`_init_database()` 中包含字段迁移逻辑，通过 `try/except sqlite3.OperationalError` 检测旧表是否缺少 `category`、`knowledge_base_id`、`folder_id` 等字段，缺失时执行 `ALTER TABLE ... ADD COLUMN`，保证旧数据库平滑升级。

---

## 7. 代码规范

### 7.1 后端（Python）

规范定义在 `backend/pyproject.toml` 的 `[tool.ruff]` 段：

| 配置项 | 值 | 说明 |
| --- | --- | --- |
| `target-version` | `py312` | 目标 Python 3.12 |
| `line-length` | `120` | 最大行宽 120 |
| `lint.select` | `E,W,F,I,UP,B,SIM,TCH` | 启用的规则集 |
| `lint.ignore` | `E501,B008,B905,SIM108` | 忽略的规则 |
| `isort.known-first-party` | `api,app,bot,cache,db,infra,inference,knowledge,middleware,training,interfaces` | 一方包识别 |

`E501`（行过长）被忽略，行宽由 `line-length=120` 软约束。建议在提交前运行 `ruff check` 与 `ruff format`。

### 7.2 前端（TypeScript/React）

规范定义在 `eslint.config.mjs`：

- 使用 `nextTs` 与 `nextVitals` 配置
- **禁用** `react-hooks/set-state-in-effect` 规则
- 通过 `ignores` 忽略 `backend/**` 目录（前端 ESLint 不检查后端代码）

CI 中通过 `pnpm ts-check`（`tsc --noEmit`）与 `pnpm lint`（`next lint`）双重检查。

### 7.3 提交前检查清单

- 后端：`ruff check backend/` + `ruff format --check backend/`
- 前端：`pnpm ts-check` + `pnpm lint`
- 类型与语法：确保无 `any` 滥用、无未使用导入

---

## 8. 测试

### 8.1 后端测试

- 测试目录：`backend/tests/`
- 配置在 `pyproject.toml` 的 `[tool.pytest.ini_options]`：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`asyncio_mode = "auto"` 表示异步测试无需显式 `@pytest.mark.asyncio` 装饰器。

运行测试：

```bash
cd backend
python -m pytest tests/ -v --tb=short
```

### 8.2 CI 流水线（`.github/workflows/ci.yml`）

CI 在 `push`/`pull_request` 到 `main` 分支时触发，包含三个 Job：

**frontend Job**（工作目录 `.`）：

1. `actions/checkout@v4`
2. `pnpm/action-setup@v4`
3. `actions/setup-node@v4`（node-version 22，缓存 pnpm）
4. `pnpm install`
5. `pnpm ts-check`
6. `pnpm lint`
7. `pnpm build`

**backend Job**（工作目录 `backend`）：

1. `actions/checkout@v4`
2. `actions/setup-python@v5`（python-version 3.12）
3. **安装 CPU-only 依赖**：先装 CPU 版 `torch/torchvision/torchaudio`，再用 `grep -v` 剔除 `vllm/torch*` 生成 `requirements-ci.txt` 后安装
4. **语法检查**：对核心模块执行 `python -m py_compile`，包括：
   - `app/main.py`、`app/config.py`
   - `db/adapter.py`、`db/pg_database.py`、`db/database.py`
   - `inference/vllm_client.py`
   - `cache/redis_client.py`、`cache/semantic_cache.py`、`cache/message_queue.py`
   - `infra/circuit_breaker.py`
   - `interfaces/__init__.py`
5. **运行测试**：`python -m pytest tests/ -v --tb=short`（失败不阻断，仅提示）

**docker Job**（仅在 `push` 到 `main` 时触发，依赖 frontend + backend）：

1. 构建后端镜像：`docker build --build-arg INSTALL_GPU_DEPS=false -t qqassistant-backend ./backend`（CI 无 GPU，禁用 GPU 依赖）
2. 构建前端镜像：`docker build -t qqassistant-frontend .`

### 8.3 本地测试建议

- GPU 相关模块（vLLM 推理、LoRA 训练）在 CI 中以 CPU-only 方式跳过，本地有 GPU 时需手动验证
- 测试数据库建议使用临时 SQLite 文件，避免污染开发库
- Redis 不可用时，缓存相关测试应能优雅跳过

---

## 9. 部署注意事项

### 9.1 AutoDL GPU 部署

项目主要面向 **AutoDL** GPU 实例部署，参考 `README.md` 中的部署说明：

- **CUDA**：推荐 CUDA 13 兼容镜像
- **环境变量**：需正确设置 `LD_LIBRARY_PATH` 等动态库路径，避免 vLLM/PyTorch 找不到 CUDA 库
- **模型路径软链接**：AutoDL 数据盘与系统盘分离，建议将模型权重放在数据盘并通过软链接挂载到代码期望的路径，兼顾容量与性能
- **`--workers 1`**：vLLM 推理服务建议单 worker 启动，避免多 worker 导致显存重复占用与 LoRA 适配器状态不一致

### 9.2 模型与量化

- 基础模型 `Qwen2.5-7B-Instruct-AWQ` 采用 **4bit AWQ 量化**
- vLLM 启动需指定 `--quantization awq` 与 `--dtype float16`
- LoRA 适配器目录 `backend/loras/` 会被自动扫描注册，新增适配器放入即可（需含 `adapter_config.json` 与 `adapter_model.safetensors`）

### 9.3 进程编排

生产环境通常运行以下进程：

| 进程 | 端口 | 说明 |
| --- | --- | --- |
| Next.js 前端 | `5000` | `pnpm start` 或 `next start -p 5000` |
| FastAPI 后端 | `8000` | `uvicorn app.main:app --port 8000`（生产去掉 `--reload`） |
| vLLM 推理 | `8001` | OpenAI 兼容 API，多 LoRA |
| NoneBot2 机器人 | — | 独立进程，连接 QQ |

前端通过 Next.js 的 `/api/*` 重写代理到后端 `:8000`，因此对外只需暴露前端端口 `5000`。

### 9.4 Redis

- 生产环境**建议部署 Redis**以启用配置缓存、知识库统计缓存、语义缓存与消息队列
- Redis 不可用时，系统应能优雅降级（`backend/cache/redis_client.py` 提供降级逻辑），但性能会下降
- JWT 吊销黑名单依赖 Redis，未启用 Redis 时登出后 Token 在过期前仍有效

### 9.5 数据库

- SQLite 默认文件路径：`backend/qq_assistant.db`
- WAL 模式下会产生 `qq_assistant.db-wal` 与 `qq_assistant.db-shm` 文件，备份时需一并复制
- 高并发场景可切换至 PostgreSQL（`backend/db/pg_database.py` + `backend/db/adapter.py` 提供适配）
- `PRAGMA busy_timeout=5000` 在锁冲突时等待 5 秒，避免频繁的 `database is locked` 错误

### 9.6 安全注意事项

- **务必显式设置 `JWT_SECRET` 环境变量**，否则每次重启会自动生成新密钥，导致所有已签发 Token 失效
- httpOnly Cookie 防止前端 JS 读取 Token，降低 XSS 窃取风险
- `SecurityMiddleware` 提供 Prompt 注入检测，生产环境应保持启用
- 用户密码使用 bcrypt 哈希，禁止明文存储
- 限流策略应在反向代理（如 Nginx）层与应用层双重配置

### 9.7 性能参考

参考 `README.md` 中的性能数据（具体数值以实际环境为准）：

- vLLM 推理吞吐量与显存占用取决于 batch size 与最大序列长度
- RAG 两阶段检索中，Cross-Encoder 精排是主要耗时点，可通过 `recall_multiplier` 控制候选数量平衡精度与延迟
- 配置缓存（60s）与知识库统计缓存（30s）显著降低数据库查询压力

---

## 附录：相关文档

- [API.md](./API.md) — 后端接口文档
- [USER_GUIDE.md](./USER_GUIDE.md) — 用户使用手册
- [README.md](../README.md) — 项目概览与 AutoDL 部署
