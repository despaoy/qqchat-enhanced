# QQ 智能助手 — 全栈架构优化与工程实践

> **项目**：基于 Next.js 16 + FastAPI + vLLM 的企业级 AI 助手管理平台
> **规模**：168 文件 / 35,555 行（Python 32K + TypeScript 3K）
> **周期**：2026.06.18 ~ 2026.06.24
> **定位**：保研面试 — 项目改进经验

---

## 一、项目概览

### 1.1 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16 (App Router) + React 19 + TypeScript + shadcn/ui + Tailwind CSS 4 |
| 后端 | Python FastAPI + NoneBot2 + OneBot V11 适配器 |
| 推理 | vLLM (OpenAI 兼容 API) + transformers PEFT + Ollama 三级回退 |
| 数据库 | SQLite (WAL模式) / PostgreSQL (可选) + Redis 缓存 |
| 向量检索 | Faiss + BM25 + BGE-Reranker 重排序 + 意图分类器 |
| 模型 | Qwen2.5-7B-Instruct + LoRA 角色适配器 |
| 部署 | Docker Compose (vLLM×2 + FastAPI + Next.js + Nginx) |

### 1.2 功能模块

| 模块 | 功能 |
|------|------|
| 对话管理 | 多轮对话、LoRA 角色热切换、消息持久化 |
| RAG 知识库 | Faiss+BM25 混合检索、BGE 重排序、意图分类路由 |
| LoRA 微调 | 参数编辑器、预设系统、训练任务管理 |
| 系统监控 | CPU/GPU/内存监控、服务状态检测、审计日志 |
| 安全防护 | 认证/限流/输入校验/沙箱执行/API 白名单 |

---

## 二、架构设计实践

### 2.1 分层架构

采用**洋葱架构**思想，将原有 God File (`bot.py` 1136行/12职责) 分析并规划为清晰的分层结构：

```
┌─────────────────────────────────────────────┐
│  前端层        Next.js 16 App Router         │
│  src/app/  src/components/  src/hooks/       │
├─────────────────────────────────────────────┤
│  API 代理层    Route Handlers → proxyRequest  │
│  Cookie→Authorization 转换 + 路径白名单校验   │
├─────────────────────────────────────────────┤
│  后端 API 层   FastAPI + 14 个 APIRouter     │
│  auth / generate / knowledge / training / … │
├─────────────────────────────────────────────┤
│  安全中间件层  5层链式中间件                  │
│  审计 → 校验 → 限流 → 认证 → 安全头          │
├────────────────┬────────────────────────────┤
│  业务逻辑层     │  基础设施层                  │
│  inference/    │  circuit_breaker(熔断器)     │
│  training/     │  load_balancer(负载均衡)     │
│  knowledge/    │  failover(故障转移)          │
│  bot/          │  resource_pool(连接池)       │
├────────────────┴────────────────────────────┤
│  数据层        SQLite/PostgreSQL + Faiss     │
│  缓存层        Redis + 进程内 LRU + TTL      │
└─────────────────────────────────────────────┘
```

**关键设计决策**：
- **中间件按逆序注册**：最外层最后添加（Starlette特性），请求路径：审计→校验→限流→认证→安全头
- **输入校验按路径过滤**：`InputValidationMiddleware` 仅对 `/api/generate` 读取 body（Prompt注入检测），其他端点由 Pydantic 独立校验

### 2.2 并发架构设计

**6层并发控制体系**：

```
第1层：进程级   → uvicorn workers=4，绕过 Python GIL
第2层：限流    → 滑动窗口 RPM/TPM 双重限制
第3层：缓存    → L1 进程内 LRU + L2 Redis 语义缓存
第4层：熔断    → 三态机 CLOSED→OPEN→HALF_OPEN
第5层：信号量  → asyncio.Semaphore 控制并发数
第6层：连接池  → HTTP + DB 连接复用
```

**为什么 14 vCPU 只开 4 个 Worker？**

GPU 是瓶颈（单卡 RTX 3090），CPU 不是。4 个异步 Worker 每秒可发出数百推理请求，远超单 GPU 处理能力。每个 Worker 内部 async/await 可同时挂起 500 连接。更多 Worker 只会增加上下文切换开销。

### 2.3 断路器三态机设计

```
     CLOSED（正常）  ──连续失败→──   OPEN（拒绝请求）
          ↑                              │
          │                        等待冷却时间
          │                              ↓
          └──── 试探成功 ←── HALF_OPEN（限量试探）←┘
                试探失败 → 回到 OPEN
```

**设计要点**：针对流式生成场景（无法用 `call()` 包裹整体响应），新增公开 `record_success()` / `record_failure()` 手动记录模式，与 `call()` 内部逻辑共享同一状态机锁。

