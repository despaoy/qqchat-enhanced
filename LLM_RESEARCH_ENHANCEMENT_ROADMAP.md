# LLM Research Enhancement Roadmap

> Goal: turn QQChat Enhanced into an evidence-driven LLM systems project that demonstrates model adaptation, efficient inference, retrieval, alignment, evaluation, and real-world deployment.

## 1. Positioning for Graduate Admission

The strongest story is not ?I called an LLM API?. It is: ?I built and measured a controllable, efficient, retrieval-grounded, multi-platform LLM system; I can explain the design trade-offs and reproduce the results.?

Use the project to demonstrate four abilities:

1. Model adaptation: LoRA variants, data curation, alignment, and post-training evaluation.
2. Efficient inference: AWQ, vLLM scheduling, KV cache behavior, adapter lifecycle, and throughput/latency trade-offs.
3. Grounded generation: hybrid RAG, reranking, citation, confidence, and failure analysis.
4. LLM systems engineering: observability, safety boundaries, platform gateways, reproducible deployment, and ablation experiments.

## 2. What Already Exists

- LoRA training and runtime switching.
- Qwen AWQ inference through vLLM.
- Faiss plus BM25 hybrid retrieval and optional reranking.
- Intent routing, knowledge-base management, and multi-platform AstrBot gateway.
- Queueing, rate limiting, idempotency, circuit breakers, structured events, security middleware, and a web management console.

This is an unusually good base. The next work should prioritize experiments with measurable claims over adding unrelated features.

## 3. Highest-Value Research Additions

### A. Training Efficiency and LoRA Variants

Implement the recommendations from `optimization-guide.md` as controlled switches in the training configuration:

- NEFTune: add embedding noise only during training, expose `neftune_noise_alpha`, and compare loss, human preference, and robustness against the baseline.
- Sequence packing: pack short conversation samples, report effective tokens per second, GPU utilization, and padding ratio.
- DoRA and RSLoRA: expose mutually exclusive switches and compare standard LoRA, DoRA, and RSLoRA at identical rank, data, seed, epoch, and learning rate.
- QA-LoRA: treat AWQ training as an experiment, not a default. Compare FP16/BF16 base-model LoRA, QLoRA, and QA-LoRA with a clear warning about supported kernels and reproducibility.

Why it matters in an interview: you can explain parameter-efficient fine-tuning, rank scaling, the quality-efficiency trade-off, and why experiment control matters.

Deliverables:

- A versioned training configuration JSON for every run.
- A reproducible dataset split and fixed random seed.
- TensorBoard curves for train/eval loss, learning rate, gradient norm, throughput, and GPU memory.
- A one-page ablation table that reports quality, speed, VRAM, trainable parameters, and adapter size.

### B. Data-Centric Fine-Tuning

The most persuasive upgrade is a data pipeline, because LLM quality is often data-limited rather than architecture-limited.

- Add dataset cards: source, license, language, size, persona/domain, known risks, and intended use.
- Add deduplication, length filtering, malformed conversation detection, unsafe-content flags, and train/validation/test split by conversation rather than random row.
- Use LLM-assisted synthetic data generation only with a review queue. Store generation prompt, source model, temperature, and reviewer decision.
- Add hard negatives and counterfactual examples for persona consistency, refusal behavior, and RAG-vs-chat intent routing.
- Build a small gold evaluation set of 100 to 300 prompts. This is more valuable than a very large unmeasured corpus.

A strong answer: ?I improved data quality with provenance, deduplication, adversarial examples, and held-out evaluation rather than only increasing epochs.?

### C. Preference Alignment

After SFT works, add a small preference-learning experiment:

- Collect pairwise preferences from generated responses: helpfulness, persona consistency, factual grounding, style, and safety.
- Start with DPO or ORPO on a small curated preference set; do not claim RLHF unless you actually train a reward model and run policy optimization.
- Compare SFT-only and SFT-plus-preference alignment using blind human judgments and the same gold prompts.
- Store preference examples as immutable records with annotator rubric and disagreement metadata.

