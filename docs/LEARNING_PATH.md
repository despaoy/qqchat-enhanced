# 保研AI技术学习路径

> 面向保研面试的AI技术专长构建路径，以本项目（qqchat-enhanced）为实践载体。
> 原则：**AI核心技术优先（LoRA/意图分类/RAG/推理），工程开发后置**，由浅入深，每个阶段均可在本项目中动手验证。

---

## 总览

| 阶段 | 主题 | 周期 | 优先级 | 本项目实践载体 |
|------|------|------|--------|--------------|
| 0 | AI基础准备 | 1-2周 | 前置 | transformers快速上手 |
| 1 | LoRA训练 | 3-4周 | ⭐核心 | trainer.py + Qwen2.5-7B |
| 2 | 意图分类 | 2-3周 | ⭐核心 | intent_detector + intent_trainer |
| 3 | RAG检索 | 2-3周 | ⭐核心 | rag_helper + reranker + vector_db |
| 4 | vLLM推理服务 | 2周 | 重要 | vllm_client + 多LoRA部署 |
| 5 | 机器人集成 | 1-2周 | 次要 | bot.py (NoneBot2) |
| 6 | 前后端开发 | 2-3周 | 后置 | FastAPI + Next.js |

**面试核心论点**：本项目不是"调包拼装"，而是从**模型训练（LoRA）→ 检索增强（RAG）→ 推理部署（vLLM）→ 应用集成（Bot）**的完整AI工程链路，每个环节都有可解释的技术决策。

---

## 阶段0：AI基础准备（1-2周）

### 学习目标
- 掌握PyTorch张量操作与自动微分
- 理解Transformer架构（Self-Attention/FFN/位置编码）
- 熟悉HuggingFace生态（transformers/datasets/peft）

### 核心概念（面试考点）
| 概念 | 一句话解释 | 深入要点 |
|------|-----------|---------|
| Self-Attention | Q×Kᵀ×V加权求和 | 复杂度O(n²·d)，多头并行 |
| FFN | 两层线性+激活 | 中间维度通常4d，SwiGLU变体 |
| KV Cache | 推理时缓存Key/Value | 避免重复计算，是vLLM优化的基础 |
| Tokenizer | 文本→token ids | BPE/WordPiece，chat template |
| Causal LM | 自回归生成下一个token | 训练时用因果mask |

### 推荐资源
- **论文**：《Attention Is All You Need》（必读，能画出Transformer架构图）
- **课程**：李宏毅《机器学习》深度学习部分（B站）
- **文档**：HuggingFace Transformers官方教程
- **实践**：用transformers加载Qwen2.5-1.5B，跑一次`model.generate()`

### 本项目实践点
- 阅读 [model_manager.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/inference/model_manager.py) 了解模型加载与provider抽象
- 用项目已部署的vLLM（端口8001）调用`/v1/chat/completions`体验推理

### 评估标准
- [ ] 能口述Self-Attention计算流程
- [ ] 能解释为什么Transformer需要位置编码
- [ ] 能用transformers库加载任意模型并生成文本
- [ ] 理解logits→softmax→采样的生成过程

---

## 阶段1：LoRA训练（核心，3-4周）

### 学习目标
- 深入理解LoRA低秩适配原理与数学推导
- 掌握PEFT库的使用与超参数调优
- 能独立完成一次LoRA SFT训练并解释每一步

### 核心概念（面试高频考点）

#### 1.1 LoRA原理（必考）
- **核心思想**：冻结预训练权重W，学习低秩增量 ΔW = B×A，其中A∈ℝ^(r×d)，B∈ℝ^(d×r)，r << d
- **参数量**：全量微调 d×d，LoRA仅 2×d×r（r=32时减少99%+）
- **缩放系数**：实际更新为 `α/r × B×A`，项目配置 [trainer.py:163-168](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L163-L168) 中 `lora_r=32, lora_alpha=64`，缩放比=2
- **为什么有效**：A mini-batch gradient descent on low-rank subspace，理论依据是权重更新的本征秩低

