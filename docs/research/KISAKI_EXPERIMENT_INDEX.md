# 月社妃实验总览

> 本文档是月社妃研究资产的统一导航入口。实验事实以数据清单、实验注册表、冻结 Gold 和运行清单为准，历史报告只用于说明探索过程。

## 当前状态

| 项目 | 状态 | 事实来源 |
|---|---|---|
| Canonical 训练集 | 826 条，已冻结 | [canonical_dataset_manifest.json](../../backend/data/character_dialogues/experiments/canonical_dataset_manifest.json) |
| 固定验证集 | 92 条，已冻结 | [canonical_dataset_manifest.json](../../backend/data/character_dialogues/experiments/canonical_dataset_manifest.json) |
| Gold v2 | 150 条，人工审核及文本/语义泄漏审计通过 | [kisaki_gold_set_v2.json](../../backend/evaluation/kisaki_gold_set_v2.json) |
| KISAKI-E1 | 标准 LoRA，等待 seed 42 正式训练 | [kisaki_e1_canonical.json](../../backend/data/character_dialogues/experiments/configs/kisaki_e1_canonical.json) |
| KISAKI-E2 | LoRA + NEFTune alpha 5.0，等待 seed 42 正式训练 | [kisaki_e2_canonical.json](../../backend/data/character_dialogues/experiments/configs/kisaki_e2_canonical.json) |
| 正式结论 | 尚未形成 | 需完成训练、自动评测和匿名 A/B 人工盲评 |

E1 与 E2 的唯一训练变量是 `neftune_noise_alpha`。历史 E1/E2/E2'/E2'' 使用不同数据或评测规则，统一标记为 `legacy_exploratory_non_comparable`。

## 推荐阅读顺序

1. [人物画像](KISAKI_CHARACTER_PROFILE.md)：人物事实、语言风格和关系边界。
2. [Canonical E1/E2 实验设计](KISAKI_E1_E2_CANONICAL_EXPERIMENT.md)：研究问题、固定条件和通过标准。
3. [Gold v2 审核说明](KISAKI_GOLD_V2_AI_PRESCREEN.md)：题目审核、语义泄漏处理和冻结状态。
4. [实验数据目录说明](../../backend/data/character_dialogues/experiments/README.md)：数据、配置、结果与历史资产的位置。
5. [LoRA 后续研究计划](KISAKI_LORA_RETRAIN_PLAN.md)：DoRA、RSLoRA、QLoRA 等后续消融方向。

## 目录分工

```text
backend/data/character_dialogues/
├── tsukiyashiro_kisaki_raw.jsonl       原作直接台词与来源定位
├── kisaki_system_prompt.txt             统一角色系统提示词
└── experiments/
    ├── canonical_dataset_manifest.json  数据数量、来源和 SHA256
    ├── canonical_experiment_registry.json
    ├── configs/                         正式与历史训练配置
    ├── results/                         可提交的小型结果与历史索引
    └── research/                        后续研究注册表

backend/evaluation/
├── kisaki_gold_set_v2_candidates.json   审核过程数据
├── kisaki_gold_set_v2.json              正式冻结评测集
├── character_benchmark_v3.py            角色质量评测
├── rag_benchmark_v2.py                  RAG 检索与引用评测
└── benchmark_gate_v2.py                 自动质量门禁

scripts/
├── build_kisaki_canonical.py             构建固定训练/验证集
├── build_kisaki_gold_v2.py               构建 Gold 候选集
├── audit_kisaki_gold_semantic.py         BGE-M3 语义泄漏审计
├── freeze_kisaki_gold_v2.py              冻结正式 Gold
├── validate_kisaki_experiments.py        检查完整实验契约
├── run_kisaki_experiment.py              运行单个 E1/E2 训练
├── lab-queue-kisaki-e1-e2.sh             共享 GPU 安全队列
├── lab-evaluate-kisaki-seed.sh            真实模型评测
└── aggregate_kisaki_repetitions.py        汇总多随机种子结果
```

模型、adapter、训练 checkpoint、TensorBoard、vLLM 日志和大体积输出位于服务器 `/home/szw/lhm2/runtime`，不进入 Git。

## 正式实验流程

```bash
python scripts/validate_kisaki_experiments.py --require-model --formal-eval
bash scripts/lab-queue-kisaki-e1-e2.sh pilot
```

seed 42 完成后检查自动质量门和失败样本，再决定是否运行 seeds 43/44：

```bash
bash scripts/lab-queue-kisaki-e1-e2.sh replicate
```

每次正式运行必须记录代码 commit、数据哈希、配置哈希、基础模型、随机种子、GPU/CUDA、依赖版本、adapter 哈希和逐样本错误。

## 结果状态

- `ready_for_training`：数据、配置、模型和 Gold 契约通过。
- `training_complete`：adapter 已生成，仅证明训练运行成功。
- `automatic_evaluation_passed`：自动指标和质量门通过。
- `blind_review_complete`：匿名 A/B 人工盲评完成。
- `conclusion_ready`：多随机种子、自动评测和人工盲评证据齐全。

## 历史材料

以下文件保留探索价值，但不进入新的 NEFTune 正式对比：

- [旧 E1 报告](KISAKI_E1_EVAL_REPORT.md)
- [旧 E2'' 报告](KISAKI_E2PP_EVAL_REPORT.md)
- [旧 E2'' 对比](KISAKI_E2PP_V2_COMPARISON.md)
- [旧问题样本](KISAKI_E2PP_V2_PROBLEM_SAMPLES.md)
- [旧对话抽查](KISAKI_E2PP_V2_SAMPLES.md)

历史结果的实际条件和不可比原因见 [legacy_result_index.json](../../backend/data/character_dialogues/experiments/legacy_result_index.json)。