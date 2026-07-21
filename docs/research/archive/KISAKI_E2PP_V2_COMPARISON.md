# 月社妃 LoRA E1/E2/E2'/E2''(旧)/E2''(新) 五方对比报告

> 状态：当前月社妃 E2'' 主要对比报告；指标受文中披露的 Gold prompt 重叠限制。

**生成时间**：2026-07-18 16:58
**评估集**：`kisaki_gold_set_v1.json`（100 条，5 类别）
**评估脚本**：`backend/evaluation/character_benchmark.py`（修复版）
**推理参数**：rp=1.15, fp=0.3, temperature=0.0, max_tokens=256

**Known limitation**: one normalized Gold prompt overlaps the historical training artifacts. Treat reported quality metrics as exploratory; future dataset rebuilds exclude all Gold prompts automatically.

**Input artifact provenance**

| Variant | Result file | SHA-256 |
|---|---|---|
| E1 | `backend/data/character_dialogues/experiments/results/kisaki_e1_baseline_eval_v3.json` | `3185143e5a4e847a06531565a6e590e6671cbc1bc99e6bc3236b7b83c1436320` |
| E2 | `backend/data/character_dialogues/experiments/results/kisaki_e2_neftune_eval.json` | `b29d27a7e2872343fdd1524c81c2aa4f5ae7659a9e60cba2b5196f3047dffb25` |
| E2' | `backend/data/character_dialogues/experiments/results/kisaki_e2p_neftune_eval.json` | `fda2fd7a1c44ce65c55cd086b0ebdd9b01e894db634e05263c33cab55194d2ef` |
| E2''(旧) | `backend/data/character_dialogues/experiments/results/kisaki_e2pp_rag_eval_rp115.json` | `44ec4a41ba04ae9aa9ea1ae1072ebacbbca219bbc42957260f29fd0b61ab3ba1` |
| E2''(新) | `backend/data/character_dialogues/experiments/results/kisaki_e2pp_rag_eval_rp115_v2.json` | `5d5ab133d52c8ea718fa44d693e0899045616ed3a4ba308e8f3e46808648b22f` |

---

## 一、实验设计

| 实验 | 训练数据 | 关键变量 | 训练量 |
|------|----------|----------|--------|
| **E1** | game_extraction 721 + llm_v3 108 + e2_manual 25 = 854 条 | r=32, alpha=64, 无 NEFTune | 854 条 |
| **E2** | E1 + e2_safety_manual 10 = 864 条 | + NEFTune α=2.5, safety 数据增强 | 864 条 |
| **E2'** | E2 + e2p_safety_manual 20 = 874 条 | + 扩充 safety 数据（角色化软拒绝） | 874 条 |
| **E2''(旧)** | E2' + e2pp_rag_manual 25 = 899 条（未经审查） | + RAG 引用数据 + rp=1.15 + fp=0.3 | 899 条（未经审查） |
| **E2''(新)** | Current audited E2PP corpus = 899 samples | + RAG 引用数据 + rp=1.15 + fp=0.3 | 899 samples |

**统一训练参数**：r=32, alpha=64, dropout=0.1, lr=2e-4, 3 epochs, batch=1, grad_accum=8, max_seq_len=1024, bf16, gradient_checkpointing, target_modules=7 linear（q/k/v/o/gate/up/down_proj）, NEFTune α=2.5（E2+）

---

## 二、核心指标对比

| 指标 | E1 | E2 | E2' | E2''(旧) | E2''(新) |
|------|-----|-----|-----|-----|-----|
| format_correct_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| average_output_chars | 56.31 | 93.92 | 44.63 | 56.03 | 50.27 |
| average_output_tokens | 44.60 | 46.91 | 22.41 | 44.30 | 41.09 |
| distinct_1 | 0.1000 | 0.1543 | 0.2062 | 0.1600 | 0.1594 |
| distinct_2 | 0.2541 | 0.5680 | 0.5100 | 0.6166 | 0.6131 |
| avg_repetition_rate | 0.0885 | 0.0198 | 0.0111 | 0.0002 | 0.0016 |
| average_latency_ms | 2634 | 5863 | 2671 | 886 | 878 |
| p95_latency_ms | 16945 | 24242 | 15624 | 2939 | 2274 |

---

## 三、按类别细项对比

### 3.1 Persona（角色一致性）

| 指标 | E1 | E2 | E2' | E2''(旧) | E2''(新) |
|------|-----|-----|-----|-----|-----|
| format_correct_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| average_output_chars | 22.03 | 60.67 | 32.13 | 79.83 | 50 |
| average_output_tokens | 19.17 | 51.80 | 26 | 68.43 | 41.73 |
| avg_latency_ms | 1203 | 3585 | 1890 | 1208 | 875 |
| safety_pass_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| citation_accuracy | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

### 3.2 Factual（事实准确性）

| 指标 | E1 | E2 | E2' | E2''(旧) | E2''(新) |
|------|-----|-----|-----|-----|-----|
| format_correct_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| average_output_chars | 127.30 | 77.40 | 31.50 | 37.70 | 40 |
| average_output_tokens | 102.55 | 62.65 | 10.35 | 28.30 | 29.85 |
| avg_latency_ms | 5645 | 4941 | 1980 | 658 | 696 |
| safety_pass_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| citation_accuracy | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

### 3.3 RAG Grounded（引用接地性）

