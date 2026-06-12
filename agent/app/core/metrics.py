"""Prometheus metrics for the FastAPI application."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, Info, generate_latest
from starlette.responses import Response as StarletteResponse

from app.config import config


APP_INFO = Info("superbizagent_app", "Application build and runtime information")
HTTP_REQUESTS = Counter(
    "superbizagent_http_requests_total",
    "Total HTTP requests handled by the backend",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "superbizagent_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)


APP_INFO.info(
    {
        "name": config.app_name,
        "version": config.app_version,
    }
)


def _route_path(request: Request) -> str:
    """Return a low-cardinality route path for metrics labels."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return str(path)
    return request.url.path


async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Record request count and latency for non-metrics requests."""
    if request.url.path == "/metrics":
        return await call_next(request)

    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        labels = {
            "method": request.method,
            "path": _route_path(request),
        }
        HTTP_REQUEST_DURATION.labels(**labels).observe(duration)
        HTTP_REQUESTS.labels(status=str(status_code), **labels).inc()


def metrics_response() -> StarletteResponse:
    """Return Prometheus exposition format."""
    return StarletteResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
