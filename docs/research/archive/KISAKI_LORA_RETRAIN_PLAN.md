> 历史规划文档：其中旧 E1/E2/E2'/E2'' 编号与数据已废弃，不得据此启动正式实验。当前唯一方案见 [月社妃 LLM 研究主线 v3](KISAKI_LLM_RESEARCH_PROGRAM_V3.md)。

# 月社妃 LoRA 重新训练科研路径（Qwen3-8B 基座）

> 执行状态：E1、E2、E2'、E2'' 已完成；后续优先人工复核、无泄漏 Gold Set、DoRA/RSLoRA 消融和盲评。

> **角色**：月社妃（月社妃，纸上魔法使系列）
> **基座模型**：Qwen3-8B-Instruct / Qwen3-8B-Instruct-AWQ
> **科研目标**：以"数据为中心 + 方法消融"双线叙事，产出可部署的高质量 LoRA 适配器
> **保研定位**：展示**数据治理、受控消融、诚实评估、可复现部署**四项能力
> **生成日期**：2026-07-17
> **关联文档**：[研究与学习路线图](RESEARCH_AND_LEARNING_ROADMAP.md)、[优化策略](../architecture/OPTIMIZATION_STRATEGY.md)、[数据集卡片](../data/dataset-card.md)、[人工评分标准](../data/human-scoring-rubric.md)

---

## 0. 背景与动机

### 0.1 为什么要重训

- 旧 LoRA 基于 Qwen2.5-7B 训练，与 Qwen3-8B 架构不兼容，已备份至 `loras/backup_qwen25/`，无法直接使用。
- 上一次月社妃 LoRA（2026-07-14 v1）在质量门禁中**失败**（见 `tsukiyashiro_kisaki_quality_gate.json`）：
  - `output_token_ratio = 0.0499`（阈值 0.25）→ 回复塌缩到 8.07 tokens，几乎不说话
  - `safety_pass_rate = 0.27`（阈值 0.75）→ 角色扮演下安全护栏崩塌
  - `rag_citation_accuracy = 0.0`（阈值 0.98）→ 完全丢失引用能力
- 这为我们提供了一个**宝贵的失败对照基线**：可以系统性地诊断根因，并在新一轮训练中验证修复效果。这是保研材料中"问题发现→根因分析→实验验证→闭环改进"叙事的天然素材。

### 0.2 科研叙事主线

> **"我从一次失败的角色 LoRA 出发，构建了数据治理流水线，通过受控消融定位关键方法因子，最终产出了既通过质量门禁又能部署服务的高质量适配器，并用盲评证据支撑结论。"**

四项可展示能力：

1. **数据为中心的微调**：原始游戏文本→SFT 样本→LLM 增强→人工审核→版本化数据集
2. **受控消融实验**：LoRA baseline / DoRA / RSLoRA / NEFTune 单变量对比
3. **诚实多层评估**：自动指标 + 质量门禁 + 人工盲评 + 失败案例分析
4. **可复现部署**：版本化配置、固定种子、隔离 vLLM 进程、Gold Set 复测

---

## 1. 数据治理流水线（第 0-1 周）

这是整个科研路径的根基。**没有可信数据，所有消融结论都是空中楼阁。**

### 1.1 数据源全景

| 来源 | 位置 | 特点 | 用途 |
|---|---|---|---|
| 原始游戏文本 | `gametext/纸上魔法使/*.txt` | 16 卷完整剧情，含 `[妃]` 标签台词 | 提取妃的原始台词与上下文 |
| 现有 SFT 样本 | `backend/data/character_dialogues/tsukiyashiro_kisaki_sft.json` | 已提取的 676 条对话（含质量评分） | 作为 v1 失败基线的训练数据 |
| 现有 raw 数据 | `backend/data/character_dialogues/tsukiyashiro_kisaki_raw.jsonl` | 原始抽取记录，含 excluded 列表 | 分析 v1 数据缺陷 |
| LLM 增强生成 | 通过 `/api/training/generate-dialogues` | 12 类场景、轮次分布、网络搜索角色背景 | 扩充多样性、覆盖游戏外场景 |
| 偏好候选对 | `experiments/research/tsukiyashiro_kisaki_preference_candidates.jsonl` | 已生成的 chosen/rejected 对 | 第 5 阶段 DPO/ORPO pilot |

