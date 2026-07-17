# 初学者真实 LLM 实验操作指南

本文按当前项目的真实状态编写。目标不是一次把所有实验跑完，而是让每一步都有明确目的、可复现输入和可解释结果。

## 1. 你已经完成了什么

截至 2026-07-14，已经完成以下真实实验：

1. 实验室服务器可以运行 vLLM 0.6.3.post1，真实推理模型为 `Qwen2.5-7B-Instruct-AWQ`。
2. vLLM 已同时挂载 `hutao`、`minamo` 和新训练的 `kisaki` LoRA。
3. Minamo 已完成基础模型和 LoRA 各 150 条真实评测，并完成一次标注为 AI-assisted 的 DeepSeek 初审。
4. 月社妃已用普通非量化 Qwen2.5-7B 完成 rank-32 LoRA 训练；早停在 200/228 步触发，并恢复 checkpoint-50。
5. 月社妃基础模型和 LoRA 已完成各 150 条真实评测，匿名 A/B 包已生成。
6. 新增了自动质量门禁，能识别安全退化、RAG 引用失败和短回复塌缩。
7. 当前月社妃 LoRA 未通过门禁，只能作为失败分析实验，不能设为生产默认模型。

这次失败不是白跑：它证明了“训练成功”和“质量合格”是两回事。你已经获得一份很适合答辩展示的完整证据链：数据统计、训练曲线、早停、真实推理、自动指标、质量门禁和失败案例。

目前最重要的工作是先修复月社妃数据分布，再做受控的学习率实验；DoRA、RSLoRA 和 DPO/ORPO 应排在新的 SFT 基线通过门禁之后。

## 2. 先理解四个容易混淆的名词

### 2.1 训练

训练会修改 LoRA 参数，需要 GPU，并会持续数十分钟到数小时。训练的输出是一个适配器目录，不是评测分数。

### 2.2 推理

推理是让训练好的模型回答问题。vLLM 负责推理。推理不会继续训练模型。

### 2.3 自动评测

自动评测统计成功率、延迟、重复率和引用格式。这些指标便宜、稳定，但不能完全判断“像不像角色”。

### 2.4 人工盲评

盲评把模型名称隐藏为 A 和 B。你只比较回复质量，不知道哪一侧是基础模型或 LoRA，从而减少主观偏见。

## 3. 本地和服务器分别做什么

| 位置 | 适合做的工作 | 原因 |
| --- | --- | --- |
| Windows 本地 | 人工盲评、偏好审核、查看 JSON 和报告、Git 提交 | 不需要 GPU，操作方便 |
| 实验室服务器 | LoRA 训练、vLLM 推理、RAG embedding/reranker、性能测试 | 有 RTX 3090 和完整模型 |

不要在本地 4060 Laptop 上重复服务器的 7B 全量实验。本地显卡适合小规模 smoke test，正式指标统一在 3090 上产生。

## 4. 第一个任务：完成 Minamo 人工盲评

### 4.1 进入项目目录

在 Windows PowerShell 中运行：

```powershell
cd C:\Users\13474\Desktop\qqchat-enhanced
```

作用：后续命令中的相对路径都从项目根目录开始。如果目录不对，Python 会提示找不到脚本或数据文件。

### 4.2 开始审核

```powershell
py -3.12 scripts\review_blind_ab.py `
  --input backend\data\character_dialogues\experiments\results\real_vllm_20260714\shenbai_mizunamo_blind_ab\blind_review.json `
  --reviewer "szw"
```

作用：逐条显示同一个问题的 A、B 两个匿名回复。脚本不会读取 `blind_key.json`，因此你不知道模型身份。

命令含义：

- `a`：A 明显更好。
- `b`：B 明显更好。
- `t`：两者质量接近，判为平局。
- `i`：问题本身无法判断、上下文缺失或两边都无效。
- `s`：暂时跳过。
- `q`：保存并退出；下次运行同一命令会继续未审核样本。

每次建议审核 20-30 条，然后休息。不要为了让 LoRA 获胜而猜测 A/B 身份。

### 4.3 每类样本看什么

| 类别 | 主要判断内容 |
| --- | --- |
| `persona` | 是否像神白水菜萌，语气、称呼、情绪和表达是否自然 |
| `factual` | 是否答对问题，是否编造人物关系或剧情 |
| `multiturn` | 是否理解前文，代词和人物关系是否连贯 |
| `safety` | 是否拒绝泄露密钥、执行危险命令，同时避免无理由过度拒答 |
| `rag_grounded` | 回答是否只依据给定证据，引用的文档 ID 是否正确 |

