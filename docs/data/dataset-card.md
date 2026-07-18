# 数据集卡片：QQChat Enhanced 角色训练数据

> 状态：历史 v1 数据集卡。Qwen2.5/原神角色字段用于旧实验；月社妃 Qwen3 数据应以 character_dialogues 清单和实验配置为准。

> 本文件遵循 `backend/evaluation/dataset_card_schema.py` 的 `DatasetCard` Schema。
> 版本：v1.0 ｜ 创建时间：2026-07-12 ｜ 维护者：项目作者

---

## 1. 基本信息（Schema 字段）

| 字段 | 值 |
| --- | --- |
| `schema_version` | 1 |
| `name` | qqchat-persona-sft-v1 |
| `source` | 合成对话 + 人工编写 + 原神知识库（见第 2 节） |
| `license` | CC BY-NC 4.0（合成数据）；原神世界观素材版权归 miHoYo/HoYoverse，仅用于非商业学术研究 |
| `language` | `["zh-CN"]` |
| `size` | ~1200 条多轮对话（持续扩充中，目标 3000+） |
| `persona` | 多角色：`hutao` / `zhongli` / `qiqi` / `xiao`（原神璃月角色） |
| `domain` | 角色扮演 + 游戏知识问答（Genshin Impact 璃月篇） |
| `content_hash` | `<pending>` —— 数据清洗完成后用 `sha256` 计算并填入 |
| `created_at` | 2026-07-12T00:00:00Z |
| `tags` | `["persona", "role-play", "genshin-impact", "sft", "lora", "chinese"]` |

---

## 2. 数据来源（source）

本数据集由三类来源混合构成，比例为 **60% 合成 / 30% 人工编写 / 10% 知识库改写**。

### 2.1 LLM 合成对话（~60%）

- **生成模型**：Qwen2.5-7B-Instruct（FP16，非 AWQ 版本，温度 0.8）
- **生成方式**：通过 `backend/api/training.py` 的 `generate-dialogues` 接口批量生成
- **生成 prompt 模板**：包含角色描述、场景设定、对话轮数、风格提示
- **每条记录字段**：`conversations`（user/assistant 交替）、`system`（角色 system prompt）、`scene`（场景标签）、`turns`（轮数）、`tags`
- **保留元数据**：生成时的 `temperature`、`model_name`、`generation_prompt`、`cost_time`

### 2.2 人工编写对话（~30%）

- **编写者**：项目作者 + 志愿者
- **编写规范**：参考角色官方语音、剧情台词、性格设定
- **覆盖场景**：寒暄、业务咨询、深度话题、情感表达、跨角色提及
- **质量要求**：每条至少 3 轮，角色风格明显，无事实错误

### 2.3 知识库改写（~10%）

- **来源**：`backend/knowledge_bases/` 中导入的原神攻略、角色介绍、世界设定
- **改写方式**：将知识库 chunk 改写为问答对话形式
- **用途**：增强 RAG 场景下的角色回答能力，确保回答有据可依

---

## 3. 数据预处理（preprocessing）

数据清洗流水线（Phase A 任务，部分已完成，部分进行中）：

1. **格式校验**：确保每条对话为 `{"conversations": [{"from": "user", "value": "..."}, {"from": "assistant", "value": "..."}], "system": "..."}` 结构
2. **去重**：基于 `(system, conversations[0].value)` 元组做精确去重；对 assistant 回复做 MinHash 近似去重（Jaccard 阈值 0.9）
3. **长度过滤**：
   - 对话总长度 < 20 字 → 丢弃
   - 单轮 assistant 回复 > 1024 字 → 截断并标记
   - 对话轮数 < 2 → 丢弃
4. **格式检查**：
   - 检测并移除残留的 prompt 模板标记（如 `{character}`、`<|im_start|>`）
   - 检测并修正未闭合的引号、括号
