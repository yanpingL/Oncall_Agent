"""Prometheus alert API helpers shared by local tools and MCP tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.prometheus_client import query_prometheus_json

ALERTS_API_PATH = "/api/v1/alerts"
COMMON_LABEL_KEYS = ("alertname", "severity", "instance", "job", "namespace", "pod")


def _parse_active_at(active_at_str: str) -> datetime | None:
    """Parse Prometheus activeAt, RFC3339 or Z-suffixed, as UTC time."""
    if not active_at_str:
        return None
    try:
        s = active_at_str.replace("Z", "+00:00", 1)
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _labels_identity(labels: dict[str, Any]) -> str:
    """Build a stable alert identity from the full label set."""
    return json.dumps(labels, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def calculate_duration(active_at_str: str) -> str:
    """Compute human-readable duration since activeAt relative to current UTC."""
    active_at = _parse_active_at(active_at_str)
    if active_at is None:
        return "unknown"
    delta = datetime.now(timezone.utc) - active_at
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def _pick_common_labels(labels: dict[str, Any]) -> dict[str, Any]:
    """Extract common dimensions for quick agent scanning."""
    out: dict[str, Any] = {}
    for key in COMMON_LABEL_KEYS:
        if key == "alertname":
            continue
        value = labels.get(key)
        if value is not None and value != "":
            out[key] = value
    return out


def _simplify_alerts(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Convert Prometheus data.alerts to a simplified list sorted by activeAt descending."""
    data = result.get("data") or {}
    alerts = data.get("alerts") or []
    if not isinstance(alerts, list):
        return [], {}

    simplified: list[dict[str, Any]] = []
    seen_identity: set[str] = set()
    state_counts: dict[str, int] = {}

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}
        if not isinstance(labels, dict):
            labels = {}
        if not isinstance(annotations, dict):
            annotations = {}

        identity = _labels_identity(labels)
        if identity in seen_identity:
            continue
        seen_identity.add(identity)

        state = str(alert.get("state", "") or "")
        state_counts[state] = state_counts.get(state, 0) + 1
        active_at = str(alert.get("activeAt", "") or "")

        simplified.append(
            {
                "alert_name": str(labels.get("alertname", "") or ""),
                "labels": labels,
                "common_labels": _pick_common_labels(labels),
                "description": str(annotations.get("description", "") or ""),
                "summary": str(annotations.get("summary", "") or ""),
                "state": state,
                "active_at": active_at,
                "duration": calculate_duration(active_at),
            }
        )

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        dt = _parse_active_at(str(item.get("active_at", "")))
        if dt is None:
            return (1, 0.0)
        return (0, -dt.timestamp())

    simplified.sort(key=sort_key)
    return simplified, state_counts


def query_prometheus_alerts_api() -> tuple[dict[str, Any], str | None]:
    """Request GET {prometheus_base_url}/api/v1/alerts."""
    return query_prometheus_json(ALERTS_API_PATH)


def get_prometheus_alerts_summary() -> dict[str, Any]:
    """Return simplified Prometheus alerts as a dict."""
    result, err = query_prometheus_alerts_api()
    if err:
        return {
            "success": False,
            "error": err,
            "message": "Failed to query Prometheus alerts",
        }

    if result.get("status") != "success":
        err_msg = result.get("error") or result.get("errorType") or "Prometheus returned non-success status"
        return {
            "success": False,
            "error": str(err_msg),
            "message": "Failed to query Prometheus alerts",
        }

    simplified, state_counts = _simplify_alerts(result)
    out = {
        "success": True,
        "alerts": simplified,
        "state_counts": state_counts,
        "total": len(simplified),
        "message": f"Fetched {len(simplified)} alerts sorted by activeAt descending; state distribution: {state_counts}",
    }
    logger.info("Prometheus alerts query completed: {} alerts, states={}", len(simplified), state_counts)
    return out
