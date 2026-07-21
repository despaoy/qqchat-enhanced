# 项目上下文文档（AI 运行前必读）

> **本文件是 AI 助手在本项目工作的权威入口。每次会话开始前，AI 必须先完整阅读本文件，再执行任何任务。**
>
> 更新时间：2026-07-18
> 维护规则：项目状态发生变更时必须同步更新本文件。

---

## 1. 项目定位

QQChat Enhanced 是一个面向角色对话研究与保研展示的多平台 LLM 系统。项目覆盖数据治理、LoRA 微调、AWQ 高效推理、混合 RAG、评测体系、AstrBot 消息网关以及可观测的 Web 管理台。

- **定位**：单机可部署、证据驱动的研究原型
- **核心链路**：数据 → 训练 → 推理 → 检索 → 评测 → 多平台交付
- **不以堆叠云原生组件为目标**

---

## 2. 技术基线

| 模块 | 版本/实现 |
|------|----------|
| 基座模型 | **Qwen3-8B-Instruct**（已从 Qwen2.5-7B 迁移） |
| 量化推理 | Qwen3-8B-Instruct-AWQ + vLLM 0.10.2 |
| 训练 | PyTorch 2.8.0+cu128, Transformers 4.57, PEFT, TRL |
| 后端 | Python 3.12 + FastAPI 2.0.0 |
| 前端 | Node.js 22 + Next.js 16 + React 19 + Tailwind v4 + shadcn/ui |
| RAG | FAISS/BM25 混合检索 + BGE-M3 + 可选 Reranker |
| 数据库 | SQLite（本地）/ PostgreSQL（部署推荐） |
| 缓存 | Redis 可选，不可用时降级到进程内实现 |
| 包管理 | 前端 pnpm 10.34，后端 pip |

---

## 3. 服务器与环境

### 3.1 实验室服务器

- **IP**：192.168.166.7
- **用户**：szw
- **SSH 连接**：paramiko（密码认证）
- **GPU**：NVIDIA RTX 3090（24GB），双卡（GPU 0 推理/训练，GPU 1 备用）
- **项目根目录**：`/home/szw/lhm2/qqchat-enhanced`
- **Conda 环境**：`/home/szw/lhm2/envs/qqchat-gpu-qwen3`
- **Python**：3.12.13
- **PyTorch**：2.8.0+cu128
- **vLLM**：0.10.2（注意：勿用 0.23.0+，有 pip 元数据解析 bug）
- **Transformers**：4.57.6

### 3.2 关键路径

| 用途 | 路径 |
|------|------|
| 基座模型 | `/home/szw/lhm2/runtime/models/Qwen3-8B-Instruct` |
| LoRA 适配器 | `/home/szw/lhm2/runtime/loras/<character>/<experiment>/final/` |
| 月社妃 E2'' 适配器 | `/home/szw/lhm2/runtime/loras/kisaki/e2pp_rag_r32/final/` |
| 训练日志 | `/home/szw/lhm2/runtime/logs/kisaki_e2pp_rag.log` |
| vLLM 日志 | `/home/szw/lhm2/runtime/logs/vllm_e2pp_rag.log` |
| 训练配置 | `backend/data/character_dialogues/experiments/configs/` |
| 评估结果 | `backend/data/character_dialogues/experiments/results/` |

### 3.3 端口约定

| 服务 | 端口 |
|------|------|
| FastAPI 后端 | 8000 |
| vLLM 默认服务 | 8001 |
| vLLM 实验实例（月社妃） | 8002 |
| Next.js 前端 | 5000 |

---

## 4. 当前实验状态

### 4.1 月社妃（Kisaki）实验进度

| 实验 | 数据量 | 关键变量 | 状态 | 核心指标 |
|------|--------|----------|------|----------|
| E1 baseline | 854 条 | r=32, 无 NEFTune | ✅ 完成 | eval_loss=2.802, safety=0.13, citation=0.60 |
| E2 NEFTune | 864 条 | + NEFTune α=2.5 | ✅ 完成 | avg_chars=93.92 |
| E2' Safety++ | 874 条 | + safety 数据增强 | ✅ 完成 | avg_chars=44.63 |
| **E2'' RAG** | **899 条** | + RAG 引用数据 | ✅ **完成（最新）** | **100/100, citation=0.05, 19条问题样本** |
| E3 DoRA | 899 条 | use_dora=true | ⏳ 待执行 | — |
| E4 RSLoRA | 899 条 | use_rslora=true | ⏳ 待执行 | — |

### 4.2 E2'' 重训详情（2026-07-18）

