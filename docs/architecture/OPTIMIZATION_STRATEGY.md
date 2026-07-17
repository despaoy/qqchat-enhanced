# Optimization Strategy

## Scope and Priorities

This document is the execution baseline for performance, reliability, security, and deployment work. Priorities are P0 (data loss, security boundary, or service outage), P1 (incorrect user-visible behavior), P2 (capacity and operability), and P3 (quality improvements).

## Cross-Module Rules

- Keep application code, model weights, and persistent data in separate directories.
- Treat every external boundary as unreliable: IM platforms, vLLM, Redis, PostgreSQL, vector storage, and model files.
- Use one configuration source: environment variables validated at startup, never frontend-exposed secrets.
- Attach `traceId`, platform, conversation, sender, model, latency, and error type to each request log.
- Preserve idempotency with `platform + adapter + messageId`; use a stable fallback hash only when the platform has no message id.

## LoRA

- P0: Use one canonical `LORA_PATH` for scan, training output, backend loading, and `VLLM_LORA_ROOT`.
- P0: Serialize adapter load/unload operations and update database state only after vLLM confirms success.
- P1: Validate `adapter_config.json`, adapter weights, rank, tokenizer compatibility, and base-model family before activation.
- P1: Keep training artifacts and runtime adapters in persistent storage outside the Git checkout.
- P2: Track adapter load time, GPU memory delta, active adapter, and rollback result in model invocation logs.
- P2: Apply quotas for concurrent training and inference; training must not start while inference GPU headroom is below a configured floor.

## RAG and Intent Routing

- P0: Respect `VECTOR_DB_PATH` everywhere and rebuild or delete vector entries atomically with source documents.
- P0: Load embeddings only from `EMBEDDING_MODEL_PATH` in offline deployments; remote model download is opt-in.
- P1: Enable reranking only when an explicitly configured local model exists; use hybrid retrieval as the safe fallback.
- P1: Bound query expansion, cache by normalized query plus knowledge-base revision, and invalidate cache on document mutation.
- P2: Record retrieval candidate count, rerank latency, context length, cache hit, and retrieval failure type.
- P2: Train intent routing asynchronously with cancellation and versioned persistent artifacts.

## AstrBot and Platform Gateways

- P0: AstrBot remains a thin gateway. It normalizes events, enforces trigger policy, calls the backend once, and sends one reply at most.
- P0: Require integration token authentication in production and support timestamp, nonce, and signature replay protection.
- P1: Keep each platform independently switchable; group messages default to mention or prefix triggers.
- P1: Correlate AstrBot and backend logs through `traceId`; duplicate events must return the original result without a second reply.
- P2: Report gateway reachability separately from platform activity so idle is never confused with disconnected.

## High Concurrency

- P0: Apply global, platform/conversation, and sender token buckets before model work.
- P0: Queue generation with admin, private, channel, and group priorities; reject full queues with a controlled response.
- P1: Serialize each conversation while allowing unrelated conversations to proceed.
- P1: Align backend queue workers, vLLM client concurrency, and GPU capacity through environment variables.
- P2: Export queue length, active workers, rejection rate, latency percentiles, and cache hit rate.

## Reliability

- P0: Use timeout and circuit-breaker boundaries around vLLM, RAG, database writes, Redis, and AstrBot HTTP calls.
- P0: Do not repeat inference because a database write failed; record the failure and return the generated response once.
- P1: PostgreSQL is the production default. SQLite is development/small-scale only and must use WAL, busy timeout, and retry.
- P1: Use graceful degradation: group chats are silent on upstream failure; private chats get a short retry-safe message.
- P2: Back up persistent data before deployment and make migrations idempotent.

## Security

- P0: Keep JWT, integration tokens, cookies, platform credentials, and personal identifiers out of logs, frontend bundles, and Git.
- P0: Enforce authenticated administration, origin/CSRF validation, request size limits, schema validation, and command authorization.
- P1: Separate user text, retrieved documents, and system prompts. Block requests for secrets, config export, and privilege escalation.
- P1: Disable Claw code execution by default; if enabled, isolate it in a restricted container with a timeout and read-only filesystem.
- P2: Rotate integration tokens with overlap support and alert on repeated authentication failures.

## Deployment and Operations

- P0: A single-GPU deployment starts exactly one vLLM process; dual vLLM is opt-in and requires two GPUs.
- P0: Start Next.js standalone output with `node .next/standalone/server.js` after a successful build.
- P1: Run Redis, vLLM, backend, frontend, and AstrBot as separate supervised services with health checks and bounded restart policy.
- P1: Validate production environment variables before startup and run smoke tests after each deployment.
- P2: Use Nginx or Caddy for TLS, trusted-network management access, and request-size limits.

## Logging and Observability

- P0: Emit JSON logs with redaction for token, password, cookie, phone, openid, and unionid fields.
- P1: Keep application, audit, model, and gateway logs in persistent directories with rotation and retention.
- P1: Surface message/reply counts, P95/P99, model and RAG failure rate, queue state, AstrBot state, and platform state.
- P2: Alert on sustained model failure, database write failure, gateway degradation, queue saturation, slow P95, and auth attacks.

## Verification Matrix

| Area | Automated checks | Production acceptance |
| --- | --- | --- |
| LoRA | adapter scan and activation contract tests | load Minamo/Hutao, generate, rollback |
| RAG | vector path, deletion, cache invalidation tests | import, search, update, delete |
| AstrBot | schema, auth, idempotency tests | private/group gateway message |
| Concurrency | token bucket and session serialization tests | bounded concurrent requests |
| Security | token, signature, input, CSRF tests | unauthorized request rejection |
| Deployment | syntax, unit tests, frontend build | health, ready, vLLM models, UI smoke |

## Execution Order

1. Fix P0 configuration and deployment defaults.
2. Add or extend focused regression tests for each fixed boundary.
3. Validate local mock mode, then a real vLLM deployment.
4. Enable platforms one at a time and monitor correlated logs.
5. Promote only after metrics remain stable under a bounded concurrency test.
