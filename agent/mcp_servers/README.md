# MCP Servers

These MCP servers provide log and monitoring tools for AIOps diagnosis.

## CLS Server

File: `cls_server.py`
Port: `8003`

Tools:
- `get_current_timestamp`
- `get_region_code_by_name`
- `get_topic_info_by_name`
- `search_service_logs`
- `search_log`

The bundled implementation returns mock data. For production, replace the mock logic with a real CLS provider implementation or use a hosted CLS MCP server.

## Monitor Server

File: `monitor_server.py`
Port: `8004`

Tools:
- `query_cpu_metrics`
- `query_memory_metrics`
- `query_process_list`
- `search_historical_tickets`
- `get_service_info`
- `list_all_services`

## Startup

```bash
python mcp_servers/cls_server.py
python mcp_servers/monitor_server.py
```

Or use Makefile targets:

```bash
make start-cls
make start-monitor
make status-mcp
```

## Real Provider Integration

For a real CLS provider, configure credentials through environment variables and replace mock data functions with SDK/API calls. Keep the tool names stable so the AIOps agent can continue using the same MCP interface.