- **训练数据**：899 条 = 721 game_extraction + 108 llm_v3_deepseek + 70 manual/safety/RAG
- **训练参数**：r=32, α=64, dropout=0.1, lr=2e-4, 3 epochs, NEFTune α=2.5, packing, 7 target_modules
- **训练质量**：loss 5.32→1.17（最佳 step 230），eval_loss=2.705（最佳 step 150），早停触发
- **评估结果**：100/100 成功，avg_chars=50.27，重复率=0.0016，延迟=878ms
- **问题样本**：19 条（5 AI自指、3 第三人称、1 禁用口癖、2 统计类、7 过长）
- **待解决**：AI 自指和第三人称问题需 System Prompt 层面解决

### 4.3 其他角色

- **胡桃（hutao）**：基于 Qwen2.5 训练的旧 adapter，需基于 Qwen3 重训
- **Minamo**：同上，需基于 Qwen3 重训

---

## 5. 关键约束与规则

### 5.1 训练数据约束

- 训练数据必须经过人工审查，去除 AI 生成污染
- 对话样本回复长度应在 10-40 字区间（68%+），无超过 100 字的样本
- 游戏提取数据为主（721条），LLM 生成数据为辅（108条，需风格校准）
- RAG 训练数据必须第一人称角色代入，不得使用第三人称客观描述
- RAG 数据不得包含 `[文档ID]` 引用标签
- 禁用口癖：哈哈/嘿嘿 → 仅允许"呼呼呼"

### 5.2 LoRA 训练约束

- Qwen2.5-7B 的 LoRA adapter 与 Qwen3-8B 不兼容，必须重新训练
- LoRA 默认参数：r=32, α=64, dropout=0.1, 7 个 target_modules（q/k/v/o/gate/up/down_proj）
- NEFTune noise alpha=2.5（E2 起启用）
- GPU 温度保护：82°C 触发散热暂停，72°C 恢复
- 训练时使用 GPU 0（若被占用则协商或等待）

### 5.3 推理约束

- vLLM 推理推荐参数：repetition_penalty=1.15, frequency_penalty=0.3
- CUDA graph 模式（不加 `--enforce-eager`），已验证稳定
- vLLM 0.10.2 是验证过的版本，不要升级
- Transformers 4.56.x（< 5.0），与 vLLM 0.10.2 实测兼容

### 5.4 评测约束

- Gold Set（100 条）永不参与训练
- 评估脚本：`backend/evaluation/character_benchmark.py`
- 月社妃安全检测包含角色化委婉拒绝句式
- citation 判定：单 ref 要求 all，多 ref 要求 any

### 5.5 测试约束

- CI 测试在 Ubuntu 运行，必须通过
- Windows 特定测试使用 `@pytest.mark.skipif(sys.platform == "win32")`
- 测试超时需考虑环境差异（CI 可能比本地慢）
- 严格错误消息断言可能跨平台失败，使用灵活匹配

### 5.6 月社妃角色特性（训练数据治理依据）

- **反向表达**："讨厌"= 爱，"连讨厌都谈不上"= 否定存在
- **拒绝 + 讽刺 > 解释**：永远选择冷淡拒绝而非解释
- **元叙事自觉**：将现实视为"被编写的故事"
- **口癖清单**：—— / 因此 / 假如 / 即使 / 呢 / 呼呼呼 / 谈不到 / 没有那个必要
- **禁止**：哈哈 / 嘿嘿 / AI 自指 / 第三人称客观回答 / 统计类回答

---

## 6. 文档导航

### 6.1 核心文档（必读）

| 文档 | 路径 | 内容 |
|------|------|------|
| **项目上下文（本文件）** | `PROJECT_CONTEXT.md` | AI 运行前必读，项目状态总览 |
| 项目 README | `README.md` | 项目总览与快速验证 |
| 文档索引 | `docs/README.md` | 文档分类与维护规则 |
| 代码百科 | `docs/architecture/CODE_WIKI.md` | 后端 18 路由、26 表、前端 14 页面全解析 |

### 6.2 架构文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 优化策略 | `docs/architecture/OPTIMIZATION_STRATEGY.md` | P0-P3 优先级基线 |
| 生产就绪审查 | `docs/architecture/PRODUCTION_READINESS_REVIEW_2026-07-18.md` | 2026-07-18 审查结论 |

### 6.3 运维文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 部署指南 | `docs/operations/DEPLOYMENT_GUIDE.md` | RTX 3090 单机部署 |
| 服务器布局 | `docs/operations/SERVER_LAYOUT.md` | `/home/szw/lhm2` 目录规范 |
| 清理策略 | `docs/operations/CLEANUP_POLICY.md` | 可清理/不可清理规则 |

### 6.4 研究文档