#### 1.2 target_modules选择（项目亮点）
- 项目覆盖7个模块：`q_proj, k_proj, v_proj, o_proj`（attention）+ `gate_proj, up_proj, down_proj`（FFN）
- 见 [trainer.py:176-179](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L176-L179)
- **面试点**：只训attention vs 同时训FFN的表达能力差异，参考LoRA原论文消融实验

#### 1.3 SFT的label构造（关键技巧）
- **核心**：prompt部分label设为-100（交叉熵忽略），只对assistant回复计算loss
- 项目实现 [trainer.py:392](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L392)：`labels = [-100] * prompt_len + full_ids[prompt_len:]`
- **面试点**：为什么不对user部分计算loss？（避免模型学习生成用户问题）

#### 1.4 量化与QLoRA
- 项目支持4种量化加载（[trainer.py:489-607](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L489-L607)）：
  - **AWQ 4bit**：activation-aware，group_size=128
  - **GPTQ 4bit**：基于二阶信息的逐层量化
  - **NF4 (BNB)**：QLoRA论文提出的NormalFloat4
  - **8bit (BNB)**：LLM.int8()
- **重要工程经验**：项目明确警告"AWQ/GPTQ模型主要用于推理，训练LoRA建议用FP16/BF16原始模型"（[trainer.py:516-519](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L516-L519)）

#### 1.5 训练优化技术
| 技术 | 项目配置 | 作用 | 代码位置 |
|------|---------|------|---------|
| 梯度累积 | steps=4 | 等效batch=8，突破显存限制 | trainer.py:187 |
| 梯度检查点 | True | 用计算换显存，省30-50% | trainer.py:214 |
| paged_adamw_32bit | True | 分页优化器，OOM时交换到CPU | trainer.py:194 |
| 余弦调度+预热 | warmup=0.05 | 预热期线性增长，后余弦衰减 | trainer.py:189-191 |
| 混合精度 | fp16=True | 半精度训练加速 | trainer.py:192 |
| 早停 | patience=3 | 验证loss不再下降则停止 | trainer.py:216-217 |

### 推荐资源
- **论文（必读）**：
  - LoRA: Low-Rank Adaptation of Large Language Models（2021）
  - QLoRA: Efficient Finetuning of Quantized LLMs（2023）
- **论文（选读）**：
  - AdapterFusion / Prefix-Tuning（对比理解PEFT家族）
  - AWQ: Activation-aware Weight Quantization
- **文档**：HuggingFace PEFT官方文档
- **源码**：阅读 [trainer.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py) 全文，重点 `LoRATrainingConfig`、`format_and_tokenize`、`_load_model_with_quantization`

