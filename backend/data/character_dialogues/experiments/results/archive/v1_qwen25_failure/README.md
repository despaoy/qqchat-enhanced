# v1 Qwen2.5-7B 失败实验归档

本目录保留月社妃 LoRA v1（基于 Qwen2.5-7B-Instruct）的失败实验记录，作为科研对照基线。

## 归档原因

- v1 LoRA 基于 Qwen2.5-7B 训练，与 Qwen3-8B 架构不兼容，无法直接使用
- v1 质量门禁失败（`tsukiyashiro_kisaki_quality_gate.json`）：
  - `output_token_ratio = 0.0499`（阈值 0.25）→ 回复塌缩到 8.07 tokens
  - `safety_pass_rate = 0.27`（阈值 0.75）→ 安全护栏崩塌
  - `rag_citation_accuracy = 0.0`（阈值 0.98）→ 丢失引用能力

## 科研价值

这些记录是"问题发现→根因分析→实验验证→闭环改进"叙事的天然素材：
- v1 训练数据已删除（重做 v2），但训练配置和评估结果保留
- v2 重训后将与此基线对比，验证数据治理和方法改进的效果

## 文件清单

| 文件 | 内容 |
|---|---|
| `tsukiyashiro_kisaki_quality_gate.json` | 质量门禁结果（FAIL） |
| `tsukiyashiro_kisaki_training/` | 训练配置、评估、结果 |
| `tsukiyashiro_kisaki_base_awq.json` | 基线（无 LoRA）生成结果 |
| `tsukiyashiro_kisaki_lora.json` | v1 LoRA 生成结果 |
| `tsukiyashiro_kisaki_lora_v2.json` | v1 LoRA v2 生成结果 |
| `tsukiyashiro_kisaki_blind_ab/` | 盲评 A/B 对比 |
| `tsukiyashiro_kisaki_blind_ab_v2/` | 盲评 A/B v2 对比 |

## 关联文档

- [月社妃 LoRA 重训科研路径](../../../../../docs/research/KISAKI_LORA_RETRAIN_PLAN.md)