### 1.2 v1 失败根因诊断（必做，半天）

**目标**：弄清为何 v1 LoRA 输出只有 8 tokens、安全率 0.27。

诊断步骤：

1. 统计 v1 训练数据 (`tsukiyashiro_kisaki_train.json`) 的回复长度分布、平均 tokens、短回复占比
2. 检查 `tsukiyashiro_kisaki_excluded.jsonl` 中被排除的样本类型
3. 抽样 20 条训练样本人工查看：是否存在大量"嗯""……""你是什么人"等极短回复
4. 检查 system prompt 是否过度约束输出长度
5. 输出 `v1_failure_diagnosis.md`：根因假设 + 验证证据 + 修复方向

**预期根因**（需数据验证）：
- 游戏文本中妃的台词本就简短冷峻，SFT 后模型学到了"短回复=符合角色"的错误先验
- 训练数据缺乏长回复正样本，模型塌缩到 mode-collapse

### 1.3 数据集构建 v2（2-3 天）

**设计原则**：**混合数据策略**，既保留角色特征又避免塌缩。

#### 1.3.1 原始游戏文本提取（保留角色灵魂）

从 `gametext/纸上魔法使/*.txt` 重新提取，改进策略：
- 提取 `[妃]` 标签的台词，**连同上下文 2-3 句**作为 user 输入
- 过滤掉过短台词（< 5 字），单独归入"简短回复"类别，控制占比 ≤ 15%
- 保留台词的场景元数据（哪一卷、什么情节）

#### 1.3.2 LLM 增强生成（扩充多样性）

利用现有 `/api/training/generate-dialogues` 接口，调用软件中的大模型（Qwen3-8B 或 DeepSeek API）：

**角色设定输入**（用于 generate-dialogues 的 `character_description`）：
```
月社妃，纸上魔法使系列女主角。性格特点：
- 冷静理智，话不多但每句都有分量
- 对克丽索贝莉露有复杂情感
- 内心柔软但不轻易表露
- 喜欢读书，常待在幻想图书馆
- 说话带有一定的文学气质，偶尔引用书本内容
- 不会过度热情，但也不冷漠
- 面对亲近的人会展现温柔一面
```

**生成配额**（建议）：
- 12 类场景 × 每类 30 条 = 360 条候选
- 轮次分布按现有权重（1-8 轮）
- **关键改进**：在 `custom_prompt` 中明确要求"回复长度不少于 30 字，避免极短回复"

#### 1.3.3 人工审核与质量过滤（核心科研动作）

**这一步是保研叙事中"数据为中心"的关键证据。**

1. 合并游戏提取 + LLM 生成，得到约 1000+ 条候选
2. 按 [人工评分标准](../data/human-scoring-rubric.md) 的 5 分制抽样审核
3. 过滤规则：
   - 回复 < 10 字的直接剔除（除非是"嗯""好"等自然简短回应）
   - 角色不一致（如妃突然变得热情话痨）剔除
   - 重复率 > 0.7 的剔除
   - 安全风险内容剔除
4. 保留 600-800 条高质量样本
5. 输出 `kisaki_sft_v2.json` + 审核日志 `kisaki_v2_review.md`

#### 1.3.4 数据集分割与版本化

- 按**对话级别**（非行级别）切分 train/val/test = 80/10/10
- test 集必须包含 30+ 条 held-out prompt，**永不参与训练**
- 记录数据集 SHA256、样本数、长度分布、来源比例
- 版本号：`kisaki-sft-v2`（区别于失败的 v1）

### 1.4 数据集卡片更新

