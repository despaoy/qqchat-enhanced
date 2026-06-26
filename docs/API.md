# QQ聊天增强系统 API 文档

> 后端基于 FastAPI (Python 3.12) 构建，版本号 `2.0.0`，应用入口位于 `backend/app/main.py`。
> 本文档基于后端实际路由代码编写，覆盖认证、消息、会话、知识库、训练、LoRA、模型、配置、工具等接口分组。

---

## 1. 概述

### 1.1 基础地址

| 环境 | 访问方式 |
| --- | --- |
| 生产/部署 | 前端通过 Next.js 路由 `/api/*` 代理到后端 FastAPI 服务（默认监听 `:8000`） |
| 本地开发 | 后端直连 `http://localhost:8000`，前端 `http://localhost:3000` |

后端已在 `main.py` 中为以下来源开启 CORS：`http://localhost:3000`、`http://localhost:5000`、`http://127.0.0.1:3000`、`http://127.0.0.1:5000`（`allow_credentials=True`）。

### 1.2 根与健康检查

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/` | 服务信息（名称/版本/状态） | 否 |
| GET | `/health` | 存活探针，返回 `healthy` + 时间戳 | 否 |
| GET | `/ready` | 就绪探针，检查数据库与 Faiss 向量索引 | 否 |

`/ready` 在数据库或 Faiss 不可用时返回 `503`，响应体含 `deps` 与 `details`。

### 1.3 全局异常

应用注册了全局异常处理器 `@app.exception_handler(Exception)`，未捕获异常统一返回：

```json
{ "success": false, "error": "Internal Server Error", "message": "服务器内部错误" }
```

---

## 2. 认证机制

系统采用 **JWT + X-API-Key 双模式** 认证，由 `middleware/security.py` 的 `SecurityMiddleware` 统一处理，业务路由再通过 `app/dependencies.py` 的 `get_current_user` 依赖二次校验。

### 2.1 双模式说明

| 模式 | 凭证来源 | 用途 |
| --- | --- | --- |
| JWT | `Authorization: Bearer <token>` 或 httpOnly Cookie `access_token` | 前端用户登录态（主要方式） |
| X-API-Key | 请求头 `X-API-Key` | 服务间/脚本调用（Key 列表来自环境变量 `API_KEYS`，逗号分隔） |

认证顺序：白名单 → 公开只读端点 → 优先校验 JWT → 再校验 X-API-Key → 均失败返回 `401`。

### 2.2 JWT 细节

- 算法：`HS256`，有效期 `24` 小时（`JWT_EXPIRY_HOURS`）。
- 密钥：优先读环境变量 `JWT_SECRET`（长度 ≥32 且非默认值）；缺失时自动生成安全密钥并持久化到 `backend/.env`。
- Payload 字段：`sub`(用户名)、`user_id`、`exp`、`iat`、`jti`(唯一 ID，用于吊销)。
- Cookie：登录/注册成功后通过 `access_token` 写入，`httpOnly=True`、`samesite=lax`、`path=/`、`max_age=86400`；生产环境（`ENVIRONMENT=production`）启用 `Secure`。
- 吊销：登出时将 `jti` 加入内存黑名单（TTL 为 Token 剩余寿命，服务重启清空，上限 10000 条）。

### 2.3 认证白名单与公开端点

白名单路径（无需认证）：

```
/ 、 /health、 /ready、 /docs、 /openapi.json、 /api/auth/login、 /api/auth/register
```

公开只读端点（`GET` 免认证）：

```
/api/stats、 /api/stats/activity、 /api/stats/services、 /api/model/status、 /api/vllm/status
```

`OPTIONS`（CORS 预检）一律放行。

### 2.4 鉴权失败响应

```json
HTTP/1.1 401 Unauthorized
{ "detail": "缺少认证凭证，请提供 X-API-Key 或 Authorization: Bearer <key>" }
```

`WWW-Authenticate: Bearer` 头随之返回。Token 过期/无效/已注销返回 `401`，detail 分别为：`Token 已过期，请重新登录`、`Token 无效`、`Token 已注销，请重新登录`。

---

## 3. 通用约定

### 3.1 请求

- `Content-Type: application/json`（文件上传除外，使用 `multipart/form-data`）。
- 字段命名：请求体多为 camelCase（与前端一致，如 `sessionId`、`loraName`），部分训练/知识库模型使用 snake_case（如 `dataset_name`、`knowledge_base_id`），以各接口字段表为准。

### 3.2 响应

成功响应一般为 JSON，常含 `success: true`。列表接口多返回 `total`/`total_all` 等计数。生成类接口返回 `GenerateResponse`：

```json
{ "reply": "<回复文本>", "model": "vllm/Qwen/Qwen2.5-7B-Instruct", "costTime": 1.23 }
```

### 3.3 错误码

| HTTP 状态码 | 含义 | 触发场景示例 |
| --- | --- | --- |
| 400 | 请求参数错误 | 无效模型配置、与内置工具重名、沙箱代码为空 |
| 401 | 未认证 / Token 失效 | 缺少凭证、Token 过期或已注销 |
| 403 | 禁止访问 | 沙箱检测到危险 token（`import os`、`open(` 等） |
| 404 | 资源不存在 | 消息/文档/LoRA/训练任务/数据集不存在 |
| 409 | 冲突 | 用户名已存在、知识库名已存在、已有生成任务运行中 |
| 413 | 实体过大 | ZIP 上传超过 100MB 限制 |
| 422 | 输入验证失败 | 字段长度/类型不合规（返回 `errors` 详情） |
| 429 | 限流 | 请求频率超限（`RateLimitMiddleware` 或生成接口 `rate_limiter`） |
| 500 | 服务器内部错误 | 推理失败、数据库异常（生成接口对客户端返回通用消息，详情写日志） |
| 503 | 服务不可用 | 信号量获取超时、向量数据库不可用、就绪探针失败 |
| 507 | 存储不足 | 训练前 GPU 显存 <8GB 或系统内存 <16GB |

限流配置（环境变量，默认值）：全局 `RATE_LIMIT_RPM=300` / `RATE_LIMIT_TPM=500000`，推理 `GENERATE_RPM=60` / `GENERATE_TPM=500000`，请求体 `MAX_BODY_SIZE=1MB`，`PROMPT_MAX_LENGTH=10000`。

---

## 4. 认证接口（Auth）

路由文件：`backend/api/auth.py`

### 4.1 注册

`POST /api/auth/register`

请求体（`RegisterRequest`）：

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| username | string | 2–50 字符 | 用户名 |
| password | string | 8–100 字符 | 密码（bcrypt 哈希存储） |

响应（同时写入 httpOnly Cookie `access_token`）：

```json
{
  "success": true,
  "user": { "id": 1, "username": "alice", "created_at": "2026-06-26 10:00:00" }
}
```

错误：`409 用户名已存在`、`500 注册失败`。

### 4.2 登录

`POST /api/auth/login`

请求体（`LoginRequest`）：`username`、`password`。

响应同注册，成功后写入 Cookie。错误：`401 用户名或密码错误`。

### 4.3 登出

`POST /api/auth/logout`

将当前 Token（Cookie 或 Authorization 头）加入黑名单并清除 Cookie。

```json
{ "success": true }
```

### 4.4 获取当前用户

`GET /api/auth/me`（需鉴权）

```json
{
  "success": true,
  "user": { "id": 1, "username": "alice", "created_at": "2026-06-26 10:00:00" }
}
```

---

## 5. 消息生成接口（Generate）

路由文件：`backend/api/generate.py`。优先使用 vLLM 高并发推理，失败回退到模型管理器；带响应缓存（Redis，TTL 300s）、限流、输入验证、熔断与故障转移。

### 5.1 生成回复

`POST /api/generate`（需鉴权）

请求体（`MessageRequest`）：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| message | string | — | 用户消息 |
| sessionType | string | `private` | 会话类型（`private`/`group`） |
| sessionId | string | `""` | 会话 ID |
| userId | string | `""` | 用户 ID |
| userName | string | `""` | 用户名 |
| loraName | string | `""` | 指定 LoRA 名称；为空则用当前激活的 LoRA |

响应（`GenerateResponse`）：

```json
{ "reply": "你好呀～", "model": "vllm/Qwen/Qwen2.5-7B-Instruct", "costTime": 1.85 }
```

行为说明：

- LoRA 名称映射：数据库 `hutao_lora_7b`→vLLM `hutao`，`minamo_lora`→`minamo`；调用前会查询 vLLM 可用 LoRA 列表，不存在则降级为基础模型。
- RAG：当设置页 `useKnowledgeBase` 开启且意图检测判定需要检索时，按预测的知识库名过滤检索 top3，注入到 user 消息【背景设定】中，并把温度降到 ≤0.5。
- 模型参数从数据库 config 表实时读取（`temperature`、`maxTokens`）。
- 错误：`429 请求过于频繁`、`422 输入验证失败`、`503 服务繁忙`、`500 生成回复失败，请稍后重试`（内部异常详情写日志，不回传客户端）。

### 5.2 vLLM 状态

`GET /api/vllm/status`（公开只读）

```json
{ "enabled": true, "instances": [ { ...健康检查结果 } ] }
```

未启用时返回 `{ "enabled": false, "instances": [] }`。

### 5.3 增强生成（可选）

`POST /api/generate/v2`（需鉴权）—— 仅当环境变量 `PIPELINE_ENABLED=true` 且 `pipeline` 模块可导入时注册。使用统一消息管道（请求合并 + 有界队列 + 优雅降级）。

- 队列中：返回 `{ "reply": "您的消息已排队处理中...", "model": "queued", "costTime": 0, "meta": { "queue_position": N, "estimated_wait": X } }`。
- 被拒绝：`503 { "message": ..., "queue_position": 0 }`。

---

## 6. 消息记录接口（Messages）

路由文件：`backend/api/messages.py`

### 6.1 获取消息列表

`GET /api/messages`（需鉴权）

查询参数：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| search | string | — | 关键词搜索 |
| sessionType | string | — | 会话类型过滤（`all` 表示全部） |
| lora | string | — | LoRA 名称过滤（`all` 表示全部） |
| sessionId | string | — | 指定会话 ID |
| limit | int | 100 | 1–1000 |
| offset | int | 0 | 分页偏移 |

```json
{ "messages": [ ... ], "total": 80, "total_all": 1024 }
```

> 过滤在 SQL 层完成（`get_messages_filtered`），`total` 为本页返回数，`total_all` 为全表计数。

### 6.2 删除单条消息

`DELETE /api/messages/{msg_id}`（需鉴权）

```json
{ "success": true, "message": "删除成功" }
```

错误：`404 消息不存在`。

### 6.3 批量删除消息

`DELETE /api/messages/batch`（需鉴权）

请求体（`BatchDeleteRequest`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| search | string? | 关键词 |
| sessionType | string? | 会话类型 |
| lora | string? | LoRA 名称 |
| sessionName | string? | 会话名称 |

```json
{ "success": true, "deleted": 42, "message": "已删除 42 条记录" }
```

---

## 7. 会话管理接口（Sessions）

> 会话接口实现在 `backend/api/messages.py` 中，按 `sessionId` 聚合统计。

### 7.1 获取会话聚合统计

`GET /api/sessions`（需鉴权）

```json
{ "sessions": [ { "sessionId": "...", ...聚合字段 } ] }
```

### 7.2 切换会话机器人开关

`PUT /api/sessions/bot-toggle`（需鉴权）

请求体（`SessionBotToggle`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| sessionId | string | 会话 ID |
| enabled | bool | 是否启用机器人 |

```json
{ "success": true, "sessionId": "grp_123", "botEnabled": true }
```

---

## 8. 知识库接口（Knowledge）

路由文件：`backend/api/knowledge.py`。包含知识库/文件夹/文档 CRUD、ZIP 上传、目录扫描导入、混合检索、意图分类器训练。

### 8.1 知识库管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/knowledge/bases` | 列出所有知识库 |
| POST | `/api/knowledge/bases` | 创建知识库（`KnowledgeBaseCreate`：`name` 1–100、`description`） |
| PUT | `/api/knowledge/bases/{kb_id}` | 更新知识库（`KnowledgeBaseUpdate`） |
| DELETE | `/api/knowledge/bases/{kb_id}` | 删除知识库（级联删除文件夹与文档） |

创建冲突返回 `409 知识库名称已存在`；不存在返回 `404 知识库不存在`。

### 8.2 文件夹管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/knowledge/bases/{kb_id}/folders` | 列出知识库下文件夹 |
| POST | `/api/knowledge/bases/{kb_id}/folders` | 创建文件夹（`KnowledgeFolderCreate`） |
| DELETE | `/api/knowledge/folders/{folder_id}` | 删除文件夹 |

### 8.3 文档管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/knowledge/documents` | 文档列表（查询参数：`limit`、`offset`、`category`、`knowledge_base_id`、`folder_id`），同时返回 `stats` |
| GET | `/api/knowledge/documents/{doc_id}` | 获取单个文档及其分块 `chunks` |
| POST | `/api/knowledge/documents` | 创建文档（`KnowledgeDocumentCreate`），自动分块 + 路径注入 + 写入向量库 |
| PUT | `/api/knowledge/documents/{doc_id}` | 更新文档（`KnowledgeDocumentUpdate`），内容变更时重新分块并更新向量库 |
| DELETE | `/api/knowledge/documents/{doc_id}` | 删除文档（同步从向量库移除） |

`KnowledgeDocumentCreate` 主要字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| title | string | 标题 |
| content | string | 正文 |
| category | string | 分类（默认 `未分类`） |
| knowledge_base_id | int? | 所属知识库 ID |
| folder_id | int? | 所属文件夹 ID |
| sourceType | string | 来源类型（默认 `text`） |
| sourceUrl / fileType / fileSize | — | 可选元信息 |

> 文档创建/更新时会用 `knowledge.text_splitter.simple_text_split` 分块，并把 `[知识库名/文件夹名] 标题: 内容` 作为检索文本写入向量库。

### 8.4 ZIP 上传

`POST /api/knowledge/bases/{kb_id}/upload-zip`（需鉴权，`multipart/form-data`，字段 `file`）

- 上限 100MB，超出返回 `413`。
- ZIP 内顶层目录名作为文件夹名，其下 `.txt/.md/.json` 作为文档；根目录文件归入「未分类」。
- 自动分块并写入向量库，支持 utf-8/gbk 编码回退。

```json
{
  "success": true,
  "message": "成功导入 12 个文档到 3 个文件夹",
  "createdFolders": ["角色", "事件"],
  "createdDocs": 12,
  "errors": []
}
```

### 8.5 目录扫描与导入

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/knowledge/scan` | 扫描 `backend/knowledge_bases/` 下子目录树（支持 `.txt/.md/.json/.csv/.html/.xml`） |
| POST | `/api/knowledge/scan/import` | 将扫描目录导入知识库；查询参数 `directory_name`（必填）、`kb_id`（可选，为空则自动新建） |

### 8.6 知识库搜索

`POST /api/knowledge/search`（公开，无需鉴权）

请求体（`KnowledgeSearchRequest`）：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| query | string | — | 查询文本 |
| topK | int | 5 | 返回条数 |
| knowledgeBaseName | string? | — | 按知识库名称过滤 |

检索链路（逐级回退）：RAGHelper 两阶段（向量+BM25 混合 → Cross-Encoder 精排）→ 向量库 `hybrid_search` → 关键词匹配。

```json
{
  "success": true,
  "query": "胡桃的技能",
  "results": [
    {
      "documentId": 7, "documentTitle": "胡桃", "chunkIndex": 0,
      "content": "...", "score": 0.92, "searchType": "rag_pipeline"
    }
  ],
  "searchType": "rag_pipeline"
}
```

`searchType` 取值：`rag_pipeline` / `hybrid` / `keyword`。首次搜索会延迟重建 Faiss 索引（从数据库加载 chunks）。

### 8.7 统计

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/knowledge/stats` | 知识库统计（需鉴权） |
| GET | `/api/vector/stats` | 向量数据库统计（需鉴权，向量库不可用时 `503`） |

### 8.8 意图分类器训练

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/knowledge/train-intent/generate` | 启动样本生成（LLM 基于知识库文档生成，参数：`kb_ids`、`samples_per_kb=100`、`negative_count=200`、`lora_name`） |
| GET | `/api/knowledge/train-intent/generate/status` | 样本生成进度 |
| GET | `/api/knowledge/train-intent/samples` | 获取全部样本 |
| PUT | `/api/knowledge/train-intent/samples` | 编辑单条样本（`label`/`index`/`text`） |
| DELETE | `/api/knowledge/train-intent/samples` | 删除单条样本（查询参数 `label`、`index`） |
| PATCH | `/api/knowledge/train-intent/samples` | 批量保存（覆盖写入，`samples`） |
| POST | `/api/knowledge/train-intent/samples` | 添加单条样本 |
| POST | `/api/knowledge/train-intent` | 训练多分类模型（参数 `kb_ids`） |
| GET | `/api/knowledge/train-intent/status` | 训练进度 |
| POST | `/api/knowledge/train-intent/cancel` | 取消训练/生成 |
| GET | `/api/knowledge/train-intent/model` | 当前模型信息 |
| GET | `/api/knowledge/train-intent/active-kbs` | 参与检索的知识库 |
| POST | `/api/knowledge/train-intent/active-kbs` | 设置参与检索的知识库（`kb_ids`） |

> 上述接口均需鉴权。运行中重复触发返回 `{ "success": false, "error": "..." }`。

---

## 9. 训练接口（Training）

路由文件：`backend/api/training.py`。包含数据集管理、LoRA 训练、对话数据生成与已保存对话管理。

### 9.1 数据集管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/training/datasets` | 列出可用数据集（读取各目录 `dataset_info.json`） |
| POST | `/api/training/datasets` | 创建数据集（`DatasetUploadRequest`：`dataset_name`、`style?`、`custom_prompt?`、`data`） |
| GET | `/api/training/datasets/{dataset_name}/export` | 导出为 ZIP 下载（中文文件名 RFC 5987 编码） |
| GET | `/api/training/datasets/scan` | 扫描文件夹发现数据集（查询参数 `folder?`） |
| POST | `/api/training/datasets/scan/import` | 从扫描结果导入（`ImportDatasetRequest`：`source_path`、`dataset_name?`，路径须在 backend 或 `/root/autodl-tmp` 下） |
| GET | `/api/training/styles` | 列出预定义人物风格 |
| GET | `/api/training/models` | 列出多 GPU 训练配置（来自 `ALL_GPU_CONFIGS`，区分 RTX 3090 24GB / RTX 4060 8GB） |

### 9.2 启动训练

`POST /api/training/start`（需鉴权）

请求体（`TrainingStartRequest`）：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| lora_name | string | — | LoRA 名称 |
| dataset_name | string | — | 数据集名称 |
| model_type | string | `qwen2.5-7b` | GPU 配置名（须在 `ALL_GPU_CONFIGS` 中） |
| custom_config | object? | — | 自定义配置，覆盖基础配置 |

```json
{ "success": true, "message": "训练任务已启动", "task_id": "task_xxx" }
```

错误：`404 数据集不存在`、`400 无效的模型配置`、`422 输入验证失败`、`507 显存/内存不足`（提示导出数据集到服务器训练）。

### 9.3 训练任务管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/training/tasks` | 列出所有训练任务 |
| GET | `/api/training/tasks/{task_id}` | 获取任务状态（不存在 `404`） |
| POST | `/api/training/tasks/{task_id}/cancel` | 取消训练任务（无法取消返回 `400`） |

### 9.4 对话数据生成

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/training/generate-dialogues` | 基于角色描述生成对话（`DialogueGenerateRequest`：`character_description`、`num_dialogues=10`、`style?`、`custom_prompt?`），内部含轮次分布策略与场景类型，附网络搜索角色背景 |
| POST | `/api/training/generate-dialogues/cancel` | 取消生成 |
| GET | `/api/training/generate-dialogues/progress` | 获取进度（含 `new_dialogues` 增量推送与 `all_generated_dialogues`） |
| POST | `/api/training/generate-dialogues/force-reset` | 强制重置生成状态（断线重连清理） |

`generate-dialogues` 响应：

```json
{
  "success": true,
  "dialogues": [ { "conversations": [...], "system": "...", "scene": "日常问候", "turns": 3, "tags": ["3轮"] } ],
  "total": 10,
  "cost_time": 12.34,
  "cancelled": false
}
```

并发控制：同一时刻仅允许一个生成任务（`generation_state_lock`），重复触发返回 `409 已有生成任务正在运行`。模型为 mock 模式时返回 `400`。

### 9.5 已保存对话管理

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/training/saved-dialogues` | 列出已保存对话（含 `turn_stats`/`scene_stats`） |
| POST | `/api/training/saved-dialogues` | 保存对话（`SaveDialoguesRequest`） |
| GET | `/api/training/saved-dialogues/{item_id}` | 获取单条（含完整 `dialogues`） |
| DELETE | `/api/training/saved-dialogues/{item_id}` | 删除 |
| DELETE | `/api/training/saved-dialogues/{item_id}/dialogues/{dialogue_index}` | 删除单条对话 |
| POST | `/api/training/saved-dialogues/{item_id}/create-dataset` | 从已保存对话创建训练数据集（查询参数 `dataset_name?`） |

---

## 10. LoRA 适配器接口（Loras）

路由文件：`backend/api/loras.py`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/loras` | 获取 LoRA 列表（查询参数 `status?`） |
| POST | `/api/loras/scan` | 扫描 `backend/loras/` 目录，自动发现并注册新适配器（读取 `adapter_config.json`，支持 `final/` 子目录），更新已有记录的 size/步数 |
| PUT | `/api/loras/{lora_id}/status` | 更新状态（请求体 `{ "status": "active" }`，激活/停用） |
| DELETE | `/api/loras/{lora_id}` | 删除 LoRA（不存在 `404`） |

`scan` 响应示例：

```json
{ "success": true, "message": "发现 2 个新 LoRA，更新 1 个记录", "new_count": 2, "updated_count": 1 }
```

---

## 11. 模型接口（Models）

路由文件：`backend/api/models.py`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/models` | 列出所有可用模型 |
| GET | `/api/models/check/{model_name}` | 检查模型是否已下载 |
| POST | `/api/models/download` | 下载模型（`ModelDownloadRequest`：`model_name`、`force=false`） |
| DELETE | `/api/models/{model_name}` | 删除模型 |
| POST | `/api/models/check-7b` | 检查并自动下载 7B 模型（`qwen2.5-7b`） |

均需鉴权。

---

## 12. 配置接口（Config）

路由文件：`backend/api/config.py`。配置存于 SQLite `config` 表，经 Redis 缓存（`cache/config_cache.py`，TTL 60s），更新时使缓存失效。

### 12.1 系统配置

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/config` | 否 | 获取配置（缓存命中时 `"cached": true`） |
| PUT | `/api/config` | 是 | 更新配置（请求体为配置键值对象），更新后失效缓存并同步 OpenAI 兼容提供商（`openaiCompatBaseUrl`/`openaiCompatApiKey`/`openaiCompatModel`） |

常见配置项（由前端设置页写入）：`temperature`、`maxTokens`、`useKnowledgeBase`、`modelProvider`、`openaiCompatBaseUrl`、`openaiCompatApiKey`、`openaiCompatModel` 等。

PUT 请求示例：

```json
{ "temperature": 0.7, "maxTokens": 2048, "useKnowledgeBase": true }
```

```json
{ "success": true, "message": "配置已更新", "config": { ... } }
```

### 12.2 模型状态与提供商

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/model/status` | 否（公开只读） | 获取模型管理器状态（当前 provider、各 provider 状态） |
| PUT | `/api/model/provider` | 是 | 切换模型提供商（请求体 `{ "provider": "ollama" }`） |

可选 provider：`ollama`、`llama_cpp`、`openai_compat`、`transformers_peft`、`vllm`、`mock`。切换成功会写回 `modelProvider` 配置并失效缓存；无效 provider 返回 `400`。

---

## 13. 工具接口（Claw）

路由文件：`backend/api/claw.py`。Claw 为机器人可调用的工具系统，含 5 个内置工具（`status`/`show_tools`/`send_file`/`get_coderesult`/`write_code`）与自定义工具。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/claw/tools` | 列出全部工具（内置在前，自定义在后，含 `builtin` 标记） |
| POST | `/api/claw/tools` | 创建/更新自定义工具（`ToolSaveRequest`：`name`、`description`、`code`、`enabled`），不可与内置工具重名 |
| DELETE | `/api/claw/tools/{name}` | 删除自定义工具（内置工具不可删，返回 `400`） |
| POST | `/api/claw/tools/execute` | 受限沙箱测试执行工具代码（`ToolExecuteRequest`：`code`、`args`） |

沙箱执行安全措施：

1. 必须登录；
2. 静态扫描拒绝危险 token（`import os`、`from subprocess`、`open(`、`exec(`、`eval(`、`__import__`、`socket.`、`pathlib` 等）→ `403`；
3. 受限 `globals`，仅暴露白名单内置函数；
4. 自定义 import 钩子，仅允许纯计算模块（`json`/`datetime`/`math`/`re`/`collections`/`itertools`/`statistics`）；
5. 捕获异常并返回 traceback。

`execute` 响应：

```json
{ "success": true, "output": "stdout 内容", "error": "stderr 内容", "result": "函数返回值字符串" }
```

---

## 14. 统计接口（Stats，补充）

路由文件：`backend/api/stats.py`，路由前缀 `/api/stats`，仪表盘使用，均为公开只读。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/stats` | 今日回复数、平均响应时间、活跃会话、模型负载、CPU/GPU/内存/磁盘 |
| GET | `/api/stats/activity` | 24 小时活动趋势（每 2 小时一个数据点） |
| GET | `/api/stats/services` | 服务状态（Backend/NoneBot:8081/NapCat:6099/Model/DB） |

`StatsResponse` 字段：`todayReplies`、`avgResponseTime`、`activeSessions`、`modelLoad`、`cpuUsage`、`gpuMemory{used,total}`、`memoryUsage{used,total}`、`diskUsage{used,total}`。

---

## 15. 附：Next.js 前端代理说明

前端通过 `src/app/api/[[...path]]/route.ts` 将 `/api/*` 请求代理到后端 `:8000`，因此前端调用时无需关心后端真实端口，统一以相对路径 `/api/...` 发起请求即可。登录态由浏览器自动携带 httpOnly Cookie，无需手动附加 Token。