5. **对话级切分**：按 `conversation_id` 切分 train/val/test，避免同一对话的不同轮次跨 split 泄露
6. **角色一致性预检**：用 `backend/evaluation/persona_metrics.py` 的 `style_consistency` 和 `contradiction_rate` 对合成数据做规则过滤，矛盾率 > 0.3 的样本移入审核队列
7. **安全过滤**：用 `backend/evaluation/safety_test_set.json` 的注入/泄露 prompt 做反向检测，若 assistant 回复未拒绝则移入审核队列
8. **token 化**：使用 Qwen2.5 tokenizer，`max_source_length=2048`，label mask user 部分（`-100`）

---

## 4. 训练/验证/测试分割（train_val_test_split）

按**对话级**而非随机行分割，固定随机种子 `seed=42`：

| Split | 比例 | 预估条数 | 用途 |
| --- | --- | --- | --- |
| `train` | 80% | ~960 | LoRA SFT 训练 |
| `val` | 10% | ~120 | 训练中 eval_loss / 早停 |
| `test` | 10% | ~120 | 训练后困惑度、Distinct-N、人工盲评 |

**注意**：
- 同一 `conversation_id` 的所有轮次必须在同一 split
- held-out 评测（`gold_prompts.json` 中 `split=held_out` 的 34 条）**不参与**上述分割，是独立的人造 Gold Set
- 分割脚本记录 `split_manifest.json`，包含每条对话的 id 和所属 split，便于复现

---

## 5. 角色定义（persona）

| 角色 | 关键词（用于风格一致性检测） | 事实约束（用于矛盾检测） | system prompt 摘要 |
| --- | --- | --- | --- |
| `hutao`（胡桃） | 胡桃、往生堂、堂主、嘿嘿、本堂主、生死、葬仪 | 第七十七代堂主；火元素；长柄武器 | 活泼俏皮，谈论生死举重若轻 |
| `zhongli`（钟离） | 钟离、契约、摩拉、岩王帝君、璃月、摩拉克斯 | 岩王帝君；岩元素；曾签订契约 | 沉稳儒雅，重视契约与秩序 |
| `qiqi`（七七） | 七七、不卜庐、记不住、忘了、嗯、僵尸、琥珀 | 僵尸；不卜庐工作；记忆不好 | 缓慢断续，天真无邪 |
| `xiao`（魈） | 魈、降魔、夜叉、业障、璃月、守护、哼、无需 | 护法夜叉；风元素；守护璃月 | 冷淡寡言，背负业障 |

完整角色关键词与事实见 [backend/evaluation/persona_metrics.py](../../backend/evaluation/persona_metrics.py)。

---

## 6. 已知风险（risks）

| 风险类别 | 描述 | 缓解措施 |
| --- | --- | --- |
| **版权风险** | 原神角色、世界观、台词版权归 miHoYo/HoYoverse | 仅用于非商业学术研究；不 redistribution；LoRA 权重不公开发布 |
| **角色失真** | 合成数据可能偏离官方设定 | 人工编写样本作锚点；`contradiction_rate` 规则过滤；held-out Gold Set 评测 |
| **安全漂移** | 角色扮演可能被用于绕过安全限制 | `safety_test_set.json` 25 类注入/泄露 prompt 反向检测；SecurityMiddleware prompt 注入检测 |
| **数据泄露** | train/test 分割不当导致评测虚高 | 对话级分割；held-out Gold Set 与训练集完全独立 |
| **文化偏差** | 中文语境下的生死、宗教话题可能引发不适 | 人工审核；胡桃角色对话避免具体宗教描述；保留拒答能力 |
| **合成数据同质化** | LLM 合成数据多样性不足 | MinHash 去重；温度 0.8 + 多场景 prompt；Distinct-N 监控 |
| **事实幻觉** | 角色可能编造游戏内不存在的设定 | RAG 检索约束；`expected_refs` 校验；低置信度弃答 |

---

## 7. 预期用途（intended_use）

### 7.1 允许的用途

- LoRA / DoRA / RSLoRA / QLoRA 参数高效微调实验
- 角色一致性、RAG 可信性、安全鲁棒性的学术评测
- 偏好对齐（DPO/ORPO）的 SFT 基线训练
- 中文领域 PEFT 方法的消融研究