完成 [数据集卡片](../data/dataset-card.md) 中月社妃条目的更新，包含：
- 来源比例（游戏提取 X% / LLM 生成 Y%）
- 长度分布直方图
- 已知风险（如游戏台词的版权、LLM 生成的幻觉风险）
- v1 vs v2 对比表

---

## 2. 评估基础建设（第 1-2 周，与数据治理并行）

### 2.1 Gold Set 构建（不可省略）

**目标**：100 条 held-out prompt，覆盖 5 类，永不参与训练。

| 类别 | 数量 | 示例方向 |
|---|---|---|
| persona 一致性 | 30 | 妃的说话风格、对克丽索贝莉露的态度 |
| factual 事实 | 20 | 关于妃的设定问题（喜欢什么书、住哪里） |
| RAG 接地 | 20 | 需要引用知识库的问题 |
| safety 安全 | 15 | 角色扮演下的越狱尝试、不当请求 |
| multiturn 多轮 | 15 | 5-8 轮连贯对话 |

存为 `experiments/research/kisaki_gold_set_v1.json`。

### 2.2 评估指标套件

复用现有 `backend/evaluation/` 模块，确保以下指标自动计算：

| 层 | 指标 | 阈值（来自 benchmark_gate） |
|---|---|---|
| 格式 | format_correct_rate | ≥ 0.99 |
| 安全 | safety_pass_rate | ≥ 0.75 |
| RAG | rag_citation_accuracy | ≥ 0.98 |
| 长度 | output_token_ratio | ≥ 0.25 |
| 重复 | repetition_rate | ≤ 0.05 |
| 多样性 | distinct-1 / distinct-2 | 记录，无硬阈值 |

### 2.3 人工盲评流程

参考 [偏好审核指南](../../backend/data/character_dialogues/experiments/research/PREFERENCE_REVIEW_GUIDE.md)：
- A/B 对比：baseline（无 LoRA）vs candidate（带 LoRA）
- 评分者不知道哪个是 A 哪个是 B
- 每条按 rubric 打分 + 原因码
- 至少 20 条盲评样本才可下结论

---

## 3. 受控消融实验（第 2-4 周，核心科研部分）

### 3.1 实验设计原则

**单变量控制**：每次只改一个因子，其余全部固定。

固定变量（所有实验相同）：
- 基座模型：`Qwen3-8B-Instruct`（非 AWQ，训练用全精度）
- 训练数据：`kisaki-sft-v2`（同一份）
- 随机种子：`seed=42`
- 学习率：`2e-4`
- epochs：`3`
- batch size：`1` × `gradient_accumulation=8`
- max_seq_length：`1024`
- target_modules：7 个线性层（q/k/v/o/gate/up/down_proj）
- lora_r：`32`，lora_alpha：`64`，lora_dropout：`0.1`

### 3.2 消融实验（实际执行）

> 原计划 E2=DoRA / E3=RSLoRA / E4=NEFTune 的四组消融；实际执行中根据 E1 暴露的问题调整为渐进式数据增强路径（NEFTune → Safety++ → RAG），DoRA/RSLoRA 消融待后续执行。

| 实验编号 | 名称 | 变量 | 配置文件 | 训练量 | 状态 |
|---|---|---|---|---|---|
| **E1** | LoRA baseline | r=32, alpha=64, 无 NEFTune | `tsukiyashiro_kisaki_lora_r32.json` | 854 条 | ✅ 已完成 |
| **E2** | + NEFTune | + NEFTune α=2.5, safety 数据增强 | `tsukiyashiro_kisaki_e2_neftune.json` | 864 条 | ✅ 已完成 |
| **E2'** | Safety++ | + 扩充 safety 数据（角色化软拒绝） | `tsukiyashiro_kisaki_e2p_neftune.json` | 874 条 | ✅ 已完成 |
| **E2''** | RAG | + RAG 引用数据（15 单 ref + 5 多 ref + 5 拒答） | `tsukiyashiro_kisaki_e2pp_rag.json` | 899 条 | ✅ 已完成 |
| **E3** | + DoRA | `use_dora=true` | 待建 | 899 条 | ⏳ 待执行 |
| **E4** | + RSLoRA | `use_rslora=true` | 待建 | 899 条 | ⏳ 待执行 |

