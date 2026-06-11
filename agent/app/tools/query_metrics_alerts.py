"""Prometheus alert query tool

Fetch alerts produced by current rules through Prometheus HTTP API GET /api/v1/alerts
including pending/firing states. Each alert is uniquely identified by full labels and matches Prometheus
documentation; do not deduplicate only by alertname, or same-name rules on multiple instances may be merged incorrectly.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
from langchain_core.tools import tool
from loguru import logger

from app.config import config

# Prometheus Alerts API path relative to base URL, alongside Query API /api/v1/query
ALERTS_API_PATH = "/api/v1/alerts"

# Common labels included in simplified output for quick service/instance/severity identification; omitted when absent
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
    """Alert unique key: full labels as sorted-key JSON, used for deduplication or merging duplicates.
    This converts labels to JSON with sorted keys.
    Why sorted keys? These two dicts are logically the same:
    {"alertname": "HighCPU", "instance": "a"}
    {"instance": "a", "alertname": "HighCPU"}
    Sorting keys makes sure they produce the same identity string.
    ensure_ascii=False keeps non-ASCII characters readable.
    separators=(",", ":") makes compact JSON without extra spaces.
    """
    return json.dumps(labels, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def calculate_duration(active_at_str: str) -> str:
    """Compute human-readable duration since activeAt relative to current UTC."""
    active_at = _parse_active_at(active_at_str)
    if active_at is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    delta = now - active_at
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def query_prometheus_alerts_api() -> tuple[dict[str, Any], str | None]:
    """Request GET {prometheus_base_url}/api/v1/alerts.

    Return (JSON body, error message). On success the second item is None; on HTTP or JSON parse failure the first item is an empty dict.
    """
    base_url = config.prometheus_base_url.rstrip("/")
    api_url = f"{base_url}{ALERTS_API_PATH}"
    logger.info("Querying Prometheus alerts: {}", api_url)
    try:
        with httpx.Client(timeout=config.prometheus_request_timeout) as client:
            resp = client.get(api_url)
            resp.raise_for_status() # Raises an exception for HTTP error responses liek 404, 500, 
            body = resp.json() 
    # Handles network errors, timeout errors, and HTTp status errors
    except httpx.HTTPError as e:
        return {}, f"failed to query Prometheus alerts: {e}"
    # Hanldes invalid JSON response bodies
    except json.JSONDecodeError as e:
        return {}, f"failed to parse response: {e}"
    return body, None


def _pick_common_labels(labels: dict[str, Any]) -> dict[str, Any]:
    """Extract common dimensions from labels to reduce the cost for the Agent to read the full label table."""
    out: dict[str, Any] = {}
    for k in COMMON_LABEL_KEYS:
        # Skips [alertname], because the simplified alert already has an [alert_name] field
        if k == "alertname":
            continue
        v = labels.get(k)
        if v is not None and v != "":
            out[k] = v
    return out


def _simplify_alerts(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Convert Prometheus data.alerts to a simplified list and sort by activeAt descending.

    Return (simplified_alerts, state_counts).
    Prometheus normally returns:
    {
        "status": "success",
        "data": {
            "alerts": [...]
        }
    }

    Prometheus alert shape usually looks like:
    {
        "labels": {...},
        "annotations": {...},
        "state": "firing",
        "activeAt": "..."
    }
    """
    data = result.get("data") or {}
    alerts = data.get("alerts") or []
    if not isinstance(alerts, list):
        return [], {}

    simplified: list[dict[str, Any]] = []
    # If upstream occasionally emits duplicate entries with identical labels, keep only one by label identity
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
        alert_name = str(labels.get("alertname", "") or "")

        simplified.append(
            {
                "alert_name": alert_name,
                "labels": labels,
                "common_labels": _pick_common_labels(labels),
                "description": str(annotations.get("description", "") or ""),
                "summary": str(annotations.get("summary", "") or ""),
                "state": state,
                "active_at": active_at,
                "duration": calculate_duration(active_at),
            }
        )

    # Newest first: sort by activeAt descending; unparsable times go last for easier human scanning
    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        dt = _parse_active_at(str(item.get("active_at", "")))
        if dt is None:
            return (1, 0.0)
        # Valid timestamps go first. The negative timestamp makes newer alerts sort before older alerts.
        return (0, -dt.timestamp())

    simplified.sort(key=sort_key)
    return simplified, state_counts


@tool
def query_prometheus_alerts() -> str:
    """Query current active alerts from Prometheus server via HTTP GET /api/v1/alerts.

    Use cases: user asks whether alerts exist, which rules are firing/pending, or what triggered recently
    operations/observability questions about investigating monitoring alerts or current Prometheus alert-rule state; user does not need to
    provide parameters; call directly to fetch server-aggregated alerts.

    Behavior: fetch alerts from Prometheus configured by prometheus_base_url; results are sorted by activation time
    newest to oldest; each item includes alert name, labels, common-dimension summary, description/summary annotations, status and
    duration. Returns a JSON string containing success, alerts, state_counts, and related fields.

    Note: this is the Prometheus built-in alerts API, not a PromQL metric query and not Alertmanager
    notification/silence API; use MCP or other metric tools for metric curves.

    Returns:
        str: JSON string. On success contains alert list and state counts; on failure contains success=false and error.
    """
    result, err = query_prometheus_alerts_api()
    if err:
        out = {
            "success": False,
            "error": err,
            "message": "Failed to query Prometheus alerts",
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    if result.get("status") != "success":
        err_msg = result.get("error") or result.get("errorType") or "Prometheus returned non-success status"
        out = {
            "success": False,
            "error": str(err_msg),
            "message": "Failed to query Prometheus alerts",
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    simplified, state_counts = _simplify_alerts(result)
    out = {
        "success": True,
        "alerts": simplified,
        "state_counts": state_counts,
        "total": len(simplified),
        "message": f"Fetched {len(simplified)} alerts sorted by activeAt descending; state distribution: {state_counts}",
    }
    logger.info("Prometheus alerts query completed: {} alerts, states={}", len(simplified), state_counts)
    return json.dumps(out, ensure_ascii=False, indent=2)