This demonstrates that you understand the post-training stack: pretraining -> SFT -> preference optimization -> evaluation.

### D. Evaluation Framework

Your guide correctly proposes perplexity, Distinct-N, and character consistency. Extend it into a layered evaluation suite:

| Layer | Metrics | Why it is useful |
| --- | --- | --- |
| Training | eval loss, perplexity, throughput, VRAM | Detect optimization and overfitting |
| Generation | length, Distinct-1/2, repetition rate | Measure fluency and diversity |
| Persona | rubric score, style consistency, contradiction rate | Measure role fidelity |
| Safety | prompt-injection success, secret-extraction refusal, harmful request refusal | Measure boundary robustness |
| RAG | context precision, context recall, answer faithfulness, citation correctness | Measure grounded generation |
| Serving | TTFT, tokens/s, P50/P95/P99, queue rejection rate | Measure user experience |

Use LLM-as-a-judge only with a fixed rubric, a held-out judge model or blinded manual sample review, and a statement of its limitations. Always keep a human-checked subset.

### E. RAG 2.0: Grounded and Verifiable Generation

Move from ?retrieve documents? to ?show why the answer is trustworthy?.

- Add chunk metadata: source document, section, version, import time, content hash, and knowledge-base revision.
- Return citations with every RAG answer. The UI should show source title and a short evidence excerpt.
- Add answer confidence derived from retrieval score distribution, citation coverage, and refusal threshold. Low confidence should lead to ?I cannot verify this from the current knowledge base.?
- Add corrective RAG: when retrieval confidence is low, reformulate one query, retrieve again, then either answer with citations or abstain. Bound retries to one or two.
- Add a retrieval evaluation dataset with questions, expected document ids, and gold answers. Measure recall@k, MRR, nDCG, faithfulness, and answer correctness.
- Compare vector-only, BM25-only, hybrid, and hybrid-plus-reranker. Report latency and accuracy together.

Interview value: you can explain retrieval failure, hallucination mitigation, reranking, chunking, evidence attribution, and abstention.

### F. Efficient Inference and AWQ Experiments

Do not merely state that AWQ is used. Demonstrate the quality-latency-memory frontier.

- Build the quantization benchmark suggested in the guide: FP16/BF16, AWQ, NF4/QLoRA-compatible loading where valid, and 8-bit baselines.
- Measure model load time, VRAM, TTFT, decode tokens/s, P50/P95 latency, and a fixed-prompt quality score.
- Compare dynamic LoRA loading with merged adapters. Explain that merge is faster for a fixed persona but removes hot switching.
- Explain vLLM concepts with evidence: PagedAttention, continuous batching, prefix caching, KV-cache memory, and why one 3090 should use bounded concurrency.
- Keep model, tokenizer, vLLM, CUDA, driver, prompt set, and command line in each experiment report.

Avoid claiming a universal AWQ win. The conclusion should be conditional: ?AWQ met the quality threshold while reducing memory enough to support the target concurrency on 24GB VRAM.?

### G. Multi-LoRA Routing

This is a distinctive extension because the project already has multiple personas and an intent classifier.

- Train or curate domain/persona adapters with clearly separated datasets.
- Use a lightweight router to select base chat, RAG-only, or one adapter; log routing confidence and fallback decisions.
- Compare hard routing, top-2 candidate routing with clarification, and a manually selected adapter baseline.
- Add adapter compatibility checks: base-model id, tokenizer revision, target modules, rank, and PEFT version.
- Demonstrate a safe fallback when an adapter fails to load instead of silently using the wrong persona.

### H. AstrBot and Agentic Workflows

Keep AstrBot as the platform gateway. Add LLM intelligence behind a narrow, auditable tool boundary:

- Define typed tools for knowledge search, session preference lookup, and approved information retrieval.
- Add tool-call tracing: tool name, sanitized arguments, result summary, latency, failure type, and traceId.
- Add a planner-vs-direct-answer experiment: only allow tool use when intent confidence or retrieval confidence requires it.
- Use MCP only for a small allow-listed demonstration tool set. Never expose shell or unrestricted filesystem access.
- Demonstrate one cross-platform conversation with the same traceId through QQ, personal WeChat, or Telegram.

