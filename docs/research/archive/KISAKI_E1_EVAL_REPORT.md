# 月社妃历史 E1 评估记录

> 状态：legacy_exploratory_non_comparable。本文只保留历史事实，不代表新的 KISAKI-E1。

历史 E1 确实完成了 Qwen3-8B-Instruct BF16 LoRA 训练，实际由 829 条源数据随机切分为 746 条训练和 83 条内部验证；原计划中的固定验证集没有被使用。最佳 checkpoint 为 step 100，历史 final adapter 与该 checkpoint 哈希一致。

历史评测存在以下限制：

- Gold v1 后来影响了数据补充过程，不能继续作为最终盲测证据。
- 三份评测结果采用不同后端或事后重算指标。
- 旧安全词表产生明显假阳性和假阴性。
- 正文文档 ID 与当前结构化 RAG 引用契约冲突。
- 修正后的重复率约为 0.0885，不是早期报告中的 0.0444。

新的标准 LoRA 基线命名为 KISAKI-E1，使用 826 条 canonical train 和 92 条固定 validation。它尚未重新训练，因此当前不能把历史指标写入正式对比表。

当前实验设计见 KISAKI_E1_E2_CANONICAL_EXPERIMENT.md。
