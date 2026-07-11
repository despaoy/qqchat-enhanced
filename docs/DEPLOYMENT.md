# Production Deployment Checklist

Recommended topology:

- AstrBot runs as an independent process or container and connects QQ, Telegram, WeCom, official WeChat, or optional personal WeChat adapters.
- FastAPI runs as the core brain and exposes only internal AstrBot integration APIs plus authenticated admin APIs.
- PostgreSQL runs as the production database. SQLite is for local development and small deployments only.
- vLLM runs as a separate inference service.
- Nginx or Caddy terminates public HTTP(S) and forwards only the intended frontend/admin routes.
- Keep the admin console on a trusted network or behind login and network access control.

Required production environment variables:

- `ASTRBOT_INTEGRATION_TOKEN`: shared secret between AstrBot plugin and FastAPI.
- `QQCHAT_BACKEND_URL`: backend URL used by AstrBot, preferably internal network HTTP.
- `DATABASE_URL`: PostgreSQL URL. `postgresql://` is normalized to the asyncpg driver automatically.
- `VLLM_BASE_URL` or `VLLM_BASE_URLS`: model inference endpoint.
- `JWT_SECRET`: non-placeholder value with at least 32 characters.
- `ALLOWED_ORIGINS`: comma-separated trusted frontend/admin origins.
- `LOG_LEVEL`: one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `BACKEND_WORKERS=1`: required while idempotency, nonce replay protection, and session locks are process-local.

Startup behavior:

- In `ENVIRONMENT=production`, missing critical variables fail startup early.
- In development, the same validator logs warnings but allows mock/local workflows.
- `deploy/docker-compose.yml` marks secrets and origins as required so Compose fails before containers start with unsafe defaults.

Local verification:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local-verify.ps1
```

This runs Python compilation, core tests, an API smoke test, a mock AstrBot event, a history query, and a Git whitespace check.
