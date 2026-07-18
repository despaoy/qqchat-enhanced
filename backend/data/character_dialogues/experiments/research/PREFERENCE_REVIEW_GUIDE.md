# 偏好数据人工审核指南

> 状态：人工审核规范。AI 初审必须标记为 assisted，不能替代最终人工审核。

## 审核目标

每条记录包含 prompt、chosen 和 rejected。你要判断的不是 chosen 是否完美，而是：

> 在同一个 prompt 下，chosen 是否在角色一致性、事实正确性、安全性和表达质量上明确优于 rejected。

结论不明确时应拒绝该样本，不要为了凑数量批准。

## 开始审核

在项目根目录运行 Minamo：

```powershell
python scripts/review_preference_candidates.py `
  --input backend/data/character_dialogues/experiments/research/shenbai_mizunamo_preference_candidates.jsonl `
  --reviewer "你的姓名或代号"
```

审核月社妃：

```powershell
python scripts/review_preference_candidates.py `
  --input backend/data/character_dialogues/experiments/research/tsukiyashiro_kisaki_preference_candidates.jsonl `
  --reviewer "你的姓名或代号"
```

工具命令：

- a：批准。chosen 已明显优于 rejected。
- r：拒绝。必须记录具体原因。
- e：修改 chosen 后批准。只用于轻微、确定的修正。
- s：暂时跳过，保留 pending。
- q：保存并退出，下次自动继续 pending 样本。

## 五项判定

### 1. Prompt 是否可判断

批准前确认问题清楚、有合理回应空间。缺少关键剧情上下文、指代无法解析或问题本身错误时，选择 r。

### 2. Chosen 是否属于目标角色

检查语气、称呼、价值观、人物关系和世界观。不要仅因为出现角色名字就批准。若回答像通用 AI、混入另一角色口癖或自称错误，选择 r 或 e。

### 3. Chosen 是否正确

检查它有没有捏造原作事实、颠倒人物关系、错误复述用户问题。无法确认的剧情事实先选择 s，核对原文后再决定。

### 4. Rejected 是否真的更差

当前困难负例主要是“另一角色回答”和“不安全服从”。如果 rejected 虽然来自另一角色但对当前问题仍然自然、正确，偏好差异不清晰，应选择 r。

### 5. 困难负例是否成立

当前候选主要使用另一角色的真实回复作为 rejected。检查它是否确实暴露出错误口吻、称呼、人物关系或答非所问。如果 rejected 对当前 prompt 同样合理，则偏好标签不明确，应拒绝该样本。

## 修改与拒绝规范

适合 e 的情况：

- chosen 只有一个明显称呼错误；
- 存在轻微病句或多余模板句；
- 事实主体正确，仅需删去无依据扩写。

必须 r 的情况：

- 需要重写一半以上内容；
- prompt 与 chosen 不对应；
- chosen 和 rejected 各有优劣，无法形成清晰偏好；
- 关键事实无法确认；
- 两个回答都很差或都很好；
- 含敏感信息、错误角色身份或严重剧情污染。

备注应写具体原因，例如“rejected 同样符合月社妃语气，偏好不明确”，不要只写“不好”。

## 审核节奏

1. 先审核 Minamo 20 条，熟悉标准。
2. 回看前 20 条，统一自己的尺度。
3. 每次审核 25-40 条，避免疲劳导致后半段标准变松。
4. 两个角色分别审核，不要交替进行。
5. 完成后随机抽查 approved 的 20%。
6. 最理想是第二名审核者独立审核抽样，记录一致率和 Cohen's kappa。

不要求 100 条全部批准。高质量的 60-80 条通常比勉强批准 100 条更适合小规模 DPO/ORPO。

## 输出文件

以 Minamo 为例，工具会生成：

- shenbai_mizunamo_preference_candidates_reviewed.jsonl：完整审核记录；
- shenbai_mizunamo_preference_candidates_reviewed_approved.jsonl：只包含 approved，可用于训练。

查看进度：

```powershell
python scripts/review_preference_candidates.py `
  --input backend/data/character_dialogues/experiments/research/shenbai_mizunamo_preference_candidates.jsonl `
  --reviewer "你的姓名或代号" `
  --summary
```

正式训练时应把 DPO/ORPO 的 dataset_path 改为 reviewed_approved 文件。先用相同 approved 数据分别运行 DPO 与 ORPO，固定基础模型、SFT adapter、seed、学习率、epoch 和 beta，才能形成有效对比。
