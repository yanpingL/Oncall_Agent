# SuperBizAgent

Enterprise AI chat and operations assistant with RAG knowledge retrieval and AIOps diagnosis.

## Features

- AI chat with LangChain and streaming responses
- RAG question answering with document upload and automatic vector indexing
- AIOps diagnosis with Plan-Execute-Replan workflow
- Static web UI with quick and streaming chat modes
- MCP integration for logs and monitoring tools

## Tech Stack

- FastAPI, LangChain, LangGraph
- DashScope or OpenAI-compatible chat models
- Milvus vector database
- MCP tool protocol

## Quick Start

### Requirements

- Python 3.11+
- Docker or Docker Desktop
- DashScope API key

### Linux/macOS

```bash
cd agent
pip install uv
uv venv
source .venv/bin/activate
uv pip install -e .
vim .env
make init
```

Start services later with:

```bash
make start
```

### Manual Startup

```bash
cd agent
source .venv/bin/activate

docker compose -f vector-database.yml up -d
python mcp_servers/cls_server.py
python mcp_servers/monitor_server.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

### Access

- Web UI: http://localhost:9900
- API docs: http://localhost:9900/docs
- Milvus Attu: http://localhost:8000
- MinIO: http://localhost:9001

## API

| Feature | Method | Path | Description |
|---|---|---|---|
| Chat | POST | `/api/chat` | Non-streaming chat |
| Streaming chat | POST | `/api/chat_stream` | SSE chat stream |
| AIOps diagnosis | POST | `/api/aiops` | Streaming diagnosis |
| File upload | POST | `/api/upload` | Upload and index documents |
| Health check | GET | `/health` | Service health |

## Example

```bash
curl -X POST "http://localhost:9900/api/chat"   -H "Content-Type: application/json"   -d '{"Id":"session-123","Question":"Hello"}'

curl -X POST "http://localhost:9900/api/aiops"   -H "Content-Type: application/json"   -d '{"session_id":"session-123"}'   --no-buffer
```

## Configuration

Create `agent/.env`:

```env
DASHSCOPE_API_KEY=your-api-key
DASHSCOPE_MODEL=qwen-max
MILVUS_HOST=localhost
MILVUS_PORT=19530
RAG_TOP_K=3
CHUNK_MAX_SIZE=800
CHUNK_OVERLAP=100
MCP_CLS_TRANSPORT=streamable-http
MCP_CLS_URL=http://localhost:8003/mcp
MCP_MONITOR_TRANSPORT=streamable-http
MCP_MONITOR_URL=http://localhost:8004/mcp
PROMETHEUS_BASE_URL=http://127.0.0.1:9090
```

For a real hosted CLS MCP endpoint, configure `MCP_CLS_TRANSPORT=sse` and point `MCP_CLS_URL` to the hosted SSE URL.

## Common Commands

```bash
make init              # Start Docker, services, and upload docs
make start             # Start MCP, Prometheus, and FastAPI
make stop              # Stop services
make restart           # Restart services
make up                # Start Milvus containers
make down              # Stop Milvus containers
make start-api         # Start FastAPI only
make start-monitor     # Start Monitor MCP only
make start-prometheus  # Start Prometheus demo container
make upload            # Upload aiops-docs into the vector DB
```

## AIOps Flow

1. Planner creates a diagnosis plan.
2. Executor calls local and MCP tools.
3. Replanner decides whether to continue, adjust the plan, or respond.
4. The final report is generated as Markdown and stored in the knowledge base.

## Troubleshooting

Check logs:

```bash
tail -f server.log
tail -f mcp_cls.log
tail -f mcp_monitor.log
```

Check ports:

```bash
lsof -i :9900
lsof -i :8003
lsof -i :8004
```

Restart Milvus:

```bash
docker compose -f vector-database.yml restart
```

## License

MIT License