理由要写具体，例如“B 保持了水菜萌语气且直接回应问题，A 像通用助手”，不要只写“B 更好”。

### 4.4 查看进度

```powershell
py -3.12 scripts\review_blind_ab.py `
  --input backend\data\character_dialogues\experiments\results\real_vllm_20260714\shenbai_mizunamo_blind_ab\blind_review.json `
  --reviewer "szw" `
  --summary
```

作用：只显示 A、B、tie、invalid 和 pending 数量，不进入交互审核。

审核结果默认写入 `blind_review_reviewed.json`。原始文件不会被修改。

### 4.5 全部完成后揭盲

只有 `pending=0` 后才能运行：

```powershell
py -3.12 scripts\score_blind_ab.py `
  --review backend\data\character_dialogues\experiments\results\real_vllm_20260714\shenbai_mizunamo_blind_ab\blind_review_reviewed.json `
  --key backend\data\character_dialogues\experiments\results\real_vllm_20260714\shenbai_mizunamo_blind_ab\blind_key.json `
  --output backend\data\character_dialogues\experiments\results\real_vllm_20260714\shenbai_mizunamo_blind_ab\blind_score.json
```

作用：把 A/B 映射回真实模型，计算基础 AWQ 和 Minamo LoRA 的胜场、决定性样本胜率及分类别结果。

合理结论应写成：

> 在 150 条留出样本上，排除平局和无效样本后，Minamo LoRA 的人工盲评胜率为 X%；自动重复率由 2.56% 降到 1.37%。

不要只挑几个优秀回复，也不要在盲评前打开密钥文件。

## 5. 第二个任务：审核 DPO/ORPO 偏好候选

这和上面的 A/B 模型盲评不是一件事：

- 模型盲评回答“LoRA 是否比基础模型更好”。
- 偏好审核回答“这条 chosen/rejected 是否足够可靠，可用于偏好训练”。

Minamo：

```powershell
py -3.12 scripts\review_preference_candidates.py `
  --input backend\data\character_dialogues\experiments\research\shenbai_mizunamo_preference_candidates.jsonl `
  --reviewer "szw"
```

月社妃：

```powershell
py -3.12 scripts\review_preference_candidates.py `
  --input backend\data\character_dialogues\experiments\research\tsukiyashiro_kisaki_preference_candidates.jsonl `
  --reviewer "szw"
```

作用：批准真正有明确偏好关系的样本，拒绝 chosen/rejected 都合理、都很差或事实不确定的样本。

达到 50 条以上高质量 approved 后才建议做 DPO/ORPO pilot。它属于偏好优化，不应称为 RLHF。

## 6. 第三个任务：准备月社妃 LoRA 训练

### 6.1 连接服务器

```bash
ssh szw@192.168.166.7
cd /home/szw/lhm2/qqchat-enhanced
```

作用：进入只属于你的项目目录。不要使用 `sudo`，不要修改 `/home/szw/lhm2/` 之外的文件。

### 6.2 检查代码和 GPU

```bash
git status -sb
nvidia-smi
ps -fu "$USER" | grep -E '[v]llm|[t]rainer.py'
```

作用：

- `git status` 防止拉取代码时覆盖未提交文件。
- `nvidia-smi` 判断显卡是否空闲。
- `ps` 只检查你自己的 vLLM/训练进程。

如果某块 GPU 显存已接近 24 GB，不要在那块卡上启动训练，也不要结束其他用户进程。

### 6.3 检查训练基础模型

```bash
test -f /home/szw/lhm2/runtime/models/Qwen2.5-7B-Instruct/config.json \
  && echo "训练模型存在" \
  || echo "缺少非 AWQ 训练模型"
```

作用：LoRA 训练应使用普通 `Qwen2.5-7B-Instruct`，而不是用于推理的 AWQ 模型。

如果这里只显示“缺少非 AWQ 训练模型”，先停止，不要把 AWQ 路径填进训练配置。需要从可联网机器通过 ModelScope 下载普通模型，再传入 `/home/szw/lhm2/runtime/models/Qwen2.5-7B-Instruct/`。

### 6.4 检查训练数据

```bash
/home/szw/lhm2/envs/qqchat-gpu/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("backend/data/character_dialogues/experiments/tsukiyashiro_kisaki_train.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("训练样本数:", len(d))
print("首条 ID:", d[0]["id"])
print("对话轮数:", len(d[0]["conversations"]))
PY
```

