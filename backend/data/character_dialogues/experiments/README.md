# 月社妃实验目录

## 正式来源

- canonical_dataset_manifest.json：唯一数据事实来源。
- canonical_experiment_registry.json：KISAKI-E1/E2 配置和状态。
- configs/kisaki_e1_canonical.json：标准 LoRA。
- configs/kisaki_e2_canonical.json：仅增加 NEFTune alpha 5.0。

evaluation_manifest.json、lora_ablation_matrix.json 和旧 E2 系列配置是 v1 研究资产，不再作为当前状态来源。

## 状态含义

- ready_for_training：数据和配置契约通过。
- training_complete：adapter 训练完成，尚未形成质量结论。
- automatic_evaluation_passed：自动指标通过。
- gold_frozen：Gold v2 已人工确认并冻结。
- blind_review_complete：人工盲评完成。
- conclusion_ready：前三项证据完整，可用于报告和答辩。

旧结果统一标记为 legacy_exploratory_non_comparable，详见 legacy_result_index.json。
