"""Prometheus alert query tool."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from app.core.prometheus_alerts import get_prometheus_alerts_summary


@tool
def query_prometheus_alerts() -> str:
    """Query current active alerts from the configured Prometheus server or AMP workspace.

    Use this when the user asks whether alerts exist, which rules are firing/pending,
    or what triggered recently. The result is sorted newest to oldest and includes
    labels, common dimensions, description/summary annotations, state, and duration.

    Returns:
        str: JSON string containing success, alerts, state_counts, total, and message.
    """
    return json.dumps(get_prometheus_alerts_summary(), ensure_ascii=False, indent=2)
