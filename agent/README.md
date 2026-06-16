# SuperBizAgent

Enterprise AI chat and operations assistant with RAG knowledge retrieval and AIOps diagnosis.

### ✨ Features

- 🤖 **Intelligent Chat** - LangChain multi-turn conversations with streaming responses or non-streaming responses
- 📚 **RAG Q&A** - RAG question answering with document upload and automatic vector indexing
- 🔧 **AIOps Diagnosis** - Automated incident diagnosis and root-cause analysis with a Plan-Execute-Replan workflow
- 🌐 **Web Interface** - Modern UI supporting multiple conversation modes: quick Q&A and streaming chat
- 🔌 **MCP Integration** - Integrated tools for log queries and monitoring data

## Tech Stack

- **Framework**: FastAPI, LangChain, LangGraph
- **LLM**: (OpenAI)GPT-5.4-nano or other OpenAI-compatible chat models
- **Vector Database**: Milvus vector database
- **Tool Protocol**: MCP (Model Context Protocol)

### Quick start Locally

## Requirements

- Docker or Docker Desktop
- OpenAI API key or DashScope API key

## Local Docker Stack
This launch method is intended to be repeatable locally without access to the AWS account. The local profile runs the backend, MCP servers, Milvus, Attu, demo CLS logs, and a demo Prometheus server through Docker Compose.

## First Run

```bash
cd agent
cp .env.local.example .env.local
```

Edit `.env.local` and set at least one LLM key:

```env
OPENAI_API_KEY=...
or
DASHSCOPE_API_KEY=...
```

Then start the full stack:
```bash
make local-up
```

Then open:

```bash
http://localhost:9900
```

This runs:

```text
backend      FastAPI app and static web UI
cls-mcp      CLS MCP server using local demo logs
monitor-mcp  Prometheus/monitoring MCP server
standalone   Milvus vector database
prometheus   Demo Prometheus server with a firing alert
attu         Milvus web UI
minio/etcd   Milvus dependencies
```

## URLs

```text
Web UI/API: http://localhost:9900
API docs:   http://localhost:9900/docs
Prometheus: http://localhost:9090
Attu:       http://localhost:8000
MinIO:      http://localhost:9001
```

Stop the stack with:

```bash
make local-down
```

## Logs

```bash
make local-logs
```

## Functional Architecture

```mermaid
flowchart BT
    subgraph storage["Knowledge Storage Layer"]
        doc1["Service 1 Business Integration Guide"]
        doc2["Service 2 Business Integration Guide"]
        doc3["Service 3 Business Integration Guide"]
        alert1["Service 1 Alert Handling Guide"]
        alert2["Service 2 Alert Handling Guide"]
        alert3["Service 3 Alert Handling Guide"]
        ticket1["Service 1 Historical Ticket Records"]
        ticket2["Service 2 Historical Ticket Records"]
        ticket3["Service 3 Historical Ticket Records"]
        vector["Vector Database"]
        doc1 --> vector
        doc2 --> vector
        doc3 --> vector
        alert1 --> vector
        alert2 --> vector
        alert3 --> vector
        ticket1 --> vector
        ticket2 --> vector
        ticket3 --> vector
    end

    subgraph core["Core Component Service Layer"]
        loader["Loader"]
        indexer["Indexer"]
        retriever["Retriever"]
        transformer["Transformer"]
        chatModel["Chat Model"]
        prompt["Prompt"]
        tool["Tool"]
        mcp["MCP"]
    end

    subgraph agents["Agent Business Layer"]
        conversation["Conversation Agent"]
        aiops["AIOps Agent"]
        knowledge["Knowledge Base Agent"]
        other["Other Agents"]
    end

    subgraph api["API Access Layer"]
        chat["/api/chat"]
        chatStream["/api/chat_stream"]
        upload["/api/upload"]
        aiopsApi["/api/aiops"]
    end

    storage --> core
    core --> agents
    conversation --> chat
    conversation --> chatStream
    knowledge --> upload
    aiops --> aiopsApi
```

## Local Runtime Architecture

```text
Browser
  -> localhost:9900
      -> FastAPI backend
          -> cls-mcp:8003
          -> monitor-mcp:8004
          -> standalone(Milvus vector database):19530
          -> prometheus:9090
```

Local Docker services are defined by:

```text
vector-database.yml
docker-compose.local.yml
```

## Notes

The local Prometheus alert is intentionally always firing. It lets the AIOps
diagnosis flow demonstrate real alert retrieval without requiring AWS Managed
Prometheus.

The local CLS MCP service runs with `CLS_MODE=demo`, so log search tools read
from `demo-data/cls_logs.json` instead of CloudWatch Logs. The demo timestamps
are made relative to the current time at query time, so recent-window searches
continue to return useful sample incidents.



### Live Demo deployed on AWS 

- Frontend: https://static-rho-six.vercel.app
- Backend health: http://oncall-agent-alb-859528003.ap-southeast-2.elb.amazonaws.com/live

The Vercel frontend rewrites `/api/*` requests to the AWS backend.


## API

| Feature | Method | Path | Description |
|---------|--------|------|----------------------|
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

## Common Commands

```bash
make local-up          # Start full local Docker stack
make local-down        # Stop full local Docker stack
make local-logs        # View local Docker logs
make local-status      # Check local Docker services
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

## Cloud Architecture

```text
Vercel static frontend
  -> /api/* rewrite
      -> AWS ALB
          -> ECS backend service
              -> one Fargate task
                  -> backend container          :9900
                  -> CLS MCP container          :8003
                  -> Monitor MCP container      :8004
                  -> AWS ADOT collector sidecar
              -> EC2 Milvus
              -> AWS Managed Prometheus
              -> CloudWatch Logs
```

The cloud stack is the live demo path. In this profile, `cls-mcp` runs in
`CLS_MODE=cloudwatch` and reads real CloudWatch Logs through AWS IAM. The
backend calls MCP through localhost inside the same ECS task:

```text
MCP_CLS_URL=http://127.0.0.1:8003/mcp
MCP_MONITOR_URL=http://127.0.0.1:8004/mcp
```


## License

MIT License