**关键**：E2→E2'→E2'' 为渐进式数据增强（各自只增加一个维度的数据），E3/E4 将在 E2'' 基线上切换 DoRA/RSLoRA 开关。

### 3.3 实验执行流程（每个实验）

1. **训练前检查**（15 分钟）：
   - `nvidia-smi` 确认 GPU 1 可用（≥ 4GB 空闲）
   - 若 GPU 紧张，**停止 vLLM 服务**，训练完再重启
   - 确认训练数据 SHA256 与 Gold Set 无交集

2. **训练启动**：
   ```bash
   # 使用项目内训练脚本
   cd /home/szw/lhm2/qqchat-enhanced
   source /home/szw/lhm2/activate_qqchat.sh
   python -m backend.training.trainer --config experiments/configs/E1_lora_baseline.json
   ```

3. **训练监控**：
   - TensorBoard：`tensorboard --logdir output/E1/logs`
   - 关注 eval_loss、perplexity、是否过拟合
   - 记录训练时间、峰值 VRAM、可训练参数数

4. **训练后评估**：
   - 在 held-out test 集上跑 `backend/evaluation/`
   - 在 Gold Set 上跑生成 + 自动指标
   - 跑 `benchmark_gate` 质量门禁
   - 20 条盲评

5. **产物归档**（每个实验一个目录）：
   ```
   experiments/results/qwen3_kisaki_E1/
   ├── adapter/              # final adapter 权重
   ├── adapter_config.json   # PEFT 配置
   ├── training_config.json  # 完整训练配置
   ├── training_log.json     # loss/eval 曲线
   ├── training_metrics.json # 时间/VRAM/参数数
   ├── eval_report.json      # Gold Set 自动指标
   ├── quality_gate.json     # 门禁结果
   ├── blind_review.json     # 20 条盲评
   └── error_cases.md        # 3 个代表性失败案例
   ```

### 3.4 消融对比表（最终产物）

| 实验 | eval_loss | perplexity | format | safety | RAG(citation) | token_ratio | distinct-2 | 平均字符 | 训练量 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 baseline | 2.802 | — | 1.0 | 0.13 | 0.60 | — | 0.50 | 56.31 | 854 | ✅ |
| E2 NEFTune | — | — | 1.0 | — | — | — | — | 93.92 | 864 | ✅ |
| E2' Safety++ | — | — | 1.0 | — | — | — | — | 44.63 | 874 | ✅ |
| E2'' RAG | 2.705 | — | 1.0 | 1.0 | 0.05 | — | 0.61 | 50.27 | 899 | ✅ |
| v1 失败基线 | — | — | 1.0 | 0.27 | 0.0 | 0.05 | — | — | — | 历史 |
| E3 DoRA | | | | | | | | | | ⏳ |
| E4 RSLoRA | | | | | | | | | | ⏳ |

**这张表是保研面试的核心展示物。**

### 3.5 实验结论模板

每个实验产出一页结论，包含：
- 假设
- 受控变量
- 结果（填表）
- 是否验证假设
- 3 个代表性成功案例
- 3 个代表性失败案例
- 对下一实验的启示

---

## 4. 部署与效果验证（第 4-5 周）

### 4.1 选择最佳 adapter

从 E1-E4 中选择**门禁通过 + 盲评分最高**的作为生产 adapter。

**选择标准**（按优先级）：
1. 质量门禁必须 PASS
2. 盲评平均分最高
3. 若并列，选训练成本最低的（VRAM/时间）
4. 若仍并列，选 E1（baseline，最简单可解释）

### 4.2 部署到 vLLM

1. 将最佳 adapter 复制到 `/home/szw/lhm2/runtime/loras/kisaki/final/`
2. 更新 `backend/loras/` 注册
3. 通过 `/api/loras/scan` 扫描注册
4. 通过 `/api/loras/{id}/status` 激活
5. 验证 vLLM 加载日志无报错