### I. Online Feedback Loop

- Add thumbs-up/down plus a short reason taxonomy: incorrect, ungrounded, style mismatch, too slow, unsafe, or irrelevant.
- Store feedback linked to traceId, model/adaptor, knowledge-base revision, and prompt version.
- Periodically sample negative feedback into a review queue for preference data and retrieval evaluation updates.
- Never automatically retrain on raw production messages without consent, privacy filtering, and human review.

## 4. Recommended Thesis-Style Experiment Package

A compact but credible package contains four experiments:

1. LoRA ablation: LoRA vs DoRA vs RSLoRA, optionally NEFTune and packing.
2. Efficient inference: FP16 vs AWQ plus dynamic-vs-merged adapter serving.
3. RAG ablation: vector vs BM25 vs hybrid vs hybrid-plus-reranker, with citation and abstention evaluation.
4. Alignment: SFT-only vs preference-optimized model on persona, helpfulness, and safety rubrics.

For each experiment include hypothesis, controlled variables, hardware/software version, dataset split, metrics, results table, error cases, and conclusion. This turns engineering work into research evidence.

## 5. A 10-Week Implementation Plan

| Weeks | Focus | Concrete output |
| --- | --- | --- |
| 1 | Data card and gold set | Dataset provenance, 100+ held-out prompts, rubric |
| 2 | Training telemetry | TensorBoard, reproducible configs, seed control |
| 3 | LoRA variants | LoRA/DoRA/RSLoRA ablation table |
| 4 | NEFTune and packing | Throughput-quality comparison |
| 5 | Evaluation suite | PPL, diversity, persona, safety scripts |
| 6 | RAG evaluation | Retrieval gold set, citations, recall/MRR metrics |
| 7 | Corrective RAG | Confidence and abstention behavior |
| 8 | AWQ serving benchmark | TTFT, throughput, VRAM report |
| 9 | Preference alignment | Small DPO/ORPO pilot with human review |
| 10 | Demo and report | Dashboard, experiment report, 8-minute presentation |

## 6. What to Demonstrate Live

1. Send the same domain question with RAG off and on; show evidence citations and confidence.
2. Switch adapters; show runtime load trace, model metadata, and persona evaluation result.
3. Show the AWQ benchmark dashboard: memory, TTFT, and throughput relative to FP16.
4. Send repeated and concurrent platform messages; show idempotency, queue priority, and trace correlation.
5. Show an unsafe or prompt-injection request being blocked, with sanitized structured audit logging.

## 7. Suggested Oral Narrative

?I began with a deployable multi-platform assistant. Then I treated it as an LLM systems research platform: I controlled data and training variants, measured the quality-efficiency trade-off of LoRA and AWQ, made RAG evidence-grounded and measurable, and built the serving layer with bounded concurrency, traceability, and safety. Each conclusion is supported by a reproducible experiment rather than a feature claim.?

## 8. Guardrails

- Do not implement every fashionable technique. Four measured experiments are stronger than ten unchecked features.
- Do not train on personal platform messages without explicit consent and privacy review.
- Do not compare methods with different data, seeds, prompt templates, or hardware and call it an ablation.
- Do not use a single LLM judge as the only evidence of quality.
- Keep production reliability features separate from experimental code paths through explicit flags and versioned configurations.

## 9. Mapping from the Provided Optimization Guide

| Provided recommendation | Best use in this roadmap |
| --- | --- |
| NEFTune plus packing | Training-efficiency ablation |
| DoRA and RSLoRA | Parameter-efficient adaptation study |
| TensorBoard | Reproducible training telemetry |
| Post-training evaluator | Layered evaluation suite |
| Quantization comparison | AWQ inference evidence |
| QA-LoRA | Optional advanced quantized-training experiment |
| Adapter merge benchmark | Runtime switching vs fixed-persona serving trade-off |

Start with TensorBoard, data cards, gold evaluation set, DoRA/RSLoRA switches, and the AWQ benchmark. These create the clearest evidence with the least architectural risk.
