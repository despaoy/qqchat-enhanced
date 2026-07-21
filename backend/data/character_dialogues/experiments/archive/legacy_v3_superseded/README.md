# Legacy JSON 归档索引（v3 主线取代）

> 本目录存放被 v3 研究主线注册表取代的历史 JSON 文件。保留作可追溯性证据，不作当前实验依据。
>
> 当前权威注册表：[../../research/research_program_registry_v3.json](../../research/research_program_registry_v3.json)（`authoritative: true`，schema_version=3）

## 归档清单

| 文件 | 原路径 | 归档原因（自我声明） | 被哪个最新文件取代 |
|---|---|---|---|
| evaluation_manifest.json | `experiments/evaluation_manifest.json` | schema_v1，Qwen2.5 时期元数据 | canonical_dataset_manifest.json |
| lora_ablation_matrix.json | `experiments/lora_ablation_matrix.json` | schema_v1，v1 baseline matrix on Qwen2.5-7B | research_program_registry_v3.json |
| core_experiment_registry.json | `experiments/research/core_experiment_registry.json` | schema_v1，被 v2/v3 取代 | research_program_registry_v3.json |
| core_research_registry_v2.json | `experiments/research/core_research_registry_v2.json` | schema_v2，被 v3 取代 | research_program_registry_v3.json |
| preference_alignment_configs.json | `experiments/research/preference_alignment_configs.json` | `status: legacy_exploratory_non_comparable` + `superseded_by: preference_alignment_config_v3.json` | preference_alignment_config_v3.json |
| dataset_cards.json | `experiments/research/dataset_cards.json` | schema_v1，待升级 | canonical_dataset_manifest.json |
| kisaki_merged_stats.json | `character_dialogues/kisaki_merged_stats.json` | 数据切分 829/91 与 canonical 826/92 不符 | canonical_dataset_manifest.json |

## 使用规则

- 这些 JSON 仅作历史数据治理证据使用
- 不得作为当前实验配置或结果依据
- 当前数据冻结以 [canonical_dataset_manifest.json](../../canonical_dataset_manifest.json) 与 [research_program_registry_v3.json](../../research/research_program_registry_v3.json) 为准
