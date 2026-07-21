# 月社妃角色数据

> 当前正式训练体系为 KISAKI-CANONICAL-V2。旧 E2/E2'/E2'' 数据仅保留作探索记录。

## Canonical 数据

| 内容 | 文件 | 当前数量 | 用途 |
|---|---|---:|---|
| 训练集 | experiments/tsukiyashiro_kisaki_train.json | 826 | KISAKI-E1/E2 共用 |
| 固定验证集 | experiments/tsukiyashiro_kisaki_eval.json | 92 | 训练损失、早停 |
| 数据清单 | experiments/canonical_dataset_manifest.json | - | 数量、来源、SHA256 |
| 排除记录 | experiments/canonical_dataset_exclusions.json | 2 | 重复与 Gold 泄漏审计 |
| Gold v2 候选 | ../../evaluation/kisaki_gold_set_v2_candidates.json | 150 | 审核与泄漏审计来源 |
| Gold v2 冻结集 | ../../evaluation/kisaki_gold_set_v2.json | 150 | KISAKI-E1/E2 正式评测 |

数量和哈希必须以 canonical_dataset_manifest.json 为准，文档中不再手工维护实验数量。

## 数据边界

- tsukiyashiro_kisaki_raw.jsonl：原始可追溯事件，不直接训练。
- tsukiyashiro_kisaki_sft.json：游戏文本提取源。
- kisaki_llm_generated_v3.json：经审核的生成数据源。
- kisaki_gold_set_v1.json：开发评测集，状态为 development_only。
- kisaki_gold_set_v2_candidates.json：150 条已人工审核候选。
- kisaki_gold_set_v2.json：人工审核、文本泄漏与 BGE-M3 语义泄漏审计通过后的正式冻结集。

## 构建与验证

从仓库根目录执行：

    python scripts/build_kisaki_canonical.py
    python scripts/build_kisaki_gold_v2.py
    python scripts/validate_kisaki_experiments.py --write-registry

三个命令必须可重复执行并产生相同数据哈希。150 条候选均为 `approved`，服务器 BGE-M3 语义审计结果为 `passed`，正式 Gold v2 已冻结。

## 历史数据

tsukiyashiro_kisaki_train_e2*.json、旧配置和旧结果未删除，但属于 legacy_exploratory_non_comparable。它们改变了数据、训练参数和评测规则，不能用于 NEFTune 严格消融结论。
