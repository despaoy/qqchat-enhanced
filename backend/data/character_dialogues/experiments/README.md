# 月社妃实验资产

> 统一导航见 [月社妃实验总览](../../../../docs/research/KISAKI_EXPERIMENT_INDEX.md)。本目录保存可复现的小型研究资产，不保存模型权重、checkpoint、日志或向量索引。

## 当前正式状态

- `canonical_dataset_manifest.json`：826 条训练数据和 92 条固定验证数据的数量、来源与 SHA256。
- `canonical_experiment_registry.json`：KISAKI-E1/E2 配置、唯一变量和当前状态。
- `gold_v2_leakage_audit.json`：文本与 BGE-M3 语义泄漏审计，当前为 `passed`。
- `../../evaluation/kisaki_gold_set_v2.json`：150 条正式冻结 Gold v2。
- `configs/kisaki_e1_canonical.json`：标准 LoRA，NEFTune alpha 0.0。
- `configs/kisaki_e2_canonical.json`：唯一增加 NEFTune alpha 5.0。

当前实验状态为 `ready_for_training`。这表示训练契约完整，并不代表 E1/E2 已训练或已形成质量结论。

## 目录结构

```text
experiments/
├── README.md
├── canonical_dataset_manifest.json       数据事实来源
├── canonical_dataset_exclusions.json     排除与防泄漏记录
├── canonical_experiment_registry.json    正式实验状态
├── gold_v2_leakage_audit.json            Gold 泄漏审计
├── legacy_result_index.json               历史结果索引
├── tsukiyashiro_kisaki_train.json         固定训练集
├── tsukiyashiro_kisaki_eval.json          固定验证集
├── configs/
│   ├── kisaki_e1_canonical.json           正式 E1
│   ├── kisaki_e2_canonical.json           正式 E2
│   └── tsukiyashiro_kisaki_*.json         历史探索配置
├── results/
│   ├── archive/                            明确归档的旧结果
│   └── kisaki_e2*.json                     历史探索结果
└── research/
    └── core_research_registry_v2.json      （已归档至 archive/legacy_v3_superseded/，被 v3 取代）
```

## 事实来源优先级

1. `canonical_dataset_manifest.json` 和文件 SHA256。
2. `canonical_experiment_registry.json` 与正式配置。
3. 冻结 Gold v2 及其内容哈希。
4. 每次运行生成的 run manifest 和 adapter 哈希。
5. 研究报告。

当报告文字与清单或运行记录冲突时，以前四项为准。

## 可复现命令

从仓库根目录执行：

```bash
python scripts/build_kisaki_canonical.py
python scripts/build_kisaki_gold_v2.py
python scripts/review_kisaki_gold_v2.py summary
python scripts/validate_kisaki_experiments.py --write-registry
```

`build_kisaki_gold_v2.py` 会生成待审核候选，不能替代已经冻结的正式 Gold。重新构建后必须重新完成人工审核、文本/语义泄漏审计和冻结流程。

服务器正式预检：

```bash
python scripts/validate_kisaki_experiments.py --require-model --formal-eval
```

## 状态含义

- `ready_for_training`：数据、配置、模型和 Gold 契约通过。
- `training_complete`：adapter 训练完成。
- `automatic_evaluation_passed`：自动指标与门禁通过。
- `blind_review_complete`：匿名 A/B 人工盲评完成。
- `conclusion_ready`：多随机种子结果和盲评证据完整。

历史 E1/E2/E2'/E2'' 统一标记为 `legacy_exploratory_non_comparable`，不得与新的 KISAKI-E1/E2 混合形成正式结论。