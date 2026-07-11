"""Deployment environment validation helpers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Mapping

logger = logging.getLogger(__name__)

_REQUIRED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_SECRET_PLACEHOLDERS = {
    "",
    "changeme",
    "change-me",
    "change-me-to-a-random-secret",
    "your-48-char-secure-secret-here-change-in-production",
    "PLEASE_SET_A_SECURE_SECRET_HERE",
}


@dataclass
class DeploymentValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise RuntimeError("Invalid production deployment configuration: " + "; ".join(self.errors))


def _value(env: Mapping[str, str], key: str) -> str:
    return str(env.get(key, "")).strip()


def _has_any(env: Mapping[str, str], *keys: str) -> bool:
    return any(bool(_value(env, key)) for key in keys)


def _is_placeholder(value: str) -> bool:
    return value.strip() in _SECRET_PLACEHOLDERS


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def validate_deployment_environment(env: Mapping[str, str] | None = None) -> DeploymentValidationResult:
    """Validate production-critical environment variables.

    Development runs are intentionally lenient. Production must declare the
    external gateway, database, model, authentication, CORS, and logging
    settings explicitly so accidental defaults do not become the deployment.
    """
    env = env or os.environ
    errors: list[str] = []
    warnings: list[str] = []
    production = _value(env, "ENVIRONMENT").lower() == "production"

    token_values = [_value(env, "ASTRBOT_INTEGRATION_TOKEN"), _value(env, "ASTRBOT_INTEGRATION_TOKENS")]
    if not any(token_values):
        (errors if production else warnings).append("ASTRBOT_INTEGRATION_TOKEN or ASTRBOT_INTEGRATION_TOKENS is required")
    elif any(_is_placeholder(token) for token in token_values if token):
        (errors if production else warnings).append("ASTRBOT integration token still uses a placeholder value")
    elif production and any(len(token) < 32 for token in token_values if token):
        errors.append("ASTRBOT integration tokens must contain at least 32 characters")

    if not _has_any(env, "QQCHAT_BACKEND_URL", "BACKEND_URL"):
        (errors if production else warnings).append("QQCHAT_BACKEND_URL is required for AstrBot callback configuration")

    database_url = _value(env, "DATABASE_URL")
    has_database_url = bool(database_url)
    if production and not has_database_url:
        errors.append("DATABASE_URL is required for the PostgreSQL application database")
    elif production and not database_url.startswith(("postgresql://", "postgresql+asyncpg://", "postgres://")):
        errors.append("DATABASE_URL must use a PostgreSQL URL")
    elif not production and not has_database_url:
        warnings.append("SQLite fallback is active; use PostgreSQL for production")

    if production and _value(env, "USE_POSTGRESQL").lower() in {"0", "false", "no", "off"}:
        errors.append("USE_POSTGRESQL=false is not allowed in production")

    if not _has_any(env, "VLLM_BASE_URL", "VLLM_BASE_URLS"):
        (errors if production else warnings).append("VLLM_BASE_URL or VLLM_BASE_URLS is required for model inference")

    jwt_secret = _value(env, "JWT_SECRET")
    if production and (len(jwt_secret) < 32 or _is_placeholder(jwt_secret)):
        errors.append("JWT_SECRET must be explicitly set to a non-placeholder value with at least 32 characters")
    elif not jwt_secret:
        warnings.append("JWT_SECRET is not set; development will auto-generate one")

    origins = _value(env, "ALLOWED_ORIGINS") or _value(env, "CORS_ORIGINS")
    if production and (not origins or origins == "*" or "localhost" in origins or "127.0.0.1" in origins):
        errors.append("ALLOWED_ORIGINS/CORS_ORIGINS must be explicit production origins")
    elif not origins:
        warnings.append("ALLOWED_ORIGINS/CORS_ORIGINS is not set")

    if production and _value(env, "SECURITY_MIDDLEWARE_ENABLED").lower() in {"0", "false", "no", "off"}:
        errors.append("SECURITY_MIDDLEWARE_ENABLED=false is not allowed in production")

    try:
        worker_count = int(_value(env, "BACKEND_WORKERS") or "1")
    except ValueError:
        worker_count = 0
    if worker_count != 1:
        errors.append("BACKEND_WORKERS must be 1 while idempotency, nonce, and session locks are process-local")

    if production and _is_truthy(_value(env, "ALLOW_PUBLIC_REGISTRATION")):
        warnings.append("Public registration is enabled; disable it immediately after creating the administrator")

    if production and _is_truthy(_value(env, "CLAW_CODE_EXECUTION_ENABLED")):
        warnings.append("Claw code execution is enabled; isolate the backend container and use a read-only filesystem")

    log_level = (_value(env, "LOG_LEVEL") or "INFO").upper()
    lora_path = _value(env, "LORA_PATH")
    vllm_lora_root = _value(env, "VLLM_LORA_ROOT")
    if lora_path and vllm_lora_root and lora_path != vllm_lora_root:
        (errors if production else warnings).append("LORA_PATH and VLLM_LORA_ROOT must match for runtime adapter switching")

    if production and _is_truthy(_value(env, "RERANKER_ENABLED")) and not _value(env, "RERANKER_MODEL_PATH"):
        errors.append("RERANKER_MODEL_PATH is required when RERANKER_ENABLED=true")

    if log_level not in _REQUIRED_LOG_LEVELS:
        errors.append("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")

    return DeploymentValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_or_raise_for_startup(env: Mapping[str, str] | None = None) -> DeploymentValidationResult:
    result = validate_deployment_environment(env)
    if result.errors:
        result.raise_if_invalid()
    for warning in result.warnings:
        logger.warning("Deployment configuration warning: %s", warning)
    return result
