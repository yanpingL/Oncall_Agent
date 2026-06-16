"""Prometheus HTTP client helpers, including Amazon Managed Prometheus SigV4 auth."""

from __future__ import annotations

import json
from typing import Any

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import get_session
from loguru import logger

from app.config import config


def _should_sign_prometheus_request(base_url: str) -> bool:
    """Return whether requests to this Prometheus endpoint should use AWS SigV4."""
    auth_type = config.prometheus_auth_type.strip().lower()
    if auth_type == "sigv4":
        return True
    if auth_type == "none":
        return False
    return "aps-workspaces." in base_url


def _sigv4_headers(method: str, url: str) -> dict[str, str]:
    """Build AWS SigV4 headers for an AMP-compatible Prometheus request."""
    session = get_session()
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("AWS credentials were not found for Prometheus SigV4 request")

    frozen_credentials = credentials.get_frozen_credentials()
    request = AWSRequest(method=method, url=url)
    SigV4Auth(
        frozen_credentials,
        config.prometheus_sigv4_service,
        config.prometheus_sigv4_region,
    ).add_auth(request)
    return dict(request.headers.items())


def query_prometheus_json(path: str) -> tuple[dict[str, Any], str | None]:
    """Query a Prometheus-compatible JSON endpoint.

    Returns:
        tuple: (JSON body, error message). On success, error is None.
    """
    base_url = config.prometheus_base_url.rstrip("/")
    api_url = f"{base_url}{path}"
    logger.info("Querying Prometheus endpoint: {}", api_url)

    headers: dict[str, str] = {}
    try:
        if _should_sign_prometheus_request(base_url):
            headers.update(_sigv4_headers("GET", api_url))

        with httpx.Client(timeout=config.prometheus_request_timeout) as client:
            resp = client.get(api_url, headers=headers)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        return {}, f"failed to query Prometheus endpoint: {e}"
    except json.JSONDecodeError as e:
        return {}, f"failed to parse Prometheus response: {e}"
    except Exception as e:
        return {}, f"failed to prepare Prometheus request: {e}"

    return body, None
