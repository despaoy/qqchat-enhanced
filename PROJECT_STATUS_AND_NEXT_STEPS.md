# Project Status and Next Steps

> Authoritative operational checklist for QQChat Enhanced.
> Last verified: 2026-07-13, revision `5daf7ed`.

## 1. Completed and Verified

### Core system

- AstrBot is the thin multi-platform gateway; FastAPI remains responsible for LLM generation, RAG, LoRA, history, configuration, and metrics.
- Multi-platform messages carry platform, adapter, conversation, sender, source message ID, and trace ID.
- Request rate limits, queueing, idempotency, circuit breakers, cache boundaries, and structured logging are implemented.
- Management pages exist for history, LoRA, training, knowledge bases, experiments, preferences, monitoring, settings, and integrations.

### LLM capabilities

- vLLM serves Qwen2.5-7B-Instruct-AWQ on an RTX 3090.
- LoRA training, runtime switching, multi-LoRA routing, hybrid RAG, BM25, FAISS, reranking hooks, Gold Set evaluation, preference-pair management, and experiment reports are implemented.
- Data generators now record generation provenance; non-mock SFT generation fails explicitly if vLLM is unavailable.
- Generated preference pairs are `pending`; only human-approved pairs are accepted by DPO/ORPO training.

### Validation

```text
Backend regression: 86 passed, 1 skipped
TypeScript: passed
Next.js production build: passed
Server health: healthy
Server readiness: database=true, faiss=true
Redis: PONG
Experiment Phase 0 mock suite: 4/4 passed
```

## 2. Current Limits

Do not make the following claims yet:

- The old DPO report's `eval_accuracy=0.65` is a historical placeholder, not a real preference win rate.
- The first LoRA baseline/DoRA report used old adapter-size and trainable-parameter accounting. Rerun it before presentation.
- The current AWQ result is a warm-service single-model benchmark, not a FP16/AWQ/NF4/INT8 comparison and not a true startup-load/streaming-TTFT measurement.
- The current RAG set is a useful regression benchmark but needs a separately authored held-out set before claiming generalization.
- SQLite plus manually started Redis is not a production deployment.

## 3. Immediate Actions

### A. Security and server control

1. Rotate every password, SSH credential, token, and platform secret that has appeared in chats, logs, or screenshots.
2. Use SSH keys and restrict firewall exposure to SSH and Nginx 80/443.
3. Keep vLLM, Redis, PostgreSQL, and FastAPI on loopback or an internal Docker network.
4. Store `.env` with mode `600`; never commit it.

### B. Production foundation

1. Use `deploy/docker-compose.yml` to run PostgreSQL, persistent Redis, FastAPI, frontend, vLLM, and Nginx as supervised services.
2. Set `ENVIRONMENT=production`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ASTRBOT_INTEGRATION_TOKEN`, and `ALLOWED_ORIGINS`.
3. Migrate SQLite data through a backup-and-verify process; do not overwrite the original database.
4. Add scheduled PostgreSQL backups and test a restore.

### C. Real platform acceptance

1. Configure QQ/NapCat to connect to AstrBot, not directly to the legacy NoneBot path.
2. In AstrBot, configure `qqchat_gateway` with the same integration token as FastAPI.
3. Test QQ private chat, group mention/prefix trigger, duplicate message ID, oversized text, missing token, and backend timeout.
4. Use a test account for personal WeChat. Verify private and group behavior before enabling it for any real contacts.
5. Save one trace ID and the corresponding AstrBot, FastAPI, and database records for every platform acceptance test.

## 4. Experiment Execution Order

### Stage 1: Data and evaluation

- Finalize `dataset-card.md`.
- Build a versioned Gold Set with at least 100 held-out prompts.
- Use `human-scoring-rubric.md` for blinded human review.
- Keep source, license, cleaning rules, seed, split, and prompt version beside every dataset.

### Stage 2: LoRA ablation

1. Regenerate or verify SFT data with `generation_mode=vllm`.
2. Train LoRA baseline and DoRA using the same data, seed, rank, learning rate, and epoch count.
3. Then add RSLoRA, NEFTune, and packing one at a time.
4. Preserve TensorBoard curves, final adapter weights, config JSON, evaluation results, and error cases.
5. Compare only reruns produced by the current metric code.

### Stage 3: RAG evaluation

- Compare vector-only, BM25-only, hybrid, and hybrid plus reranker.
- Report Recall@5, MRR, nDCG, latency, citation correctness, and abstention behavior.
- Build a held-out question set distinct from seed-document construction.

### Stage 4: Quantization and serving

- Start one isolated vLLM process per FP16/BF16, AWQ, NF4, or INT8 variant.
- Record GPU, driver, CUDA, PyTorch, vLLM, model revision, command line, context length, concurrency, VRAM, streaming TTFT, end-to-end latency, and tokens per second.
- Do not label a warm request latency as startup loading or TTFT.

### Stage 5: Preference alignment

- Review generated pairs in the management console and promote only acceptable records to `approved`.
- Train DPO or ORPO on approved pairs only.
- Add a held-out preference set and compute real chosen-versus-rejected log-probability win rate.
- Compare SFT-only and preference-aligned models using the same Gold Set and blinded reviewers.

## 5. Deployment Acceptance Checklist

| Area | Required evidence |
| --- | --- |
| Authentication | login, logout, protected APIs, CSRF/same-origin behavior |
| Model | real response, history record, trace ID |
| LoRA | load, switch, failure fallback, base-model recovery |
| RAG | document import, retrieval, citation display, low-confidence abstention |
| AstrBot | real QQ or WeChat private chat, group trigger, deduplication, graceful failure |
| Reliability | queue overload does not return uncontrolled 500 errors |
| Observability | trace ID links gateway, backend, and stored record |
| Recovery | PostgreSQL restore and service restart are tested |

## 6. Safe Cleanup Rules

Safe to remove after verification:

- `__pycache__`, temporary test directories, mock reports, failed attempt logs, and training checkpoints when a final adapter exists.

Keep:

- final adapters, TensorBoard logs, approved datasets, database backups, knowledge bases, model files, real experiment reports, and deployment configuration.

## 7. Documentation Map

- `README.md`: project entry point and document index.
- This document: current state and execution checklist.
- `LLM_RESEARCH_ENHANCEMENT_ROADMAP.md`: research design and 10-week plan.
- `OPTIMIZATION_STRATEGY.md`: engineering principles.
- `dataset-card.md`: dataset governance.
- `human-scoring-rubric.md`: human evaluation method.
- `astrbot_plugins/qqchat_gateway/README.md`: gateway-specific configuration.