### 4.3 线上效果验证

1. 通过前端 `/lora` 页面切换到新 adapter
2. 在 `/chat` 页面发送 10 条测试消息，确认回复正常
3. 通过 AstrBot 发送真实 QQ 消息端到端测试
4. 监控 `logs/backend.log` 和 `logs/vllm.log` 24 小时无异常
5. 收集 5 条真实用户反馈（可自己用小号）

### 4.4 部署验收清单

- [ ] adapter 加载成功，vLLM `/v1/models` 显示
- [ ] Gold Set 复测指标与训练时一致（±5%）
- [ ] 前端聊天回复长度正常（平均 ≥ 30 tokens）
- [ ] 安全测试：越狱 prompt 被拒绝
- [ ] AstrBot QQ 消息端到端正常
- [ ] 24 小时无崩溃

---

## 5. 进阶：偏好对齐 pilot（第 5-6 周，可选）

如果时间充裕，在最佳 SFT adapter 基础上做小型 DPO/ORPO pilot，展示"对齐"能力。

### 5.1 偏好数据准备

利用已有的 `tsukiyashiro_kisaki_preference_candidates.jsonl`：
1. 按 [偏好审核指南](../../backend/data/character_dialogues/experiments/research/PREFERENCE_REVIEW_GUIDE.md) 人工审核
2. 仅保留 `approved` 的对
3. 目标：≥ 50 条 approved 偏好对
4. 添加 ≥ 10 条 hard negative（角色崩塌、过度通用、不安全）

### 5.2 DPO pilot

- 基于 E1-E4 中最佳 SFT adapter 作为参考模型
- QLoRA + DPO（3090 显存约束）
- 评估：held-out 偏好集上的 chosen/rejected log-probability 差
- **不报告历史 `eval_accuracy=0.65`**（占位值）
- **不声称 RLHF**（DPO 是对比学习，非强化学习）

### 5.3 SFT vs SFT+DPO 对比

在相同 Gold Set 上对比：
- persona 一致性
- helpfulness
- safety
- 偏好胜率

---

## 6. 时间线总览

| 周 | 阶段 | 交付物 | Pass 标准 |
|---|---|---|---|
| 第 0 周 | v1 失败诊断 + 数据治理启动 | `v1_failure_diagnosis.md`、`kisaki_sft_v2.json` | 根因明确、v2 数据 ≥ 600 条 |
| 第 1 周 | Gold Set + 评估基础 | `kisaki_gold_set_v1.json`、评估流水线 | Gold Set 100 条、自动指标可跑 |
| 第 2 周 | E1 baseline + E2 NEFTune | 两个实验完整产物 | 至少一个门禁 PASS |
| 第 3 周 | E2' Safety++ + E2'' RAG | 两个实验完整产物 | 四组全部完成 |
| 第 4 周 | 消融对比 + 部署 | 对比表、最佳 adapter 上线 | 线上效果验证通过 |
| 第 5 周 | 偏好 pilot（可选） | DPO adapter、对比报告 | 偏好胜率 > 50% |
| 第 6 周 | 报告撰写 + 作品集 | 完整实验报告 | 可复现、可答辩 |

---

## 7. 保研材料清单

完成后的可展示材料：

1. **一张架构图**：数据治理流水线 + 消融实验 + 部署架构
2. **一张消融对比表**：E1-E4 + v1 失败基线，6 行 × 11 列
3. **一张数据治理图**：原始游戏文本 → LLM 增强 → 人工审核 → 版本化数据集
4. **一张失败案例图**：v1 塌缩 vs v2 修复的回复长度分布对比
5. **一张盲评结果图**：baseline vs best adapter 的 rubric 雷达图
6. **一张部署演示**：QQ 消息端到端 trace ID 串联
7. **一份完整实验报告**：含假设、方法、结果、失败分析、结论
8. **5 分钟 demo + 8 分钟技术讲解**

---

## 8. 研究诚信 Guardrails

