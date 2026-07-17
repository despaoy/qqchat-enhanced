# 月社妃角色对话训练数据（v2）

## 文件说明

- `tsukiyashiro_kisaki_raw.jsonl`：完整可追溯语料，用于覆盖审计，不直接训练。
- `tsukiyashiro_kisaki_sft.json`：推荐训练集，过短回复占比已控制（≤15%）。
- `tsukiyashiro_kisaki_sft_full.json`：上下文有效的完整候选集，仅去除完全相同问答。
- `tsukiyashiro_kisaki_excluded.jsonl`：排除候选及原因，避免静默丢数据。
- `manifest.json` / `coverage_report.json`：覆盖率与排除统计。

## v2 改进

- 适配 gametext/纸上魔法使/*.txt 数据源
- 移除已清除的深白水波（ATRI）相关代码
- 新增过短回复（<5字）占比控制（≤15%），缓解 v1 回复塌缩
- 保留质量评分、去重、excluded 审计逻辑

## 使用建议

默认训练 sft 文件；先人工抽查 excluded；按剧情文件划分训练/验证集；固定数据哈希、脚本版本和随机种子。
