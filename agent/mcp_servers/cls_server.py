"""CloudWatch Logs MCP server.

This server keeps the original CLS-style tool names used by the AIOps agent,
but backs them with real AWS CloudWatch Logs queries.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CLS_MCP_Server")

mcp = FastMCP("CLS")

DEFAULT_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-2"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_MODE_NAMES = {"demo", "local", "mock"}
DEFAULT_LOG_TOPICS = [
    {
        "topic_id": "backend",
        "topic_name": "OnCall Agent backend logs",
        "service_name": "oncall-agent-backend-service",
        "region_code": DEFAULT_REGION,
        "log_group_name": "/ecs/superbizagent-backend",
        "description": "FastAPI backend application logs",
    },
    {
        "topic_id": "cls-mcp",
        "topic_name": "OnCall Agent CLS MCP logs",
        "service_name": "oncall-agent-cls-mcp-service",
        "region_code": DEFAULT_REGION,
        "log_group_name": "/ecs/oncall-agent-cls-mcp",
        "description": "CLS MCP server logs",
    },
    {
        "topic_id": "monitor-mcp",
        "topic_name": "OnCall Agent Monitor MCP logs",
        "service_name": "oncall-agent-monitor-mcp-service",
        "region_code": DEFAULT_REGION,
        "log_group_name": "/ecs/oncall-agent-monitor-mcp",
        "description": "Monitor MCP server logs",
    },
    {
        "topic_id": "adot-collector",
        "topic_name": "OnCall Agent ADOT collector logs",
        "service_name": "oncall-agent-backend-service",
        "region_code": DEFAULT_REGION,
        "log_group_name": "/ecs/oncall-agent-adot-collector",
        "description": "AWS Distro for OpenTelemetry collector logs",
    },
]

BUILTIN_DEMO_LOG_EVENTS = [
    {
        "topic_id": "backend",
        "offset_seconds": -300,
        "logStreamName": "backend/demo",
        "message": "INFO request_id=demo-001 POST /api/chat completed status=200 latency_ms=184",
    },
    {
        "topic_id": "backend",
        "offset_seconds": -240,
        "logStreamName": "backend/demo",
        "message": "WARN request_id=demo-002 aiops diagnosis detected elevated checkout latency service=payment-api latency_ms=2380",
    },
    {
        "topic_id": "backend",
        "offset_seconds": -180,
        "logStreamName": "backend/demo",
        "message": "ERROR request_id=demo-003 service=payment-api dependency=postgres timeout after 5000ms",
    },
    {
        "topic_id": "monitor-mcp",
        "offset_seconds": -150,
        "logStreamName": "monitor-mcp/demo",
        "message": "INFO Prometheus query executed query='up' status=success samples=4",
    },
    {
        "topic_id": "cls-mcp",
        "offset_seconds": -120,
        "logStreamName": "cls-mcp/demo",
        "message": "INFO demo CLS search served local fixture events source=demo-data",
    },
    {
        "topic_id": "adot-collector",
        "offset_seconds": -90,
        "logStreamName": "adot-collector/demo",
        "message": "WARN otel collector exported partial batch exporter=prometheus remote_write_dropped=2",
    },
]


def log_tool_call(func):
    """Log MCP tool calls with arguments and a compact result summary."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__
        logger.info("=" * 80)
        logger.info("Method called: %s", method_name)

        if kwargs:
            try:
                params_str = json.dumps(kwargs, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                params_str = str(kwargs)
            logger.info("Arguments:\n%s", params_str)
        else:
            logger.info("Arguments: none")

        try:
            result = func(*args, **kwargs)
            logger.info("Return status: SUCCESS")
            if isinstance(result, dict):
                summary = {
                    k: v if not isinstance(v, (list, dict)) else f"<{type(v).__name__} with {len(v)} items>"
                    for k, v in list(result.items())[:5]
                }
                logger.info("Result summary: %s", json.dumps(summary, ensure_ascii=False))
            else:
                logger.info("Result: %s", result)
            logger.info("=" * 80)
            return result
        except Exception as e:
            logger.exception("Return status: ERROR; error message: %s", e)
            logger.info("=" * 80)
            raise

    return wrapper


def _load_topics() -> list[dict[str, Any]]:
    """Load topic-to-log-group mapping from env, falling back to project defaults."""
    raw = os.getenv("CLS_LOG_TOPICS_JSON", "").strip()
    if not raw:
        return DEFAULT_LOG_TOPICS

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Invalid CLS_LOG_TOPICS_JSON; using defaults: %s", e)
        return DEFAULT_LOG_TOPICS

    if not isinstance(parsed, list):
        logger.warning("CLS_LOG_TOPICS_JSON must be a JSON list; using defaults")
        return DEFAULT_LOG_TOPICS

    topics: list[dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            logger.warning("Ignoring non-object CLS topic at index %s", idx)
            continue
        log_group_name = str(item.get("log_group_name", "")).strip()
        if not log_group_name:
            logger.warning("Ignoring CLS topic without log_group_name at index %s", idx)
            continue
        topic_id = str(item.get("topic_id") or log_group_name).strip()
        service_name = str(item.get("service_name") or topic_id).strip()
        topics.append(
            {
                "topic_id": topic_id,
                "topic_name": str(item.get("topic_name") or log_group_name),
                "service_name": service_name,
                "region_code": str(item.get("region_code") or DEFAULT_REGION),
                "log_group_name": log_group_name,
                "description": str(item.get("description") or f"CloudWatch log group {log_group_name}"),
            }
        )

    return topics or DEFAULT_LOG_TOPICS


def _logs_client(region_name: str):
    return boto3.client("logs", region_name=region_name)


def _cls_mode() -> str:
    return os.getenv("CLS_MODE", "cloudwatch").strip().lower()


def _demo_logs_path() -> Path:
    raw_path = os.getenv("CLS_DEMO_LOGS_PATH", "demo-data/cls_logs.json").strip()
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _topic_public_view(topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic_id": topic["topic_id"],
        "topic_name": topic["topic_name"],
        "service_name": topic["service_name"],
        "region_code": topic["region_code"],
        "log_group_name": topic["log_group_name"],
        "description": topic["description"],
    }


def _find_topic(topic_id: str) -> dict[str, Any] | None:
    for topic in _load_topics():
        if topic["topic_id"] == topic_id or topic["log_group_name"] == topic_id:
            return topic
    return None


def _format_timestamp(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def _extract_terms(query: str) -> list[list[str]]:
    """Parse a small subset of common log search syntax for client-side filtering.

    Each OR clause becomes a list of terms. A log matches if every term in one
    clause appears in the message or stream name.
    """
    clauses = re.split(r"\s+OR\s+", query, flags=re.IGNORECASE)
    parsed: list[list[str]] = []
    for clause in clauses:
        raw_terms = re.findall(r'"([^"]+)"|(\S+)', clause)
        terms: list[str] = []
        for quoted, bare in raw_terms:
            token = (quoted or bare).strip()
            if not token or token.upper() in {"AND", "OR"}:
                continue
            if ":" in token:
                _, value = token.split(":", 1)
                token = value
            token = token.strip("()'\"")
            token = token.lstrip("><=!")
            if token:
                terms.append(token.lower())
        if terms:
            parsed.append(terms)
    return parsed


def _event_matches_query(event: dict[str, Any], query: Optional[str]) -> bool:
    if not query or not query.strip():
        return True

    haystack = " ".join(
        [
            str(event.get("message", "")),
            str(event.get("logStreamName", "")),
        ]
    ).lower()

    clauses = _extract_terms(query)
    if not clauses:
        return True
    return any(all(term in haystack for term in clause) for clause in clauses)


def _to_log_entry(event: dict[str, Any]) -> dict[str, Any]:
    timestamp = int(event.get("timestamp", 0))
    ingestion_time = int(event.get("ingestionTime", 0))
    message = str(event.get("message", "")).rstrip()
    level = "UNKNOWN"
    upper_message = message.upper()
    for candidate in ("ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"):
        if candidate in upper_message:
            level = "WARN" if candidate == "WARNING" else candidate
            break

    return {
        "timestamp": _format_timestamp(timestamp) if timestamp else "",
        "ingestion_time": _format_timestamp(ingestion_time) if ingestion_time else "",
        "level": level,
        "log_stream": event.get("logStreamName", ""),
        "message": message,
        "event_id": event.get("eventId", ""),
    }


def _load_demo_log_events() -> list[dict[str, Any]]:
    path = _demo_logs_path()
    raw_events: list[dict[str, Any]]

    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                events = parsed.get("events", [])
            else:
                events = parsed
            raw_events = [event for event in events if isinstance(event, dict)]
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to read CLS demo logs from %s; using built-in demo logs: %s", path, e)
            raw_events = BUILTIN_DEMO_LOG_EVENTS
    else:
        logger.warning("CLS demo logs file not found at %s; using built-in demo logs", path)
        raw_events = BUILTIN_DEMO_LOG_EVENTS

    now_ms = int(time.time() * 1000)
    normalized_events: list[dict[str, Any]] = []
    for idx, event in enumerate(raw_events):
        normalized = dict(event)
        if "timestamp" not in normalized:
            offset_seconds = int(normalized.get("offset_seconds", -idx - 1))
            normalized["timestamp"] = now_ms + offset_seconds * 1000
        normalized.setdefault("ingestionTime", normalized["timestamp"])
        normalized.setdefault("eventId", f"demo-{idx + 1}")
        normalized.setdefault("logStreamName", f"{normalized.get('topic_id', 'demo')}/demo")
        normalized_events.append(normalized)

    normalized_events.sort(key=lambda item: int(item.get("timestamp", 0)), reverse=True)
    return normalized_events


def _search_demo_log(
    topic: dict[str, Any],
    start_time: int,
    end_time: int,
    query: Optional[str],
    safe_limit: int,
    started: float,
) -> dict[str, Any]:
    topic_ids = {topic["topic_id"], topic["log_group_name"]}
    matched_events = [
        event
        for event in _load_demo_log_events()
        if str(event.get("topic_id") or event.get("log_group_name")) in topic_ids
        and int(start_time) <= int(event.get("timestamp", 0)) <= int(end_time)
        and _event_matches_query(event, query)
    ][:safe_limit]
    logs = [_to_log_entry(event) for event in matched_events]
    took_ms = int((time.monotonic() - started) * 1000)

    return {
        "topic_id": topic["topic_id"],
        "log_group_name": topic["log_group_name"],
        "region_code": topic["region_code"],
        "source": "demo",
        "start_time": start_time,
        "end_time": end_time,
        "query": query,
        "limit": safe_limit,
        "total": len(logs),
        "logs": logs,
        "next_token": None,
        "took_ms": took_ms,
        "message": f"Successfully queried {len(logs)} local demo log events",
    }


@mcp.tool()
@log_tool_call
def get_current_timestamp() -> int:
    """Get the current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


@mcp.tool()
@log_tool_call
def get_region_code_by_name(region_name: str) -> Dict[str, Any]:
    """Find an AWS region code by a common display name or region code."""
    region_mapping = {
        "Sydney": {"region_code": "ap-southeast-2", "region_name": "Sydney", "available": True},
        "ap-southeast-2": {
            "region_code": "ap-southeast-2",
            "region_name": "Sydney",
            "available": True,
        },
        "Singapore": {
            "region_code": "ap-southeast-1",
            "region_name": "Singapore",
            "available": True,
        },
        "us-east-1": {
            "region_code": "us-east-1",
            "region_name": "N. Virginia",
            "available": True,
        },
    }

    result = region_mapping.get(region_name)
    if result:
        return result
    return {
        "region_code": region_name if region_name.startswith(("ap-", "us-", "eu-")) else None,
        "region_name": region_name,
        "available": region_name.startswith(("ap-", "us-", "eu-")),
        "message": "Unknown display name; pass an AWS region code directly if you know it.",
    }


@mcp.tool()
@log_tool_call
def get_topic_info_by_name(topic_name: str, region_code: Optional[str] = None) -> Dict[str, Any]:
    """Find configured log topic information by topic name."""
    topic_name_lower = topic_name.lower()
    for topic in _load_topics():
        if region_code and topic["region_code"] != region_code:
            continue
        if topic["topic_name"].lower() == topic_name_lower or topic["log_group_name"].lower() == topic_name_lower:
            return _topic_public_view(topic)

    return {
        "topic_id": None,
        "topic_name": topic_name,
        "region_code": region_code,
        "error": f"Topic not found: {topic_name}",
    }


@mcp.tool()
@log_tool_call
def search_topic_by_service_name(
    service_name: str,
    region_code: Optional[str] = None,
    fuzzy: bool = True,
) -> Dict[str, Any]:
    """Search configured log groups by service name.

    Use the returned topic_id with search_log.
    """
    matched_topics = []
    service_name_lower = service_name.lower()

    for topic in _load_topics():
        if region_code and topic["region_code"] != region_code:
            continue

        candidates = [
            topic["service_name"].lower(),
            topic["topic_name"].lower(),
            topic["log_group_name"].lower(),
            topic["topic_id"].lower(),
        ]

        if fuzzy:
            if any(service_name_lower in candidate or candidate in service_name_lower for candidate in candidates):
                matched_topics.append(_topic_public_view(topic))
        elif service_name_lower in candidates:
            matched_topics.append(_topic_public_view(topic))

    return {
        "total": len(matched_topics),
        "topics": matched_topics,
        "query": {
            "service_name": service_name,
            "region_code": region_code,
            "fuzzy": fuzzy,
        },
        "message": (
            f"Found {len(matched_topics)} matching log topics"
            if matched_topics
            else f"No log topic found for service '{service_name}'"
        ),
    }


@mcp.tool()
@log_tool_call
def search_log(
    topic_id: str,
    start_time: int,
    end_time: int,
    query: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Search log events for a configured topic.

    By default this queries AWS CloudWatch Logs. Set CLS_MODE=demo, local, or mock
    to serve deterministic local demo logs for Docker-based development.

    Args:
        topic_id: topic ID returned by search_topic_by_service_name, or a CloudWatch log group name.
        start_time: start timestamp in milliseconds.
        end_time: end timestamp in milliseconds.
        query: optional keyword query. Supports common terms such as ERROR, WARN, level:ERROR,
            or OR expressions like "level:ERROR OR level:WARN".
        limit: maximum number of matching log events to return.
    """
    topic = _find_topic(topic_id)
    if topic is None:
        return {
            "topic_id": topic_id,
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": 0,
            "logs": [],
            "error": f"Topic does not exist: {topic_id}",
            "message": "Topic not found. Use search_topic_by_service_name first, or pass a log group name configured in CLS_LOG_TOPICS_JSON.",
        }

    if end_time < start_time:
        return {
            "topic_id": topic_id,
            "log_group_name": topic["log_group_name"],
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": limit,
            "total": 0,
            "logs": [],
            "error": "end_time must be greater than or equal to start_time",
        }

    safe_limit = max(1, min(int(limit), 500))
    fetch_limit = min(max(safe_limit * 5, safe_limit), 1000)
    started = time.monotonic()

    if _cls_mode() in DEMO_MODE_NAMES:
        return _search_demo_log(topic, start_time, end_time, query, safe_limit, started)

    logs_client = _logs_client(topic["region_code"])

    try:
        response = logs_client.filter_log_events(
            logGroupName=topic["log_group_name"],
            startTime=int(start_time),
            endTime=int(end_time),
            limit=fetch_limit,
            interleaved=True,
        )
    except logs_client.exceptions.ResourceNotFoundException:
        return {
            "topic_id": topic["topic_id"],
            "log_group_name": topic["log_group_name"],
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": safe_limit,
            "total": 0,
            "logs": [],
            "error": f"CloudWatch log group not found: {topic['log_group_name']}",
        }
    except (BotoCoreError, ClientError) as e:
        return {
            "topic_id": topic["topic_id"],
            "log_group_name": topic["log_group_name"],
            "start_time": start_time,
            "end_time": end_time,
            "query": query,
            "limit": safe_limit,
            "total": 0,
            "logs": [],
            "error": str(e),
            "message": "Failed to query CloudWatch Logs. Check task role permissions and region/log group configuration.",
        }

    matched_events = [
        event
        for event in response.get("events", [])
        if _event_matches_query(event, query)
    ][:safe_limit]
    logs = [_to_log_entry(event) for event in matched_events]
    took_ms = int((time.monotonic() - started) * 1000)

    return {
        "topic_id": topic["topic_id"],
        "log_group_name": topic["log_group_name"],
        "region_code": topic["region_code"],
        "start_time": start_time,
        "end_time": end_time,
        "query": query,
        "limit": safe_limit,
        "total": len(logs),
        "logs": logs,
        "next_token": response.get("nextToken"),
        "took_ms": took_ms,
        "message": f"Successfully queried {len(logs)} CloudWatch log events",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8003, path="/mcp")