### 2.4 重复实现统合

**发现**：项目中存在三套 vLLM 客户端、三套消息管道并行维护。

| 实现 | 特点 | 决策 |
|------|------|------|
| `VLLMClient` | 多实例+熔断+重试+LoRA切换 | ✅ 唯一版本 |
| `VLLMProvider` | 单实例+无熔断+死锁风险 | ❌ 废弃 |
| `_infer_vllm` | 无重试+绕过断路器 | ❌ 废弃 |

**统合原则**：识别功能最完整、安全性最高的实现作为唯一版本，其余标注废弃并逐步迁移。

---

## 三、安全防护体系

### 3.1 纵深防御架构

```
第1层：Pydantic 模型校验   → 类型/范围/必填（FastAPI 自动）
第2层：中间件安全检测      → SQL注入/XSS/路径遍历/命令注入（15+ 正则）
第3层：Prompt注入检测      → 仅 /api/generate（避免误杀正常POST）
第4层：代码执行沙箱        → 受限builtins + import钩子 + 静态扫描
```

### 3.2 代码执行沙箱设计（Claw工具）

Claw 工具允许用户编写 Python 代码在服务端执行。安全设计采用**四层递进防护**：

| 层 | 机制 | 实现 |
|----|------|------|
| 1 | 强制认证 | `Depends(get_current_user)`，未登录拒绝 |
| 2 | 危险Token扫描 | 拒绝含 25+ 危险模式的代码 (`import os`/`open(`/`eval(` 等) |
| 3 | 内置函数白名单 | 仅暴露 `abs/min/max/list/dict/str/print` 等安全函数 |
| 4 | Import钩子 | `sys.meta_path` 拦截，仅允许 json/math/re/collections |

**设计权衡**：`exec()` 无法做到完全隔离。当前方案标注为"测试模式"，生产环境建议容器隔离。这是**安全与可用性的平衡**。

### 3.3 JWT 注销方案设计

**挑战**：JWT 无状态，服务端无法"删除"已签发的 Token。

| 方案 | 延迟 | 持久化 | 适用场景 |
|------|------|--------|----------|
| 内存 TTL 黑名单 | 0ms | ❌ 重启清空 | 开发/小规模 |
| Redis 黑名单 | <1ms | ✅ | 生产环境 |
| Token 版本号 | 查DB | ✅ | 高频注销 |

**当前实现**：内存 TTL 黑名单。`logout` 时将 `jti`+过期时间戳写入，`get_current_user` 检查命中则拒绝。条目在 JWT 自然过期后自动清理。

### 3.4 API 白名单代理设计

**问题**：Next.js catch-all 路由可能将整个后端 API 表面暴露。

**方案**：路径白名单 + 穿越拒绝双层校验

```typescript
const ALLOWED = ['/api/auth','/api/knowledge','/api/training',...];
function isAllowed(path: string): boolean {
  if (path.includes('..') || path.includes('//')) return false; // 路径穿越拒绝
  return ALLOWED.some(p => path.startsWith(p));
}
```

---

## 四、性能优化策略

### 4.1 SQL 查询优化

| 问题模式 | 优化方案 | 效果 |
|----------|----------|------|
| 全表扫描 `limit=100000` | SQL 层多条件 WHERE + 分页 | 内存从 O(N)→O(limit) |
| N+1 查询 | LEFT JOIN + GROUP BY | 3+2N 次查询→1 次 |
| 高频读库(每条消息) | 内存 TTL 缓存 60s + 写失效 | DB 查询量降 90%+ |
| 消息查询无索引 | `(sessionId, createdAt)` 复合索引 | 查询从全表扫→索引查找 |

**N+1 → JOIN 案例**：
```sql
-- 优化前：N个知识库 = 2N+1 次查询
SELECT * FROM knowledge_bases;
SELECT COUNT(*) FROM knowledge_documents WHERE id=?;  -- N次
SELECT COUNT(*) FROM knowledge_folders WHERE id=?;    -- N次

-- 优化后：1 次查询
SELECT kb.*, COUNT(DISTINCT kd.id) docCount, COUNT(DISTINCT kf.id) folderCount
FROM knowledge_bases kb
LEFT JOIN knowledge_documents kd ON kd.knowledge_base_id = kb.id
LEFT JOIN knowledge_folders kf ON kf.knowledge_base_id = kb.id
GROUP BY kb.id;
```

### 4.2 React 性能优化

| 问题 | 方案 | 效果 |
|------|------|------|
| useEffect 依赖循环→无限重渲染 | 拆分 effect + 移除循环依赖 | 页面 0.35s 渲染 |
| fetchX 每次渲染重建→stale closure | `useCallback` + 完整依赖 | 引用稳定 |
| 定时器因动态依赖频繁重建 | `useRef` 存最新值 | interval 生命周期稳定 |
| 后台标签页持续轮询 | `visibilityState` 跳过不可见时 | 减少无效请求 |

