FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=9900

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY pyproject.toml ./
COPY app ./app
COPY mcp_servers ./mcp_servers
COPY static ./static
COPY aiops-docs ./aiops-docs
COPY prometheus-demo ./prometheus-demo
COPY demo-data ./demo-data

RUN pip install --upgrade pip \
    && pip install . \
    && mkdir -p /app/uploads /app/logs \
    && chown -R app:app /app

USER app

EXPOSE 9900

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/live || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9900"]