| 文档 | 路径 | 状态 | 内容 |
|------|------|------|------|
| 月社妃人物特性 | `docs/research/KISAKI_CHARACTER_PROFILE.md` | 最新 | 7 章节人物全解析 |
| LoRA 重训计划 | `docs/research/KISAKI_LORA_RETRAIN_PLAN.md` | 最新 | E1-E4 实验设计（已同步实际执行） |
| E1 评估报告 | `docs/research/KISAKI_E1_EVAL_REPORT.md` | 历史基线 | E1 baseline 真实评估 |
| E2'' 四方对比 | `docs/research/KISAKI_E2PP_EVAL_REPORT.md` | ⚠️ 历史归档 | 旧 E2'' 结论已被推翻 |
| E2'' 五方对比 | `docs/research/KISAKI_E2PP_V2_COMPARISON.md` | 最新 | 重训前后对比（citation 0.95→0.05） |
| E2'' 问题样本 | `docs/research/KISAKI_E2PP_V2_PROBLEM_SAMPLES.md` | 最新 | 19 条问题样本清单 |
| E2'' 对话抽查 | `docs/research/KISAKI_E2PP_V2_SAMPLES.md` | 历史快照 | 样本抽查（已被 V2_COMPARISON 取代） |
| vLLM 基准报告 | `docs/research/REAL_VLLM_BENCHMARK_REPORT.md` | ⚠️ 历史对照 | Qwen2.5 迁移前快照 |
| 研究路线图 | `docs/research/RESEARCH_AND_LEARNING_ROADMAP.md` | 最新 | 9 个研究方向 + 10 周计划 |
| 新手实验指南 | `docs/research/BEGINNER_REAL_LLM_EXPERIMENT_GUIDE.md` | 最新 | 真实 LLM 实验操作指南 |

### 6.5 数据文档

| 文档 | 路径 | 状态 | 内容 |
|------|------|------|------|
| 数据集卡片 v1 | `docs/data/dataset-card.md` | ⚠️ v1 历史 | 原神 4 角色 1200 条（Qwen2.5） |
| 人工评分标准 | `docs/data/human-scoring-rubric.md` | 最新 | 5 类别 5 分制 rubric |
| 对话数据 README | `backend/data/character_dialogues/README.md` | 最新 | 月社妃 899 条数据说明 |

---

## 7. AI 运行前检查清单

每次会话开始时，AI 必须确认以下事项：

### 7.1 身份确认
- [ ] 当前工作目录：`c:\Users\13474\Desktop\qqchat-enhanced`
- [ ] 用户语言：中文
- [ ] 用户偏好：简洁直接，无过度文学修饰

### 7.2 项目状态确认
- [ ] 基座模型：Qwen3-8B-Instruct（非 Qwen2.5）
- [ ] 当前最优实验：E2'' RAG（899 条，100/100 成功）
- [ ] 待解决问题：AI 自指、第三人称描述（需 System Prompt 层面）
- [ ] 待执行实验：E3 DoRA、E4 RSLoRA

### 7.3 禁止事项
- ❌ 不要将 Qwen2.5 的 LoRA adapter 用于 Qwen3
- ❌ 不要升级 vLLM 到 0.23.0+
- ❌ 不要在训练数据中使用第三人称客观描述
- ❌ 不要在 RAG 训练数据中保留 `[文档ID]` 引用标签
- ❌ 不要使用"哈哈"/"嘿嘿"作为月社妃口癖
- ❌ 不要将 Gold Set（100 条）用于训练
- ❌ 不要在 CI 中运行 Windows 特定测试
- ❌ 不要创建不必要的文档文件

### 7.4 注意事项
- ⚠️ SSH 连接使用 paramiko，nohup 命令会超时但后台进程正常启动
- ⚠️ GPU 0 用于推理/训练，GPU 1 可能被其他用户占用
- ⚠️ GPU 温度 82°C 会触发散热暂停
- ⚠️ 历史文档（标注⚠️）不应作为当前状态的依据
- ⚠️ 训练数据计数以 899 条为准（721+108+70）

### 7.5 常用命令

```bash
# 检查训练状态
python scripts/check_e2pp_training_status.py

# 重启 vLLM（月社妃 E2''）
python scripts/restart_vllm_e2pp.py

# 运行 E2'' 评估
python scripts/run_e2pp_eval_v2.py

# 后训练管道（等待→重启→评估→分析）
python scripts/post_e2pp_retrain_pipeline.py

# 生成五方对比报告
python scripts/generate_e2pp_comparison_report.py
```

---

## 8. 变更日志

| 日期 | 变更内容 |
|------|----------|
| 2026-07-18 | 创建本文件；E2'' 重训完成（899 条，100/100）；6 份文档更新（EVAL_REPORT 归档、CHARACTER_PROFILE 数据校准、对话 README 补充、CODE_WIKI 模型版本修正、RETRAIN_PLAN 实验编号同步、E1 报告注释）|
