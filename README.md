# QQChat Enhanced

QQChat Enhanced is a multi-platform LLM system for persona chat, knowledge-grounded answers, LoRA adaptation, and reproducible LLM experiments.

The system keeps AstrBot as the platform gateway and FastAPI as the core service. It supports QQ/NapCat and extensible IM platforms, vLLM AWQ inference, RAG, LoRA training and switching, experiment tracking, and a Next.js management console.

## Current Verified State

- Server revision: `5daf7ed`.
- Backend health and readiness checks pass; Redis and FAISS are available.
- vLLM serves `qwen2.5-7b-awq` on the RTX 3090 server.
- Backend regression: `86 passed, 1 skipped`.
- TypeScript and Next.js production build pass.
- AstrBot gateway, multi-platform message schema, idempotency, trace IDs, rate limiting, queues, and security boundaries are implemented.

The project is a validated single-server research prototype. PostgreSQL migration, persistent service supervision, and real IM account acceptance are still required before calling it a production deployment.

## Architecture

```text
QQ / WeChat / Telegram
          |
       AstrBot
          |
  qqchat_gateway plugin
          |
      FastAPI core
   /       |        \
vLLM     RAG      PostgreSQL/Redis
          |
     Next.js console
```

## Documentation

| Document | Purpose |
| --- | --- |
| [Project Status and Next Steps](PROJECT_STATUS_AND_NEXT_STEPS.md) | Current completion status, server operations, deployment and acceptance checklist |
| [LLM Research Enhancement Roadmap](LLM_RESEARCH_ENHANCEMENT_ROADMAP.md) | Research experiments, milestones, and graduate-admission presentation plan |
| [Optimization Strategy](OPTIMIZATION_STRATEGY.md) | Concurrency, reliability, security, observability, and deployment principles |
| [Dataset Card](dataset-card.md) | Training-data provenance, usage constraints, and versioning requirements |
| [Human Scoring Rubric](human-scoring-rubric.md) | Blind evaluation and preference-labeling rubric |
| [AstrBot Gateway Plugin](astrbot_plugins/qqchat_gateway/README.md) | AstrBot installation and platform gateway configuration |

## Local Verification

```powershell
pnpm ts-check
pnpm build
cd backend
py -3.12 -m pytest tests -q
py -3.12 -m scripts.local_smoke
```

## Server Verification

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
redis-cli -h 127.0.0.1 ping
curl -fsS http://127.0.0.1:8001/v1/models
```

## Research Integrity Rules

- Never treat mock outputs as real experiment results.
- Generated preference pairs begin in `pending` status and require human review before DPO/ORPO training.
- A real quantization comparison requires isolated vLLM processes for each model variant.
- Existing early DPO and LoRA reports are runtime records; rerun them with the current metric collection code before presenting results.
- Keep dataset versions, seeds, model versions, commands, hardware, and reports together for every experiment.

## Repository Layout

```text
backend/                 FastAPI, training, RAG, evaluation, database
src/                     Next.js management console
astrbot_plugins/         AstrBot gateway plugin
deploy/                  Compose, Nginx, server scripts, experiment runner
loras/                   Local development adapters (do not commit large artifacts)
genshin_knowledge_base/  Knowledge-base source material
```

For day-to-day work, start with [Project Status and Next Steps](PROJECT_STATUS_AND_NEXT_STEPS.md). It is the authoritative operational checklist.