作用：确认文件能以 UTF-8 解析、不是空数据，并抽查格式。这里只输出统计，不会修改数据。

### 6.5 理解训练配置

配置文件已经准备好：

`backend/data/character_dialogues/experiments/configs/tsukiyashiro_kisaki_lora_r32.json`

关键参数：

- `lora_r=32`：低秩矩阵容量；越大参数越多，不保证效果越好。
- `lora_alpha=64`：LoRA 更新的缩放强度。
- `learning_rate=2e-4`：每一步参数更新幅度。
- `num_train_epochs=3`：完整读取训练集三次。
- `batch_size=1` 和 `gradient_accumulation_steps=8`：降低单步显存，同时形成有效 batch。
- `gradient_checkpointing=true`：用额外计算换显存。
- `packing=false`、`NEFTune=0`：先建立最简单基线，后续一次只改变一个因素。
- `use_dora=false`、`use_rslora=false`：基线不启用两种变体。

DoRA 和 RSLoRA 在库层面可能同时打开，但受控消融实验中不要同时启用，否则无法判断提升来自哪种方法。

## 7. 第四个任务：训练月社妃基线 LoRA

训练前必须保证选择的 GPU 空闲，并停止占用同一块 GPU 的你自己的 vLLM。初学阶段不要自行 `kill -9`；先用 `ps -fp PID` 确认进程属于自己，再正常停止。

假设 GPU 1 已空闲：

```bash
cd /home/szw/lhm2/qqchat-enhanced/backend
CUDA_VISIBLE_DEVICES=1 \
  /home/szw/lhm2/envs/qqchat-gpu/bin/python -m training.trainer \
  --config ../backend/data/character_dialogues/experiments/configs/tsukiyashiro_kisaki_lora_r32.json
```

作用：加载普通 Qwen2.5-7B、冻结基础参数，只训练月社妃 LoRA，并输出 TensorBoard 日志、检查点、最终适配器和评测结果。

训练时另开一个 SSH 窗口观察：

```bash
watch -n 2 nvidia-smi
```

正常现象：显存稳定、loss 整体下降但有波动、GPU 利用率周期变化。

异常现象：

- `CUDA out of memory`：先确认 vLLM 已停；再减小序列长度或改成 QLoRA，不要反复盲目重跑。
- loss 变成 `nan`：停止训练，降低学习率并检查数据。
- 温度持续过高：停止实验并等待散热。
- 基础模型路径不存在：补齐普通 Instruct 模型，不要改成 AWQ 路径。

训练完成后检查：

```bash
find /home/szw/lhm2/runtime/loras/kisaki/lora_r32 -maxdepth 2 \
  -type f -printf '%P\n' | sort
```

至少应看到 `final/adapter_config.json` 和 `final/adapter_model.safetensors`。

## 8. 第五个任务：把月社妃 LoRA 挂到 vLLM

重新启动 vLLM 时需要：

1. 保留基础模型 `qwen2.5-7b-instruct-awq`。
2. 在 `--lora-modules` 中增加：

```text
kisaki=/home/szw/lhm2/runtime/loras/kisaki/lora_r32/final
```

3. 把 `--max-loras 2` 调整为至少 `--max-loras 3`。
4. 保留 `--max-lora-rank 64`，因为当前 rank 32 未超过限制。

启动后验证：

```bash
curl -fsS http://127.0.0.1:8001/v1/models
```

作用：确认返回结果中同时出现基础模型、`minamo`、`hutao` 和 `kisaki`。仅看到目录存在不等于 vLLM 已成功加载。

## 9. 第六个任务：真实评测月社妃 LoRA

```bash
cd /home/szw/lhm2/qqchat-enhanced
/home/szw/lhm2/envs/qqchat-gpu/bin/python \
  backend/evaluation/character_benchmark.py \
  --dataset backend/data/character_dialogues/experiments/tsukiyashiro_kisaki_eval.json \
  --rag-documents backend/data/character_dialogues/experiments/tsukiyashiro_kisaki_rag_documents.json \
  --model kisaki \
  --output /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_lora.json \
  --base-url http://127.0.0.1:8001 \
  --max-tokens 256 \
  --timeout 120 \
  --gpu 1
```

作用：使用与基础模型完全相同的 150 条留出集、生成参数和硬件条件测试月社妃 LoRA。

随后构建月社妃盲评包：

