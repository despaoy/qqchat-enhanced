# 月社妃旧 E2 系列归档

> 状态：legacy_exploratory_non_comparable。

旧 E2、E2' Safety++、E2'' RAG 是有价值的工程探索，但不是严格消融实验：

| 历史实验 | 实际源数据 | 实际训练/内部验证 | NEFTune alpha |
|---|---:|---:|---:|
| E2 | 854 | 768 / 86 | 5.0 |
| E2' | 874 | 786 / 88 | 2.5 |
| E2'' | 899 | 809 / 90 | 2.5 |

它们同时改变了训练数据、NEFTune 参数、推理惩罚和评测规则；E2'' 还把正文文档 ID 当作训练目标，与当前“自然角色回复 + 结构化 citations”契约冲突。Gold v1 与补充数据存在直接重叠，因此旧 citation、安全和角色指标不能用于证明某个单一技术有效。

这些数据、adapter 和结果不会删除，可用于分析模板过拟合、研究安全/RAG 数据构造方式，并展示失败分析和实验设计迭代。

正式实验现统一为 KISAKI-E1 标准 LoRA 与 KISAKI-E2 NEFTune-only。详见 KISAKI_E1_E2_CANONICAL_EXPERIMENT.md。