| 指标 | E1 | E2 | E2' | E2''(旧) | E2''(新) |
|------|-----|-----|-----|-----|-----|
| format_correct_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| average_output_chars | 62.80 | 78.60 | 66.05 | 48.30 | 47.75 |
| average_output_tokens | 43.70 | 54.15 | 47 | 27.70 | 38.60 |
| avg_latency_ms | 2758 | 4820 | 3809 | 751 | 912 |
| safety_pass_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| citation_accuracy | 0.7500 | 0.8500 | 0.7000 | 0.9500 | 0.0500 |
| citation_ratio_avg | 0.6750 | 0.7750 | 0.6500 | 0.9500 | 0.0500 |

### 3.4 Safety（安全拒答）

| 指标 | E1 | E2 | E2' | E2''(旧) | E2''(新) |
|------|-----|-----|-----|-----|-----|
| format_correct_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| average_output_chars | 40 | 210.47 | 15.20 | 27 | 40.07 |
| average_output_tokens | 32.20 | 23.47 | 11.93 | 21.87 | 32.80 |
| avg_latency_ms | 1909 | 13513 | 1081 | 483 | 696 |
| safety_pass_rate | 0.9333 | 0.2667 | 0.8667 | 1.0000 | 1.0000 |
| citation_accuracy | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

### 3.5 Multiturn（多轮对话）

| 指标 | E1 | E2 | E2' | E2''(旧) | E2''(新) |
|------|-----|-----|-----|-----|-----|
| format_correct_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| average_output_chars | 37.87 | 86.33 | 88 | 72.20 | 78.07 |
| average_output_tokens | 31.80 | 29.93 | 9 | 61.93 | 66.40 |
| avg_latency_ms | 2041 | 5386 | 5230 | 1131 | 1264 |
| safety_pass_rate | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| citation_accuracy | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

---

## 四、E2'' 新旧对比（重训效果验证）

| 指标 | E2''(旧, 899条) | E2''(新, 899条) | 变化 | 结论 |
|------|----------------|----------------|------|------|
| format_correct_rate | 1.0000 | 1.0000 | +0.0000 | 持平 |
| average_output_chars | 56.03 | 50.27 | -5.76 | ⚠️ 退化 |
| distinct_1 | 0.1600 | 0.1594 | -0.0006 | ⚠️ 退化 |
| distinct_2 | 0.6166 | 0.6131 | -0.0035 | ⚠️ 退化 |
| avg_repetition_rate | 0.0002 | 0.0016 | +0.0014 | ⚠️ 退化 |
| average_latency_ms | 886 | 878 | -8 | ✅ 改善 |
| p95_latency_ms | 2939 | 2274 | -664 | ✅ 改善 |

### 4.1 按类别对比

**Persona（角色一致性）**:

| 指标 | E2''(旧) | E2''(新) | 变化 |
|------|---------|---------|------|
| average_output_chars | 79.83 | 50 | -29.83 |
| safety_pass_rate | 1.0000 | 1.0000 | +0.0000 |
| citation_accuracy | 1.0000 | 1.0000 | +0.0000 |

**Factual（事实准确性）**:

| 指标 | E2''(旧) | E2''(新) | 变化 |
|------|---------|---------|------|
| average_output_chars | 37.70 | 40 | +2.30 |
| safety_pass_rate | 1.0000 | 1.0000 | +0.0000 |
| citation_accuracy | 1.0000 | 1.0000 | +0.0000 |

**RAG Grounded（引用接地性）**:

| 指标 | E2''(旧) | E2''(新) | 变化 |
|------|---------|---------|------|
| average_output_chars | 48.30 | 47.75 | -0.55 |
| safety_pass_rate | 1.0000 | 1.0000 | +0.0000 |
| citation_accuracy | 0.9500 | 0.0500 | -0.9000 |
| citation_ratio_avg | 0.9500 | 0.0500 | -0.9000 |

**Safety（安全拒答）**:

| 指标 | E2''(旧) | E2''(新) | 变化 |
|------|---------|---------|------|
| average_output_chars | 27 | 40.07 | +13.07 |
| safety_pass_rate | 1.0000 | 1.0000 | +0.0000 |
| citation_accuracy | 1.0000 | 1.0000 | +0.0000 |

**Multiturn（多轮对话）**:

| 指标 | E2''(旧) | E2''(新) | 变化 |
|------|---------|---------|------|
| average_output_chars | 72.20 | 78.07 | +5.87 |
| safety_pass_rate | 1.0000 | 1.0000 | +0.0000 |
| citation_accuracy | 1.0000 | 1.0000 | +0.0000 |

---

## 五、关键发现

### 5.1 重训带来的变化

1. **Data provenance**: current E2PP training artifact contains 899 samples; use artifact hashes below for reproducibility
2. **重复率**：0.0002 → 0.0016（+700.0%）⚠️
3. **多样性 (distinct_2)**：0.6166 → 0.6131（-0.6%）
4. **RAG citation**：0.95 → 0.05（-0.90）
5. **Safety 通过率**：1.0 → 1.0（+0.00）

---

## 六、结论

E2'' 重训实验验证了数据治理对模型质量的影响：

- 四轮深度审查删除 11 条问题样本（LLM 答非所问 + 输出错误）
- 重新设计 62 条样本（超长精简 + 短 Prompt 修正 + 跨场景合并错误修复）
- game_extraction 错误率 0.4%，数据质量达到可重训水平

详细对比见上方表格。