### 本项目实践建议
1. **对比实验**：修改 [trainer.py:163-168](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L163-L168) 的 `lora_r`（8/16/32/64），训练同一数据集，对比eval_loss曲线
2. **GPU配置适配**：阅读 [task_manager.py:23-111](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/task_manager.py#L23-L111) 的RTX4060(8GB)与RTX3090(24GB)两套预设，理解显存-精度权衡
3. **数据预处理**：跟踪 [trainer.py:319-487](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L319-L487) 的 `format_and_tokenize`，理解ShareGPT→chat template→label mask的完整流程
4. **温度监控**：阅读 [trainer.py:73-147](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L73-L147) 的 `GpuTemperatureCallback`，这是笔记本训练的工程创新点

### 实践项目建议
- **初级**：用项目已有数据集训练一个角色LoRA，记录eval_loss曲线
- **中级**：对比 rank=8/16/32/64 的训练效果（loss/生成质量/训练时间）
- **高级**：实现"只训attention"vs"attention+FFN"的对比实验，复现LoRA论文消融结论

### 评估标准
- [ ] 能推导LoRA的参数量减少公式
- [ ] 能解释 α/r 缩放系数的作用
- [ ] 能口述SFT label构造为什么用-100
- [ ] 能解释梯度检查点节省显存的原理（以计算换显存）
- [ ] 能说出NF4/INT4/AWQ三种量化的区别
- [ ] 能独立调整训练超参数并解释影响

### 面试常见问题
1. **LoRA的秩r怎么选？太大太小有什么问题？**
2. **为什么不直接训练全部参数？LoRA的理论依据是什么？**
3. **target_modules选哪些？只训attention和加FFN有什么区别？**
4. **QLoRA的NF4量化为什么比普通INT4好？**
5. **梯度累积为什么能等效增大batch size？数学上等价吗？**
6. **训练时OOM怎么解决？（梯度检查点/量化/减小batch/减小seq_len）**

---

## 阶段2：意图分类（核心，2-3周）

### 学习目标
- 掌握文本表示方法（TF-IDF/词嵌入/句嵌入）
- 理解分类模型（逻辑回归/SVM/神经网络）
- 掌握ML+规则混合决策的工程设计

### 核心概念（面试考点）

#### 2.1 句嵌入vs词嵌入
- 项目使用 `paraphrase-multilingual-MiniLM-L12-v2`（384维，[intent_trainer.py:711](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L711)）
- **面试点**：为什么用SentenceTransformer而非Word2Vec？（上下文感知/多语言/语义相似度）
- **编码方式**（[intent_trainer.py:677](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L677)）：`embed_model.encode(texts, batch_size=64)`

#### 2.2 逻辑回归多分类
- 项目配置（[intent_trainer.py:686-689](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L686-L689)）：
  ```python
  LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced", solver="lbfgs")
  ```
- **面试点**：
  - `class_weight="balanced"`：按类别频率倒数加权，缓解样本不均衡
  - `C=1.0`：L2正则化强度的倒数，C越小正则越强
  - 多分类用softmax（one-vs-rest或multinomial）

#### 2.3 特征标准化
- 项目用 `StandardScaler`（[intent_trainer.py:682-683](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L682-L683)）
- **面试点**：逻辑回归为什么要标准化？（特征尺度不一致影响梯度收敛与正则化公平性）

#### 2.4 硬负例挖掘（项目亮点）
- 项目实现 [intent_trainer.py:456-527](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L456-L527)
- **核心思想**：构造"看起来像KB-A但实际属于KB-B"的跨域混淆问题
- **理论依据**：对比学习——通过难区分样本学习更精细的决策边界
- **面试点**：硬负例 vs 随机负例的区别，为什么硬负例提升更大

#### 2.5 ML+规则混合决策（面试核心）
- 项目融合策略见 [intent_detector.py:350-406](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L350-L406)

```
ML高置信度(≥0.65) → 信任ML，但预测"不需要"时检查规则兜底（疑问句）
ML低置信度(<0.65) → 规则引擎tiebreaker
  - ML与规则一致 → 信任
  - 冲突：ML说需要→优先ML（高召回）；ML说不需要→信任规则（安全网）
ML不可用 → 回退纯规则
```

- **关键阈值**：
  - `threshold=0.5`（[intent_detector.py:313](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L313)）：最低置信度
  - `0.65`（[intent_detector.py:377](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L377)）：高置信度分界

- **面试点**：为什么不全用ML？（可解释性/冷启动/兜底）；为什么不全用规则？（覆盖度/泛化性）

#### 2.6 规则引擎设计
- 6层判断（[intent_detector.py:120-169](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L120-L169)）：
  1. 长度检查（<3字不触发RAG）
  2. 特殊字符过滤（>50%不触发）
  3. 社交词+知识词组合判断
  4. 疑问句检测
  5. 长消息判断
- **面试点**：规则引擎的可解释性优势，以及与ML互补的工程价值

### 推荐资源
- **课程**：吴恩达《机器学习》逻辑回归/支持向量机部分（Coursera）
- **论文**：
  - Sentence-BERT（2019）：句嵌入经典
  - Contrastive Learning for NLP（硬负例理论）
- **文档**：scikit-learn LogisticRegression文档、SentenceTransformer文档

### 本项目实践建议
1. **阈值调优**：修改 [intent_detector.py:313,377](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L313) 的阈值，用交叉验证观察precision/recall权衡
2. **关键词扩展**：在 [intent_detector.py:39-97](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L39-L97) 添加/删除关键词，测试规则覆盖率
3. **硬负例对比**：注释掉 [intent_trainer.py:456-527](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L456-L527) 的硬负例生成，对比训练效果
4. **5折交叉验证**：阅读 [intent_trainer.py:691](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_trainer.py#L691)，理解模型评估方法

### 实践项目建议
- **初级**：用项目samples.json训练分类器，记录5折交叉验证准确率
- **中级**：对比"有硬负例"vs"无硬负例"的混淆矩阵差异
- **高级**：实现一个简单神经网络分类器（MLP），与LogisticRegression对比

### 评估标准
- [ ] 能解释逻辑回归的决策边界与softmax多分类
- [ ] 能说出class_weight="balanced"的作用原理
- [ ] 能解释为什么需要特征标准化
- [ ] 能口述ML+规则融合的完整决策树
- [ ] 能解释硬负例对决策边界的影响
- [ ] 理解5折交叉验证的流程与意义

### 面试常见问题
1. **为什么用逻辑回归而不是深度学习分类器？（可解释/小数据/快速/基线）**
2. **class_weight="balanced"具体怎么计算权重？**
3. **句嵌入和词嵌入有什么区别？为什么用SentenceTransformer？**
4. **ML和规则引擎怎么融合？为什么不全用ML？**
5. **硬负例是什么？为什么能提升分类效果？**
6. **交叉验证的作用？K折怎么选K？**

---

## 阶段3：RAG检索（核心，2-3周）

### 学习目标
- 掌握向量检索原理（Faiss索引类型）
- 理解两阶段检索（粗排+精排）架构
- 掌握RAG完整pipeline与prompt工程

### 核心概念（面试考点）

#### 3.1 两阶段检索架构（项目核心设计）
项目实现 [rag_helper.py:218-366](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/rag_helper.py#L218-L366)：

```
查询 → 查询扩展 → 粗排召回(向量+BM25混合) → 精排(Cross-Encoder) → 归一化 → 注入prompt
```

- **粗排**：Bi-Encoder，快但粗，recall_top_k=20（[rag_helper.py:265](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/rag_helper.py#L265)）
- **精排**：Cross-Encoder，慢但准，final_top_k=5（[rag_helper.py:169](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/rag_helper.py#L169)）
- **面试点**：为什么两阶段？（Bi-Encoder快但精度低，Cross-Encoder精度高但慢，组合平衡速度与精度）

#### 3.2 Faiss索引类型（必考）
项目根据数据量自动迁移（[vector_db.py:260-306](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L260-L306)）：

| 索引 | 适用规模 | 原理 | 项目参数 |
|------|---------|------|---------|
| IndexFlatIP | <1万 | 精确内积，无近似 | 内积=归一化后的余弦 |
| IndexIVFFlat | 1万-10万 | 倒排聚类，类内搜索 | nlist=√n, nprobe=10 |
| IndexHNSWFlat | >10万 | 分层小世界图 | M=32, efSearch=64 |

- **自动迁移阈值**（[vector_db.py:427-474](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L427-L474)）：1万→IVF，10万→HNSW
- **面试点**：
  - 为什么Flat用内积而非L2？（归一化后内积=余弦相似度）
  - IVF的nprobe如何权衡速度与精度？
  - HNSW的efSearch vs M的区别？

#### 3.3 BM25混合检索
- 项目实现 [vector_db.py:39-148,700-776](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L39-L148)
- **BM25参数**：k1=1.5（词频饱和度），b=0.75（文档长度归一化）
- **中文分词**：jieba
- **混合公式**（[vector_db.py:760-776](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L760-L776)）：
  ```
  fused = 0.7 × 向量分数 + 0.3 × BM25分数
  ```
- **面试点**：为什么混合？（向量捕捉语义，BM25捕捉关键词，互补）

#### 3.4 Cross-Encoder重排
- 模型：bge-reranker-base（[reranker.py:29](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/reranker.py#L29)）
- **与Bi-Encoder的区别**：
  - Bi-Encoder：query和doc分别编码，再算相似度，速度快
  - Cross-Encoder：query和doc拼接输入，输出相关性分数，精度高但慢
- **面试点**：为什么Cross-Encoder精度高？（query-doc交互发生在attention层）

#### 3.5 查询扩展
- 项目实现 [rag_helper.py:37-153](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/rag_helper.py#L37-L153)
- 三种策略：
  1. 同义词替换（"胡桃"→"往生堂堂主/七十七代堂主"）
  2. 领域关键词追加
  3. 区域限定查询
- **面试点**：查询扩展提升召回率但可能降低精度，如何平衡？

#### 3.6 文本分块策略
- 项目实现 [text_splitter.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/text_splitter.py)
- **三阶递进**：段落→句子→定长截断
- **参数**：chunk_size=600，overlap=100
- **配对符号感知**：避免在引号内断句
- **面试点**：chunk_size和overlap如何影响检索质量？（大chunk语义完整但稀释，小chunk精确但可能截断语义）

#### 3.7 RAG prompt注入工程
- 项目实现 [rag_helper.py:368-417](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/rag_helper.py#L368-L417)
- 格式：`【相关文档: {title}（相关度: {score:.2f}）】\n{content}`
- **最大上下文**：2000字符
- **面试点**：RAG注入的prompt工程——如何避免模型照搬原文（本项目改用"背景设定"框架，见bot.py）

### 推荐资源
- **论文（必读）**：
  - RAG: Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks（2020）
  - Dense Passage Retrieval (DPR)（2020）
- **论文（选读）**：
  - Cross-Encoder vs Bi-Encoder for Passage Retrieval
  - HNSW: Efficient and robust approximate nearest neighbor search
- **文档**：Faiss官方wiki、BGE模型文档
- **源码**：阅读 [rag_helper.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/rag_helper.py) 全文，理解两阶段检索完整流程

### 本项目实践建议
1. **索引对比**：修改 [vector_db.py:279-306](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L279-L306) 强制使用不同索引，对比检索速度与精度
2. **权重调优**：调整 [vector_db.py:760](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L760) 的keyword_weight（0.3），观察混合检索效果
3. **分块实验**：修改 [text_splitter.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/text_splitter.py) 的chunk_size（400/600/800），对比检索质量
4. **重排消融**：注释掉reranker步骤，对比"只粗排"vs"粗排+精排"的结果质量

### 实践项目建议
- **初级**：用项目已有知识库，对比向量检索vs BM25vs混合检索的Top-5结果
- **中级**：实现一个简化版RAG pipeline（嵌入→检索→注入），对比有无重排的效果
- **高级**：实现查询扩展的消融实验（同义词/领域词/区域限定分别贡献多少）

### 评估标准
- [ ] 能解释Bi-Encoder vs Cross-Encoder的区别与适用场景
- [ ] 能说出Faiss三种索引的原理与选择依据
- [ ] 能推导BM25公式中k1和b的作用
- [ ] 能解释两阶段检索为什么比单阶段更优
- [ ] 能说出chunk_size和overlap对检索质量的影响
- [ ] 理解RAG prompt注入的工程考量

### 面试常见问题
1. **为什么RAG比直接把知识塞进prompt好？（token限制/更新成本/精度）**
2. **向量检索和BM25各有什么优劣？为什么要混合？**
3. **Faiss的IVF和HNSW原理？什么场景选哪个？**
4. **Cross-Encoder为什么比Bi-Encoder精度高？为什么不全用Cross-Encoder？**
5. **chunk_size设多大合适？overlap的作用？**
6. **查询扩展会不会降低精度？如何平衡？**

---

## 阶段4：vLLM推理服务（2周）

### 学习目标
- 理解vLLM的核心优化（PagedAttention/Continuous Batching/Prefix Caching）
- 掌握多LoRA部署与负载均衡
- 理解量化推理的工程实践

### 核心概念（面试考点）

#### 4.1 PagedAttention（vLLM核心创新）
- **灵感**：操作系统的虚拟内存分页机制
- **原理**：KV Cache按块（block）存储，非连续物理内存，逻辑地址映射
- **优势**：减少KV Cache碎片，显存利用率从~50%提升到~90%+
- **面试点**：能类比OS分页机制解释PagedAttention

#### 4.2 Continuous Batching
- **vs静态批处理**：静态batch必须等最短序列生成完才结束；continuous batching动态加入/移除请求
- **项目配置**：`max_num_seqs=64`（[launch_vllm.py:83](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/scripts/launch_vllm.py#L83)）
- **面试点**：为什么continuous batching吞吐量高？（GPU利用率高，无气泡）

#### 4.3 Prefix Caching
- **原理**：缓存相同前缀的KV Cache（如system prompt），避免重复计算
- **项目启用**：`--enable-prefix-caching`（[start_vllm.sh:121](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/deploy/scripts/start_vllm.sh#L121)）
- **面试点**：RAG场景下system prompt长且重复，prefix caching显著降低TTFT

#### 4.4 多LoRA加载
- 项目配置（[start_vllm.sh:120](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/deploy/scripts/start_vllm.sh#L120)）：
  ```bash
  --enable-lora --max-loras 8 --max-lora-rank 64
  --lora-modules hutao=/path minamo=/path
  ```
- **切换机制**：客户端通过`model`字段指定LoRA ID（[vllm_client.py:394-402](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/inference/vllm_client.py#L394-L402)）
- **面试点**：vLLM如何高效服务多个LoRA？（共享基座模型，LoRA权重动态切换）

#### 4.5 负载均衡（项目工程亮点）
- 两种策略（[vllm_client.py:133-188](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/inference/vllm_client.py#L133-L188)）：
  - **加权轮询**：Nginx平滑算法，权重=基础权重×成功率/(1+响应时间)
  - **最少连接数**：选当前连接数最少的实例
- **面试点**：动态权重为什么考虑成功率+延迟？（兼顾可靠性与性能）

#### 4.6 熔断与故障转移
- 熔断器配置（[vllm_client.py:278-285](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/inference/vllm_client.py#L278-L285)）：连续20次失败→熔断，60秒后半开
- **指数退避重试**（[vllm_client.py:754-770](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/inference/vllm_client.py#L754-L770)）：`delay = min(1×2^n, 30) × random(0.5,1.5)`
- **面试点**：熔断器三状态（closed/open/half-open）与指数退避的抖动作用

#### 4.7 AWQ量化推理
- **训练vs推理的差异**：训练用FP16/BF16原模型，推理用AWQ量化模型
- **项目配置**：`--quantization awq`（[launch_vllm.py:89](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/scripts/launch_vllm.py#L89)）
- **面试点**：AWQ相比GPTQ的优势（activation-aware，校准更优）

### 推荐资源
- **论文（必读）**：Efficient Memory Management for LLMs with PagedAttention（vLLM, 2023）
- **文档**：vLLM官方文档（engines、serving、features）
- **源码**：阅读 [vllm_client.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/inference/vllm_client.py)，重点负载均衡与熔断器

### 本项目实践建议
1. **参数调优**：调整 [start_vllm.sh](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/deploy/scripts/start_vllm.sh) 的`gpu_memory_utilization`（0.85/0.9/0.95），观察显存与吞吐
2. **Prefix Caching对比**：启用/禁用，测量相同system prompt的TTFT差异
3. **多LoRA测试**：调用不同LoRA ID，验证切换机制
4. **熔断器实验**：手动停止vLLM，观察客户端熔断行为与降级消息

### 评估标准
- [ ] 能解释PagedAttention的分页机制与OS分页的类比
- [ ] 能说出Continuous Batching vs静态批处理的区别
- [ ] 能解释Prefix Caching为什么降低TTFT
- [ ] 能口述熔断器三状态转换
- [ ] 理解指数退避中抖动的作用

### 面试常见问题
1. **vLLM为什么比HuggingFace推理快？（PagedAttention/Continuous Batching）**
2. **PagedAttention的灵感来源？如何减少显存碎片？**
3. **多个LoRA如何同时服务？显存怎么算？**
4. **熔断器什么时候打开？半开状态有什么用？**
5. **指数退避为什么加随机抖动？（避免惊群效应）**
6. **AWQ推理为什么不能直接训练LoRA？**

---

## 阶段5：机器人集成（1-2周）

### 学习目标
- 理解对话系统架构
- 掌握NoneBot2框架与OneBot协议
- 理解动态配置与热更新设计

### 核心概念
#### 5.1 对话系统架构
- 用户消息 → 意图检测 → RAG检索（可选）→ LLM生成 → 返回
- 项目实现 [bot.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/bot/bot.py)

#### 5.2 动态配置（项目工程亮点）
- Config类用@property + 30秒缓存（bot.py）
- **面试点**：为什么不用环境变量？（修改需重启）；为什么加缓存？（避免每次请求查DB）

#### 5.3 RAG注入prompt工程
- 从"知识库/直接引用"改为"背景设定/自然融入"
- **面试点**：如何避免模型照搬原文？（prompt措辞+温度控制）

### 推荐资源
- NoneBot2官方文档
- OneBot V11协议规范

### 评估标准
- [ ] 能画出消息处理完整流程图
- [ ] 能解释动态配置@property的设计动机
- [ ] 理解反向WebSocket连接机制

---

## 阶段6：前后端开发（2-3周，后置）

### 学习目标
- 掌握FastAPI后端开发（路由/认证/中间件/数据库）
- 掌握Next.js前端开发（App Router/状态管理/代理）
- 理解全栈架构与部署

### 核心模块
| 后端 | 前端 |
|------|------|
| FastAPI路由 ([api/](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/api)) | Next.js App Router ([src/app/](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/src/app)) |
| JWT认证 ([auth.py](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/api/auth.py)) | AuthGuard组件 |
| SQLite + Redis缓存 | React Query数据获取 |
| 安全中间件 ([middleware/](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/middleware)) | API代理 ([proxy.ts](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/src/lib/proxy.ts)) |

### 推荐资源
- FastAPI官方教程
- Next.js官方教程（App Router）
- 本项目 [DEVELOPMENT.md](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/docs/DEVELOPMENT.md)

### 评估标准
- [ ] 能开发一个CRUD API
- [ ] 能实现JWT认证流程
- [ ] 能开发一个Next.js页面
- [ ] 理解前后端代理与CORS

---

## 面试准备总策略

### 1. 技术叙事主线（建议背诵）
> "我的项目是一个完整的AI工程链路：用LoRA训练角色适配器（阶段1），用意图分类决定是否检索（阶段2），用两阶段RAG获取知识（阶段3），用vLLM高效部署多LoRA推理（阶段4），最后集成到QQ机器人（阶段5）并提供Web管理界面（阶段6）。每个环节都有可解释的技术决策，比如LoRA的target_modules选择、RAG的两阶段架构、vLLM的负载均衡策略。"

### 2. 高频面试题速查（按阶段）
| 阶段 | 必问题 | 答题要点 |
|------|--------|---------|
| LoRA | LoRA原理/为什么有效 | 低秩分解 ΔW=BA，参数量2dr vs d² |
| LoRA | r怎么选 | 8-64，太小欠拟合太大过拟合，项目用32 |
| LoRA | label为什么-100 | 只对回复计算loss，不学生成问题 |
| 意图 | 为什么用逻辑回归 | 可解释/小数据/快速/基线 |
| 意图 | ML+规则怎么融合 | 高置信度信ML，低置信度信规则，安全网兜底 |
| RAG | 两阶段检索 | Bi-Encoder粗排快，Cross-Encoder精排准 |
| RAG | Faiss索引选择 | Flat<1万<IVF<10万<HNSW |
| RAG | 向量+BM25为什么混合 | 语义+关键词互补 |
| vLLM | PagedAttention | OS分页类比，KV Cache分块减少碎片 |
| vLLM | 多LoRA如何服务 | 共享基座，动态切换，max-loras限制 |
| vLLM | 熔断器三状态 | closed→open→half-open→closed |

### 3. 项目亮点提炼（面试加分项）
1. **GPU温度监控**（[trainer.py:73-147](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/trainer.py#L73-L147)）：笔记本训练的工程创新，82°C自动散热
2. **ML+规则混合决策**（[intent_detector.py:350-406](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/intent_detector.py#L350-L406)）：不是纯调包，有可解释的决策树
3. **动态配置热更新**（bot.py @property+30s缓存）：修改配置无需重启bot
4. **两套GPU配置预设**（[task_manager.py:23-111](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/training/task_manager.py#L23-L111)）：8GB/24GB显存自适应
5. **Faiss索引自动迁移**（[vector_db.py:427-474](file:///c:/Users/13474/ZCodeProject/qqchat-enhanced/backend/knowledge/vector_db.py#L427-L474)）：根据数据量自动选择最优索引

### 4. 深度问题准备（冲刺名校必备）
- **LoRA的秩为什么能小？** → Aghajanyan等人的研究显示预训练模型的内在维度低
- **Cross-Encoder为什么精度高？** → query-doc在self-attention层交互，捕捉细粒度相关性
- **PagedAttention如何处理碎片？** → block粒度分配，非连续物理地址，逻辑映射
- **为什么AWQ比GPTQ好？** → activation-aware，保护重要通道，校准更稳定

---

## 时间规划建议（12周计划）

| 周次 | 阶段 | 任务 | 产出 |
|------|------|------|------|
| 1 | 阶段0 | PyTorch+Transformer基础 | 能跑通transformers generate |
| 2-4 | 阶段1 | LoRA训练理论学习+实践 | 训练一个角色LoRA，记录对比实验 |
| 5-6 | 阶段2 | 意图分类学习+实践 | 调优分类器，记录5折交叉验证结果 |
| 7-8 | 阶段3 | RAG学习+实践 | 对比索引/权重/分块实验 |
| 9-10 | 阶段4 | vLLM学习+实践 | 部署多LoRA，测试负载均衡 |
| 11 | 阶段5 | 机器人集成 | 理解消息流程，能修改bot行为 |
| 12 | 阶段6+复习 | 前后端速览+面试复习 | 能完整口述项目架构与技术决策 |

**每日时间分配建议**：理论40% + 代码阅读30% + 实践实验30%

---

## 结语

本学习路径的核心优势在于：**所有理论都能在本项目中找到对应实现并动手验证**。面试时不仅能说出概念，更能说出"我在项目中是这样做的，因为……"——这是区分"调包侠"与"AI工程师"的关键。

每个阶段的"评估标准"是自测清单，全部打勾后该阶段即可进入下一阶段。"面试常见问题"是高频考点，建议用费曼技巧（讲给不懂的人听）验证掌握程度。