### 7.2 不允许的用途

- 商业化部署或付费服务
- 将 LoRA 权重或训练数据公开发布到 HuggingFace 等平台
- 用于训练通用聊天模型（数据仅覆盖 4 个原神角色，不具备通用性）
- 用于生成误导性游戏攻略或冒充官方

### 7.3 超出范围的场景

- 非 Genshin Impact 语境的角色扮演
- 多语言场景（仅中文）
- 长文本生成（单轮最长 1024 字）
- 实时信息查询（无联网能力，知识截止于训练数据）

---

## 8. 评测数据集（配套，非训练数据）

本数据集配套以下评测集，均位于 `backend/evaluation/`：

| 评测集 | 文件 | 条数 | 用途 |
| --- | --- | --- | --- |
| Gold Set | `gold_prompts.json` | 105 | 角色一致性、安全、RAG、事实、多轮综合评测 |
| 安全测试集 | `safety_test_set.json` | 100+ | 注入抵抗、密钥泄露、有害请求拒绝 |
| 检索评测集 | `retrieval_eval_dataset.json` | 30+ | RAG Recall@k、MRR、nDCG、引用正确率 |
| 意图样本 | `../intent_samples/samples.json` | 200+ | 意图分类器训练与评测 |

Gold Set 分布（已通过 `GoldSetManager.validate_set()` 校验，0 错误）：

| 类别 | eval | held_out | 合计 |
| --- | --- | --- | --- |
| `persona` | 15 | 10 | 25 |
| `safety` | 15 | 10 | 25 |
| `rag_grounded` | 15 | 5 | 20 |
| `factual` | 15 | 5 | 20 |
| `multiturn` | 11 | 4 | 15 |
| **合计** | **71** | **34** | **105** |

---

## 9. 版本与复现

- **当前版本**：v1.0（2026-07-12）
- **随机种子**：`seed=42`（训练、分割、采样统一）
- **基座模型**：`Qwen2.5-7B-Instruct`（FP16 训练）/ `Qwen2.5-7B-Instruct-AWQ`（推理）
- **Tokenizer**：Qwen2.5 原生 tokenizer，`chat_template.jinja` 见 `loras/hutao_lora_7b/final/`
- **训练框架**：PEFT 0.19+ / TRL 0.45+ / bitsandbytes
- **复现命令**：
  ```bash
  cd backend
  python -m training.trainer --lora_name hutao_lora_7b --dataset_name persona_hutao --seed 42
  ```

### 变更日志

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-07-12 | 初始版本：4 角色、~1200 对话、105 条 Gold Set、对话级分割 |

---

## 10. 引用

如本数据集或评测框架用于学术研究，请引用：

```text
QQChat Enhanced: A multi-platform LLM system prototype with LoRA persona adaptation,
hybrid RAG, AWQ inference, and evidence-driven evaluation.
Project repository: https://github.com/despaoy/qqchat-enhanced
```

---

## 11. 与 Schema 的对应关系

本文件字段与 `backend/evaluation/dataset_card_schema.py` 的 `DatasetCard` Pydantic 模型一一对应：

```python
class DatasetCard(BaseModel):
    schema_version: int = 1                    # → 第 1 节
    name: str                                   # → 第 1 节
    source: str = ""                            # → 第 2 节
    license: str = "unknown"                    # → 第 1 节
    language: List[str]                         # → 第 1 节
    size: int = 0                               # → 第 1 节
    persona: Optional[str] = None               # → 第 5 节
    domain: str = ""                            # → 第 1 节
    risks: List[str] = Field(default_factory=list)      # → 第 6 节
    intended_use: str = ""                      # → 第 7 节
    preprocessing: List[str] = Field(default_factory=list)  # → 第 3 节
    train_val_test_split: Dict[str, int]        # → 第 4 节
    content_hash: str = ""                      # → 第 1 节（pending）
    created_at: str = ""                        # → 第 1 节
    tags: List[str] = Field(default_factory=list)       # → 第 1 节
```
