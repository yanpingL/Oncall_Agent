"""Tools module containing tools callable by Agents"""

from app.tools.knowledge_tool import retrieve_knowledge
from app.tools.time_tool import get_current_time

# Default local tool set for in-process tools. Monitoring tools are exposed through MCP Monitor.
DEFAULT_LOCAL_AGENT_TOOLS = (
    retrieve_knowledge,
    get_current_time,
)

__all__ = [
    "DEFAULT_LOCAL_AGENT_TOOLS",
    "retrieve_knowledge",
    "get_current_time",
]
