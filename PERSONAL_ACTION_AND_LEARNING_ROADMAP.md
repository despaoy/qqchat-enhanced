# Personal Action and Learning Roadmap

> For QQChat Enhanced after revision `5daf7ed`  
> Goal: turn engineering work into credible LLM-system evidence for graduate-admission interviews.

## 0. How to Use This Roadmap

Each phase has four parts:

- **Learn**: concepts you should be able to explain.
- **Do**: work you personally need to complete.
- **Deliver**: files, figures, or results to keep.
- **Pass**: objective criteria before moving forward.

Do not run all experiments at once. Finish one small, reproducible comparison, write down the conclusion, then continue.

## 1. This Week: Establish a Trustworthy Baseline

### Learn

- Difference between training, validation, and held-out test sets.
- Why random seeds, data versions, hardware versions, and prompts are experimental controls.
- Difference between a mock result, a smoke test, a benchmark, and a research conclusion.
- Basic Git workflow: commit, push, tag, and reproducible revision recording.

### Do

1. Read `README.md`, `PROJECT_STATUS_AND_NEXT_STEPS.md`, `dataset-card.md`, and `human-scoring-rubric.md`.
2. Create one experiment notebook or Markdown log. Every run must record date, Git commit, command, GPU, model, dataset version, and result path.
3. Create a `data/` work log outside Git for raw/private material. Do not commit private chat records.
4. Check the server before every experiment:

```bash
nvidia-smi
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
redis-cli -h 127.0.0.1 ping
```

5. Rotate exposed passwords and tokens. Use a test account for QQ/WeChat integration.

### Deliver

- `experiment-log.md` with a first baseline entry.
- Dataset version identifier, for example `hutao-sft-v1`.
- A screenshot of server health and `nvidia-smi`.

### Pass

You can answer: “Which data was used, which code revision ran it, on what hardware, and where are the result files?”

## 2. Week 1: Build the Data and Evaluation Foundation

### Learn

- Dataset provenance, licensing, deduplication, contamination, and data leakage.
- SFT conversation format and why splitting by conversation is safer than random-row splitting.
- Gold Set design: coverage, difficulty, and why test prompts must not be training prompts.
- Human evaluation: blind comparison, rubric design, agreement, and annotation bias.

### Do

1. Complete `dataset-card.md` for every training corpus.
2. Review generated SFT samples. Keep only outputs that are factually acceptable, persona-consistent, and not repetitive.
3. Build a held-out Gold Set with at least 100 prompts:
   - 30 persona/style prompts
   - 20 factual prompts
   - 20 RAG-grounded prompts
   - 15 safety/prompt-injection prompts
   - 15 multi-turn prompts
4. Ensure no Gold Set prompt or near-duplicate appears in the SFT training file.
5. Use `human-scoring-rubric.md` to annotate 20 baseline responses. Record reason codes, not only a total score.

### Deliver

- Versioned Gold Set JSON.
- Completed dataset card.
- `gold-set-v1-review.md` describing categories and known weaknesses.
- At least 20 human-scored baseline examples.

### Pass

You can explain why your test set is held out and show at least one failed model case.

## 3. Week 2: Human Review of Preference Data

### Learn

- SFT versus preference optimization.
- DPO and ORPO intuition: chosen/rejected pairs, reference behavior, beta, and why this is not RLHF.
- Preference-data failure modes: easy negatives, same-model bias, position bias, and reward hacking.

### Do

1. Open the generated preference-pair file or management page.
2. For every pair, judge whether `chosen` is truly better than `rejected` according to the rubric.
3. Mark only valid pairs as `approved`; reject malformed, factually wrong, unsafe, or ambiguous pairs.
4. Add at least 10 manually written hard negatives:
   - persona collapse
   - overly generic answer
   - unsupported RAG claim
   - unsafe instruction following
   - excessive refusal
5. Keep at least 20 approved pairs for a pilot, but aim for 50 or more before drawing conclusions.

### Deliver

- Approved preference JSONL or database export.
- Annotation log with counts: approved, rejected, uncertain.
- A short bias note explaining how pairs were generated and reviewed.

### Pass

No automatically generated pair enters DPO/ORPO without a human review decision.

## 4. Weeks 3-4: LoRA, DoRA, and RSLoRA Experiment

### Learn

- Low-rank adaptation, rank, alpha, target modules, dropout, and adapter size.
- DoRA and RSLoRA design goals.
- Overfitting signals: train loss improving while held-out loss or human ratings worsen.
- TensorBoard curves: loss, learning rate, gradient norm, throughput, and GPU memory.

### Do

1. Train a LoRA baseline with fixed data, seed, rank, learning rate, epochs, and max sequence length.
2. Train DoRA with only `use_dora=true` changed.
3. Train RSLoRA with only `use_rslora=true` changed.
4. Keep vLLM stopped during training if GPU memory is tight, then restart it for inference evaluation.
5. Evaluate each adapter on the same Gold Set and collect:
   - validation loss and perplexity
   - adapter weight size
   - actual trainable parameters
   - generation diversity and repetition
   - 20 blind human comparisons
6. Do not use the old ablation report. Rerun after revision `5daf7ed`.

### Deliver

- One configuration JSON per run.
- TensorBoard logs and screenshots.
- `lora-ablation-v1.md` with a table and three representative error cases.

### Pass

You can defend one conclusion such as: “DoRA did not improve held-out persona score enough to justify its extra training time on this dataset.”

## 5. Week 5: RAG Evaluation and Grounding

### Learn

- Dense retrieval, BM25, hybrid retrieval, reranking, chunking, Recall@k, MRR, nDCG.
- Retrieval correctness versus answer faithfulness.
- Citation coverage and abstention when evidence is weak.

