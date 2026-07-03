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

    if not _has_any(env, "QQCHAT_BACKEND_URL", "BACKEND_URL"):
        (errors if production else warnings).append("QQCHAT_BACKEND_URL is required for AstrBot callback configuration")

    has_database_url = bool(_value(env, "DATABASE_URL"))
    has_pg_parts = _is_truthy(_value(env, "USE_POSTGRESQL")) and all(
        _value(env, key) for key in ("PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DATABASE")
    )
    if production and not (has_database_url or has_pg_parts):
        errors.append("DATABASE_URL or complete PostgreSQL PG_* settings are required")
    elif not production and not (has_database_url or has_pg_parts):
        warnings.append("SQLite fallback is active; use PostgreSQL for production")

    if production and _value(env, "PG_PASSWORD") in {"changeme", "password", "qqassistant"}:
        errors.append("PG_PASSWORD must be changed from the default")

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

    log_level = (_value(env, "LOG_LEVEL") or "INFO").upper()
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
