# 月社妃实验总览

> 当前唯一研究主线：[月社妃 LLM 研究主线 v3](KISAKI_LLM_RESEARCH_PROGRAM_V3.md)。

## 当前状态

- `prompt-v1 pilot` 已冻结：E1 胜 26、E2 胜 32、平局 62，双侧精确符号检验 `p=0.512`。该结果不可改写，也不作为 prompt-v2 正式结论。
- R0：canonical train 826、validation 92、Gold v2 150 已冻结；`kisaki_system_prompt_v2.txt` 已建立。
- R1：E1/E2 adapter 已完成；E3 DoRA、E4 RSLoRA、E5 Packing 的单变量配置与安全队列已就绪。
- R2：60 条 held-out 候选已生成，等待人工冻结。
- R3：真实 SSE TTFT 基准器已实现，等待隔离服务测试。
- R4：等待至少 100 条月社妃人工批准偏好对。
- S1：等待最终路由与 AstrBot 系统验收。

## 权威文件

| 作用 | 文件 |
|---|---|
| 静态研究定义 | `backend/data/character_dialogues/experiments/research/research_program_registry_v3.json` |
| R1 运行前检查 | `scripts/validate_kisaki_experiments.py` |
| R1 E1-E5 配置 | `backend/data/character_dialogues/experiments/configs/kisaki_e*_canonical.json` |
| prompt v2 | `backend/data/character_dialogues/kisaki_system_prompt_v2.txt` |
| Gold v2 | `backend/evaluation/kisaki_gold_set_v2.json` |
| Seed 42 prompt-v1 pilot | [盲评结果](reviews/KISAKI_SEED42_BLIND_REVIEW_RESULT.md) |
| 历史资产索引 | `backend/data/character_dialogues/experiments/legacy_result_index.json` |

## 规则

1. 设计注册表、服务器运行清单和实验结果分开保存。
2. mock 只能验证界面和流程，必须显示“演示数据”，不能进入报告。
3. 旧 E2/E2'/E2'' 是 `legacy_exploratory_non_comparable`。
4. RAG 引用属于结构化响应，不训练人物正文输出文档 ID。
5. 单种子只称 pilot；最终只为 E1 与最佳变体补 Seed 43/44。