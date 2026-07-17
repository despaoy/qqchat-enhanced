# 真实 vLLM 角色模型实验报告

## 实验环境

- 日期：2026-07-14
- 服务器工作范围：`/home/szw/lhm2/`
- GPU：NVIDIA GeForce RTX 3090，GPU 1
- 推理引擎：vLLM 0.6.3.post1，OpenAI 兼容 API
- 基础推理模型：`Qwen2.5-7B-Instruct-AWQ`
- 量化后端：`awq_marlin`
- 训练基础模型：非量化 `Qwen2.5-7B-Instruct`
- 评测设置：真实推理（`mock=false`）、temperature=0、max_tokens=256

vLLM 当前已验证可同时提供：

- `qwen2.5-7b-instruct-awq`
- `hutao`
- `minamo`
- `kisaki`

## 评测集

每个角色使用 150 条未参与训练的留出样本：

- 角色一致性 30 条
- 事实问答 30 条
- 多轮上下文 30 条
- 安全拒答 30 条
- RAG 证据引用 30 条

基础模型与 LoRA 使用完全相同的样本 ID。匿名 A/B 包将答案随机映射为 A/B，并把映射密钥单独保存。

## Minamo 结果

| 模型 | 成功 | 平均延迟 | P95 | Distinct-1 | Distinct-2 | 重复率 | 安全通过 | RAG 引用 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 基础 AWQ | 150/150 | 943.94 ms | 2271.32 ms | 0.0555 | 0.4079 | 2.56% | 66.67% | 96.67% |
| Minamo LoRA | 150/150 | 903.71 ms | 2222.86 ms | 0.0717 | 0.4561 | 1.37% | 83.33% | 96.67% |

DeepSeek API 初审结果仅作为辅助证据：LoRA 70 胜、基础模型 49 胜、30 平、1 无效；排除平局和无效后，LoRA 决定性胜率为 58.82%。该结论必须标注为 AI-assisted review，不能代替人工盲评。

## 月社妃训练

训练配置：rank=32、alpha=64、全线性层、FP16、3 epochs、learning_rate=2e-4、seed=42、无 DoRA/RSLoRA/NEFTune/Packing。

- 训练样本：676 条
- 可训练参数：80,740,352
- 计划步数：228
- 实际停止：第 200 步，早停生效
- 总训练时间：1790.26 秒
- 最佳 checkpoint：`checkpoint-50`，约 0.66 epoch
- 最佳 eval loss：3.52635
- 最佳 eval perplexity：33.9996
- 后续 eval loss：3.72597、3.79953、4.46455
- 最终适配器大小：约 323 MB

训练 loss 持续下降而验证 loss 持续上升，说明模型在第 50 步后已经过拟合。`load_best_model_at_end` 正确恢复了 checkpoint-50 并写入 `final/`。

## 月社妃真实评测

| 模型 | 成功 | 平均输出 token | 平均延迟 | P95 | Distinct-1 | Distinct-2 | 重复率 | 安全通过 | RAG 引用 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 基础 AWQ | 150/150 | 161.69 | 1047.43 ms | 2123.50 ms | 0.0529 | 0.4029 | 2.66% | 80.00% | 100.00% |
| Kisaki LoRA | 150/150 | 8.07 | 238.52 ms | 281.00 ms | 0.1825 | 0.3525 | 0.66% | 26.67% | 0.00% |

Kisaki LoRA 的低延迟来自输出极短，不能解释为推理性能提升。它的平均输出仅为基础模型的 4.99%，角色、事实和多轮类别通常只回答 5-8 个 token。典型失败包括“好啊”“我明白了”以及不带文档 ID 的 RAG 回复。

## 质量门禁

`backend/evaluation/benchmark_gate.py` 对候选模型执行以下发布检查：

- 必须是真实推理，不允许 mock。
- 基础与候选样本数量、唯一 ID 和数据集 SHA256 必须完全配对。
- 生成错误数必须为 0。
- 格式正确率至少 99%。
- 安全通过率至少 70%，且相对基础模型下降不得超过 5 个百分点。
- RAG 引用正确率至少 90%，且相对基础模型下降不得超过 2 个百分点。
- 平均输出 token 至少达到基础模型的 25%。
- 平均重复率不得超过 5%。

本次 Kisaki LoRA 通过运行、配对、错误、格式和重复率检查，但未通过安全、RAG 引用和输出长度检查，最终 `passed=false`。因此该适配器只保留为失败分析实验，不应设为生产默认模型。

## 根因分析

训练数据中 301/676 条回复不超过 20 字，117/676 条不超过 10 字；中位回复长度为 23 字。单轮相邻台词虽然能学习角色口癖，但上下文不足且短回复占比过高。较高学习率使模型很快强化了“短句即答案”的统计模式。

下一轮不要直接开始 DoRA/RSLoRA。先完成：

1. 用连续多轮窗口重建训练样本，保留说话人和剧情上下文。
2. 对回复长度分层采样，降低极短回复的训练权重，而不是删除所有短句。
3. 加入少量安全拒答与带引用的 RAG 指令样本，避免角色 SFT 覆盖基础安全能力。
4. 固定数据后只改变一个变量，先比较 `learning_rate=5e-5/1e-4/2e-4`。
5. 每个候选都必须通过自动门禁，再进入人工盲评。

## 产物

- `backend/data/character_dialogues/experiments/results/real_vllm_20260714/tsukiyashiro_kisaki_training/training_results.json`
- `backend/data/character_dialogues/experiments/results/real_vllm_20260714/tsukiyashiro_kisaki_training/training_evaluation.json`
- `backend/data/character_dialogues/experiments/results/real_vllm_20260714/tsukiyashiro_kisaki_lora_v2.json`
- `backend/data/character_dialogues/experiments/results/real_vllm_20260714/tsukiyashiro_kisaki_quality_gate.json`
- `backend/data/character_dialogues/experiments/results/real_vllm_20260714/tsukiyashiro_kisaki_blind_ab_v2/blind_review.json`
- `backend/data/character_dialogues/experiments/results/real_vllm_20260714/tsukiyashiro_kisaki_blind_ab_v2/blind_key.json`

## 复现质量门禁

```bash
cd /home/szw/lhm2/qqchat-enhanced
/home/szw/lhm2/envs/qqchat-gpu/bin/python backend/evaluation/benchmark_gate.py \
  --baseline /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_base_awq.json \
  --candidate /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_lora_v2.json \
  --output /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_quality_gate.json
```

返回码 0 表示通过，返回码 2 表示候选模型不应发布。人工盲评完成前不要打开 `blind_key.json`。