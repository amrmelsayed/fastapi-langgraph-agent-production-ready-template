"""Sentry integration for error tracking and performance monitoring.

This module configures Sentry SDK with FastAPI integration, custom error filtering,
and integration with existing structlog logging.
"""

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings
from app.core.logging import logger


def before_send(event, hint):
    """Filter events before sending to Sentry.

    Args:
        event: The Sentry event dictionary
        hint: Additional context about the event

    Returns:
        The modified event or None to drop it
    """
    # Drop HTTPExceptions with status < 500 (client errors)
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        if hasattr(exc_value, "status_code"):
            if exc_value.status_code < 500:
                # Don't send 4xx errors to Sentry
                return None

    # Drop rate limit errors (handled by slowapi)
    if "exception" in event:
        for exception in event.get("exception", {}).get("values", []):
            if "RateLimitExceeded" in exception.get("type", ""):
                return None

    return event


def before_send_transaction(event, hint):
    """Filter transactions before sending to Sentry.

    Args:
        event: The transaction event
        hint: Additional context

    Returns:
        The modified event or None to drop it
    """
    # Drop health check transactions to reduce noise
    transaction_name = event.get("transaction", "")
    if transaction_name in ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]:
        return None

    return event


def traces_sampler(sampling_context):
    """Dynamic sampling for traces based on transaction type.

    Args:
        sampling_context: Context about the transaction

    Returns:
        Float between 0.0 and 1.0 representing sample rate
    """
    # Get the ASGI scope
    asgi_scope = sampling_context.get("asgi_scope", {})
    path = asgi_scope.get("path", "")

    # Always sample errors
    if sampling_context.get("parent_sampled") is True:
        return 1.0

    # Lower sampling for high-volume endpoints
    if path in ["/health", "/metrics"]:
        return 0.01  # 1% sampling

    # Higher sampling for critical endpoints
    if path.startswith("/api/v1/chat"):
        return min(settings.SENTRY_TRACES_SAMPLE_RATE * 1.5, 1.0)  # 150% of default, max 1.0

    # Default sampling rate
    return settings.SENTRY_TRACES_SAMPLE_RATE


def init_sentry():
    """Initialize Sentry SDK with FastAPI integration."""
    if not settings.SENTRY_ENABLED:
        logger.info("sentry_disabled", environment=settings.ENVIRONMENT.value)
        return

    if not settings.SENTRY_DSN:
        logger.warning(
            "sentry_dsn_not_configured",
            environment=settings.ENVIRONMENT.value,
            message="SENTRY_DSN is empty. Sentry will not be initialized.",
        )
        return

    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                AsyncioIntegration(),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=None,  # Don't capture logs automatically (we have structlog)
                    event_level=None,  # Don't create events from logs
                ),
            ],
            # Performance monitoring
            traces_sampler=traces_sampler,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            # Event filtering
            before_send=before_send,
            before_send_transaction=before_send_transaction,
            # Privacy
            send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
            # Configuration
            debug=settings.SENTRY_DEBUG,
            max_breadcrumbs=settings.SENTRY_MAX_BREADCRUMBS,
            attach_stacktrace=True,
            # Release tracking (optional - add later)
            # release=f"{settings.PROJECT_NAME}@{settings.VERSION}",
            # Server name (optional)
            server_name=f"{settings.PROJECT_NAME}-{settings.ENVIRONMENT.value}",
        )

        logger.info(
            "sentry_initialized",
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            debug=settings.SENTRY_DEBUG,
        )
    except Exception as e:
        logger.error(
            "sentry_initialization_failed",
            error=str(e),
            environment=settings.ENVIRONMENT.value,
            exc_info=True,
        )