- **不**用不同数据、种子、prompt 对比方法并称之为消融
- **不**用单一 LLM judge 作为质量的唯一证据
- **不**将 mock 输出当作真实实验结果
- **不**声称 `eval_accuracy=0.65`（历史占位值）
- 生成的偏好对必须 `pending` → 人工 `approved` 才能用于 DPO
- DPO/ORPO **不是** RLHF
- 每次实验保留：数据版本、种子、模型版本、命令、硬件、报告
- 至少 50 条 approved 偏好对才可进行 DPO pilot
- 失败案例必须诚实展示，不得隐瞒

---

## 9. 立即执行清单

### 本周（第 0 周）立即可做

1. **诊断 v1 失败**（半天）：
   ```bash
   cd /home/szw/lhm2/qqchat-enhanced
   python -c "
   import json
   data = json.load(open('backend/data/character_dialogues/tsukiyashiro_kisaki_train.json'))
   replies = [c['value'] for d in data for c in d['conversations'] if c['from']=='gpt']
   lengths = [len(r) for r in replies]
   print(f'样本数: {len(replies)}')
   print(f'平均长度: {sum(lengths)/len(lengths):.1f} 字')
   print(f'短回复(<10字)占比: {sum(1 for l in lengths if l<10)/len(lengths):.1%}')
   print(f'最短5条: {sorted(lengths)[:5]}')
   "
   ```

2. **提取游戏文本**（1 天）：
   - 写脚本从 `gametext/纸上魔法使/*.txt` 提取 `[妃]` 台词 + 上下文
   - 过滤过短台词，控制短回复占比

3. **LLM 增强生成**（1 天）：
   - 通过前端 `/training` 页面或 API 调用 generate-dialogues
   - 角色描述用第 1.3.2 节的设定
   - 生成 360 条候选

4. **人工审核合并**（1-2 天）：
   - 合并游戏提取 + LLM 生成
   - 按 rubric 审核，保留 600-800 条
   - 输出 `kisaki_sft_v2.json`

### 配置文件模板

参考现有的 `experiments/configs/tsukiyashiro_kisaki_lora_r32.json`，创建 4 个实验配置，**注意更新**：
- `base_model_path`: `/home/szw/lhm2/runtime/models/Qwen3-8B-Instruct`
- `train_data_path`: 指向 `kisaki_sft_v2.json`
- `output_dir`: 每个实验独立目录
- 对应实验的变量开关

---

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| GPU 被 mythoughtV5 训练占用 | 中 | 训练延后 | 协商错峰、训练时停 vLLM |
| v2 数据仍导致塌缩 | 低 | 需三轮数据治理 | 第 0 周先诊断根因，针对性修复 |
| 四组实验都不过门禁 | 低 | 需调参 | 先跑 E1，若不过则调 lr/epochs/data |
| 偏好数据不足 50 条 | 中 | DPO pilot 取消 | SFT 部分已足够展示，DPO 标为可选 |
| 时间不足 | 中 | 跳过 E3/E4（DoRA/RSLoRA） | 已完成 E1+E2+E2'+E2''，E3/E4 视时间补充 |

---

## 11. 与项目文档的映射

| 本路径章节 | 关联文档 |
|---|---|
| 1. 数据治理 | [数据集卡片](../data/dataset-card.md)、[人工评分标准](../data/human-scoring-rubric.md) |
| 2. 评估基础 | [研究与学习路线图](RESEARCH_AND_LEARNING_ROADMAP.md) §4 评估框架 |
| 3. 消融实验 | [研究与学习路线图](RESEARCH_AND_LEARNING_ROADMAP.md) §5.A LoRA 变体 |
| 4. 部署 | [优化策略](../architecture/OPTIMIZATION_STRATEGY.md) §LoRA |
| 5. 偏好对齐 | [研究与学习路线图](RESEARCH_AND_LEARNING_ROADMAP.md) §5.C 偏好对齐 |
| 8. 诚信 | [研究与学习路线图](RESEARCH_AND_LEARNING_ROADMAP.md) §13 研究诚信 |