### 4.3 缓存策略设计

| 数据 | TTL | 失效机制 |
|------|-----|----------|
| session_bot_enabled | 60s | 状态变更 `pop` |
| 知识库列表 | 建议 30s | 增删改主动失效 |
| Faiss 查询结果 | 300s (LRU 100) | 数据变更 `clear_cache()` |

---

## 五、高可靠设计

### 5.1 容错与降级

```
推理失败 → 三级回退链：
  vLLM → transformers+PEFT → Ollama (CPU)
  
vLLM 额外配备：
  - 3次指数退避重试 + 随机抖动（防惊群）
  - 断路器（20次失败触发熔断，60s冷却后半开试探）
  - 故障转移（主备双 provider）
```

### 5.2 数据一致性保障

| 场景 | 机制 |
|------|------|
| Faiss 写入后查询 | 变更后 `clear_cache()` 防脏读 |
| SQLite 删除 | 事务包裹 `BEGIN IMMEDIATE` + 失败回滚 |
| 训练状态机 | 严格转换 `pending→training→completed/failed/cancelled` |
| 服务重启 | 标记未完成任务为 `interrupted` |
| DB 初始化失败 | `raise RuntimeError` 阻断启动 |

### 5.3 健康检查

| 端点 | 用途 | 检查内容 |
|------|------|----------|
| `/health` | Liveness | 进程存活 |
| `/ready` | Readiness | DB `SELECT 1` + Faiss 索引状态 |

---

## 六、功能开发实践

### 6.1 LoRA 训练参数编辑器

**背景**：原训练仅 3 字段（名称/数据集/预设），无法精细控制。

**设计**：
- **分层展示**：必填参数（始终可见）+ 高级设置（折叠，含一键预设）
- **23 字段全链路对齐**：UI → API → `_build_config` → `LoRATrainingConfig`
- **即时校验**：数据集 JSON/JSONL 上传后前端即时解析
- **预设系统**：低显存(≤6GB) / 均衡(8-12GB) / 高性能(≥16GB)
- **可复现**：JSON 配置导入/导出

**技术要点**：
- 后端 `_build_config` 从硬编码 18 参数改为动态 `**kwargs` + `extra_keys` 白名单
- `warmup_ratio` 字段与 HuggingFace 标准对齐

### 6.2 RAG 检索与 LLM 幻觉对抗

**三层防护**：检索质量(向量索引重建+中文分词) → 知识注入(System Prompt嵌入+权威性强调) → 生成约束(Temperature=0.3+限制历史轮数)

**核心发现**：RAG 模式下降低 Temperature 至 0.3，模型忠实度大幅提升。

### 6.3 意图分类多分类路由

**优化前**：二分类"要不要RAG" → 全库搜索 → 跨KB污染

**优化后**：多分类"应查哪个KB" → 精准路由 → 单KB检索

**亮点**：训练时保存 KB名→ID 映射到模型 config；每个KB生成"硬负例"提高判别力。

---

## 七、常见问题与修复经验

| 问题模式 | 症状 | 根因 | 修复思路 |
|----------|------|------|----------|
| **连接池破坏** | 全服务DB不可用 | `conn.close()` 后 thread-local 引用未置空 | 连接池管理生命周期，业务不直接 close |
| **useEffect 循环** | 页面持续 compiling | 依赖链形成闭环 | 拆分 effect + 移除动态依赖 |
| **JWT 注销无效** | 退出后仍可访问 | JWT 无状态 | TTL 黑名单服务端吊销 |
| **Body 被消费** | POST 端点解析失败 | 中间件读取 body | 路径过滤 + 仅特定端点介入 |
| **断路器失效** | 熔断静默不触发 | 公开 API 不完整 | 补充 record 手动模式 |
| **全表扫描** | 查询耗时随数据量线性增长 | 应用层过滤 | SQL 层 WHERE + 索引 |

---

## 八、项目评分变化

| 维度 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 安全 | 4.0 | 7.5 | +3.5 |
| 性能 | 5.0 | 6.5 | +1.5 |
| 可靠性 | 6.0 | 7.5 | +1.5 |
| 可观测性 | 2.0 | 3.0 | +1.0 |
| **综合** | **4.3** | **6.1** | **+1.8** |

---

## 九、技术能力体现

**全栈**：Next.js 16 + React 19 + FastAPI + SQLAlchemy + Redis + vLLM + Faiss

**系统设计**：分层架构 + 6层并发 + 纵深防御 + 三级回退 + 状态机

**工程实践**：代码审计 + SQL优化 + React优化 + 测试驱动 + Git管理