```bash
/home/szw/lhm2/envs/qqchat-gpu/bin/python scripts/build_blind_ab_review.py \
  --a /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_base_awq.json \
  --b /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_lora.json \
  --output-dir /home/szw/lhm2/runtime/results/character_eval/tsukiyashiro_kisaki_blind_ab \
  --seed 42
```

下载盲评目录到本地后，使用与 Minamo 相同的 `review_blind_ab.py` 流程。

## 9.1 本次月社妃实验的实际结论

本次训练和挂载均成功，但模型质量未达标：

- 最佳 checkpoint 是第 50 步，最佳 eval loss 为 3.52635。
- 后续验证损失持续升高，早停在第 200 步生效。
- LoRA 平均输出只有 8.07 token，基础模型为 161.69 token。
- 安全通过率从 80% 降到 26.67%。
- RAG 引用正确率从 100% 降到 0%。
- 自动质量门禁返回 `passed=false`。

因此不要把 `kisaki` 切为生产默认模型。它保留在 vLLM 中仅用于复现实验和人工盲评。详细数据见 `docs/research/REAL_VLLM_BENCHMARK_REPORT.md`。

下一轮先重建多轮训练数据并平衡极短回复比例，再固定数据做学习率对比。只有新基线通过质量门禁后，才开始 rank、DoRA、RSLoRA、NEFTune、Packing 和 QLoRA 消融。
## 10. 消融实验应该怎么做

月社妃基线通过后，按以下顺序，每次只改一个变量：

1. rank：`r=8/16/32/64`，alpha 固定为 `2*r`。
2. target modules：`q_proj+v_proj` 对比全部线性层。
3. DoRA：只把 `use_dora` 改为 `true`。
4. RSLoRA：只把 `use_rslora` 改为 `true`。
5. NEFTune：只把噪声 alpha 从 0 改为 5。
6. Packing：只把 `packing` 从 false 改为 true。
7. QLoRA：只把 `load_in_4bit` 改为 true，并使用普通模型作为量化来源。

每次保留：配置 JSON、Git commit、数据哈希、随机种子、训练日志、峰值显存、训练时间、最终 adapter、真实评测 JSON 和人工盲评结果。

## 11. RAG 实验排在 LoRA 基线之后

需要比较四条检索链路：

1. vector only：只使用向量相似度。
2. BM25 only：只使用关键词匹配。
3. hybrid：融合向量和 BM25。
4. hybrid + reranker：召回后再用 reranker 排序。

重点指标是 Recall@5、MRR、nDCG@5、平均检索延迟、引用正确率和低置信度拒答率。检索到文档不代表最终回答一定忠实，所以“检索指标”和“答案引用指标”必须分开报告。

## 12. 推荐执行顺序

### 现在

1. 保留当前月社妃 LoRA 和报告，不删除失败实验。
2. 抽查月社妃盲评包中的 20-30 条，确认短回复塌缩与自动指标一致。
3. 用多轮上下文重建月社妃训练集，并生成数据卡和长度分布报告。
4. 给新的 SFT 数据加入经过审核的安全拒答和 RAG 引用样本。

### 新基线

1. 固定新的训练集、评测集和 seed=42。
2. 保持 rank=32、alpha=64 和 target modules 不变，只比较学习率 `5e-5/1e-4/2e-4`。
3. 每次保存 TensorBoard、训练时间、峰值显存、最佳 checkpoint 和真实评测 JSON。
4. 先运行 `benchmark_gate.py`；门禁失败的模型不进入完整人工盲评。

### 基线通过后

1. 完成月社妃与 Minamo 的人工盲评。
2. 依次做 rank、DoRA、RSLoRA、NEFTune、Packing 和 QLoRA 单变量消融。
3. 审核高质量偏好对后再做 DPO/ORPO pilot，不把它描述成 RLHF。
4. 开展 vector、BM25、hybrid、reranker 的 RAG 检索和引用实验。
5. 最后补 AWQ/FP16、动态 LoRA 和 Adapter Merge 的延迟、吞吐与显存基准。
## 13. 每次实验都要记录的内容

```text
实验名称：
日期：
Git commit：
服务器/GPU：
CUDA/PyTorch/vLLM 版本：
基础模型及路径：
LoRA 配置：
训练数据路径和 SHA256：
评测数据路径和 SHA256：
启动命令：
输出目录：
成功数/错误数：
平均延迟/P95/显存：
人工盲评结果：
三个失败案例：
本次结论：
限制与下一步：
```

这份记录是保研展示中最有价值的证据。老师通常更看重你是否知道如何控制变量、解释失败和限制结论，而不是单纯列出用了多少技术名词。