### Do

1. Create a held-out retrieval evaluation set separate from the seed-document construction process.
2. Import a versioned knowledge base with source metadata, section, import date, and hash.
3. Run vector-only, BM25-only, hybrid, and hybrid+rereanker configurations.
4. Record Recall@5, MRR, nDCG, average latency, and failed queries.
5. Add answer citations in the UI and manually check 20 cited answers.
6. Define a low-confidence threshold that causes abstention rather than unsupported generation.

### Deliver

- `retrieval-eval-v1.json`.
- `rag-ablation-v1.md` with metric table and failure analysis.
- Screenshots showing answer citations and a low-confidence refusal.

### Pass

You can distinguish “the document was retrieved” from “the final answer was supported by the document.”

## 6. Week 6: vLLM and AWQ Serving Study

### Learn

- AWQ, FP16/BF16, NF4, quantization error, and memory-quality trade-offs.
- vLLM PagedAttention, continuous batching, KV cache, context length, concurrency, and TTFT.
- Difference between model startup time, streaming TTFT, full request latency, and decode throughput.

### Do

1. Run one isolated vLLM process per model variant. Never label one hot AWQ process as FP16 or NF4.
2. Use identical prompts, context limit, sampling parameters, and concurrency for each variant.
3. Measure VRAM, startup time, streaming TTFT, end-to-end P50/P95, tokens/s, and failure rate.
4. Compare dynamic LoRA loading and merged adapter serving for one fixed persona.
5. Record model path, driver, CUDA, PyTorch, vLLM, and command line in every report.

### Deliver

- `quantization-benchmark-v1.md`.
- CSV/JSON raw measurements.
- One plot: VRAM versus P95 latency versus quality score.

### Pass

You can make a conditional statement, for example: “AWQ met the accepted quality threshold while leaving enough VRAM for target concurrency on a 24GB GPU.”

## 7. Week 7: DPO or ORPO Pilot

### Learn

- DPO objective, reference model behavior, beta, and why preference accuracy needs held-out log-probability scoring.
- QLoRA, NF4, gradient checkpointing, and memory constraints.
- Why a tiny preference dataset demonstrates a pipeline but does not prove broad alignment.

### Do

1. Train only on approved pairs.
2. Start with a short QLoRA DPO pilot on the 3090.
3. Keep an immutable copy of the SFT baseline adapter.
4. Evaluate baseline and DPO adapter on the same held-out Gold Set.
5. Do not report the historical `eval_accuracy=0.65`; it was a placeholder from older code.
6. Score a held-out preference set with explicit chosen/rejected log probabilities or blinded human comparisons.

### Deliver

- DPO config, adapter, training log, and memory record.
- A small baseline-versus-DPO table.
- A limitations paragraph describing data size and annotation bias.

### Pass

You can accurately say: “This is a small DPO pilot, not RLHF, and the conclusion is limited by the reviewed preference set size.”

## 8. Week 8: AstrBot and Production Demonstration

### Learn

- Webhook/gateway boundaries, idempotency, retries, rate limiting, trace IDs, and failure isolation.
- Authentication, token rotation, replay protection, and platform privacy constraints.

### Do

1. Configure QQ/NapCat to connect to AstrBot.
2. Install and configure `qqchat_gateway` with the backend URL and shared token.
3. Test private chat, group mention, prefix trigger, duplicate message ID, missing token, and timeout behavior.
4. Use a test account for personal WeChat. Treat it as optional due stability and compliance risk.
5. Capture the same trace ID through AstrBot logs, FastAPI logs, and message history.
6. Move from SQLite/manual Redis to PostgreSQL/persistent Redis/supervised services when the demo path is stable.

### Deliver

- One cross-platform trace screenshot.
- A failure-handling screenshot or log.
- A deployment diagram and service-health screenshot.

### Pass

A teacher can send one real message and you can explain how it reaches AstrBot, FastAPI, RAG/LoRA/vLLM, the database, and back to the platform.

## 9. Learning Resources by Topic

Use official papers and documentation first. Read enough to explain the idea, then verify it with this project.

| Topic | Read and understand | Apply in this project |
| --- | --- | --- |
| LoRA | LoRA paper; PEFT documentation | baseline, target modules, rank/alpha study |
| DoRA / RSLoRA | DoRA and RSLoRA papers | controlled ablation only |
| QLoRA | QLoRA paper; bitsandbytes docs | DPO memory-efficient pilot |
| DPO / ORPO | DPO paper; TRL docs | reviewed preference pairs and pilot |
| RAG | DPR, BM25, hybrid retrieval, RAG evaluation | vector/BM25/hybrid/reranker benchmark |
| vLLM | PagedAttention paper; vLLM docs | serving and quantization study |
| AWQ | AWQ paper | memory-latency-quality comparison |
| Evaluation | Distinct-N, MRR, nDCG, blind human evaluation | Gold Set and scoring rubric |
| Systems | queues, idempotency, circuit breakers, observability | AstrBot/FastAPI production path |

## 10. Final Portfolio Package

Before contacting teachers, prepare these artifacts:

1. One architecture diagram.
2. One deployment diagram and service-health screenshot.
3. One LoRA/DoRA/RSLoRA comparison table.
4. One RAG comparison table with citations and failure cases.
5. One AWQ serving benchmark plot.
6. One small DPO pilot comparison with limitations stated honestly.
7. One AstrBot cross-platform trace ID demonstration.
8. A five-minute demo and an eight-minute technical explanation.

Your core narrative should be: “I built an LLM system, measured its adaptation, retrieval, inference, and safety trade-offs, and can reproduce both successes and failures.”