"""
MCP client management
Provides a global singleton MCP client to avoid repeated initialization

MCP: Model Context Protocol
- A way for the agent to connect to external tool servers

Realize four things:
1. Keeps one shared MCP client instance for the whole app.
2. Loads MCP tools safely.
3. Adds retry behavior when MCP tool calls fail.
4. Checks whether MCP server config looks suspicious.
"""

import asyncio
from typing import Optional, Dict, Any, List, Union

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import CallToolResult, TextContent
from loguru import logger


# Global MCP client, lazily initialized
# Module-level global variable
# At first, no MCP client, it is None
# Later when get_mcp_client() called, the variable stores the shared client instance
# singleton pattern
_mcp_client: Optional[MultiServerMCPClient] = None

# Converts an exeption into a readable string
# Accepts any [BaseException]
def format_exception_chain(exc: BaseException) -> str:
    """
    Expand ExceptionGroup / TaskGroup errors so logs can show the real child exceptions.
    """
    # Some modern Python errors, like ExeptionGroup, contain multiple child exception in .exceptions
    sub_exceptions = getattr(exc, "exceptions", None)
    if sub_exceptions is not None:
        lines = [str(exc)]
        for i, sub in enumerate(sub_exceptions):
            lines.append(f"  [{i}] {format_exception_chain(sub)}")
        return "\n".join(lines)

    # For a normal exception, creae text like ValueError: invalid value
    msg = f"{type(exc).__name__}: {exc}"
    # Get the underlying cause/context of the exception, if any
    cause = exc.__cause__ or exc.__context__
    if cause is not None and cause is not exc:
        return f"{msg}\n  caused by: {format_exception_chain(cause)}"
    return msg

# Defines an async function that loads tools from an MCP client.
# Returns a tuple:
#   - IF successful: ([tool1, tool2], None)
#   - IF failed: ([], "error details")
async def load_mcp_tools_safe(
    client: MultiServerMCPClient,
) -> tuple[list[Union[BaseTool, Any]], str | None]:
    """Load MCP tools; on failure return an empty list and readable error instead of raising."""
    try:
        tools = await client.get_tools()
        return tools, None
    except BaseException as e:
        return [], format_exception_chain(e)

"""
It wraps an MCP tool call and retries it if it fails.
"""
async def retry_interceptor(
    request: MCPToolCallRequest,
    handler,
    max_retries: int = 3,
    delay: float = 1.0,
):
    """MCP tool-call retry interceptor
    
    Automatically retry with exponential backoff when tool calls fail.
    If all retries fail, return a result containing the error instead of raising.
    
    MCPToolCallRequest structure:
    - name: str - Tool name
    - args: dict[str, Any] - Tool arguments
    - server_name: str - Server name
    
    Args:
        request: MCP tool call request.
        handler: actual function that performs the tool call.
        max_retries: Try up to 3 times by default.
        delay: Start with 1 second delay before retrying.
    
    Returns:
        CallToolResult: Tool call result or error information
    """

    # Stores the most recent error, so it can be reported if all retries all 
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(
                f"Calling MCP tool: {request.name} "
                f"(server: {request.server_name}, attempt  {attempt + 1}/{max_retries} )"
            )
            result = await handler(request)
            logger.info(f"MCP tool {request.name} call succeeded")
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(
                f"MCP tool {request.name} call failed "
                f"(attempt  {attempt + 1}/{max_retries} time): {str(e)}"
            )
            
            # If this is not the last attempt, wait and retry
            if attempt < max_retries - 1:
                # Calculate exponential backoff delay
                wait_time = delay * (2 ** attempt)  # exponential backoff
                logger.info(f"Waiting {wait_time:.1f} sbefore retrying...")
                await asyncio.sleep(wait_time) # wait before the next retry
    
    # All retries failed; return an error result instead of raising
    error_msg = f"Tool {request.name} after  {max_retries}  retries still failed: {str(last_error)}"
    logger.error(error_msg)

    # Return an MCP-compatible error result instead of raising an exception.
    # This lets the agent receive a tool result saying “this tool failed” instead of crashing the whole workflow.
    return CallToolResult(
        content=[TextContent(type="text", text=error_msg)],
        isError=True
    )


# Read MCP server config from configuration
from app.config import config

# Use the full MCP server config defined in configuration
DEFAULT_MCP_SERVERS = config.mcp_servers


async def get_mcp_client(
    servers: Optional[Dict[str, Dict[str, str]]] = None,
    tool_interceptors: Optional[List] = None,
    force_new: bool = False
) -> MultiServerMCPClient:
    """
    Get or initialize the MCP client without retry interceptor
    
    This is a singleton pattern so the app has one MCP client unless force_new=True
    
    Since langchain-mcp-adapters 0.1.0, MultiServerMCPClient no longer supports context-manager usage.
    Create the instance directly and use it.
    
    Args:
        servers: Optional MCP server config. If not given, use DEFAULT_MCP_SERVERS.
        tool_interceptors: Optional list of interceptors, like retry logic.
        force_new: If True, create a new client instead of using the global singleton
    
    Returns:
        MultiServerMCPClient: MCP client instance
    """
    global _mcp_client
    
    # If a new instance is requested, create and return it without caching
    if force_new:
        logger.info("Creating new MCP client instance, non-singleton")
        client = _create_mcp_client(
            servers or DEFAULT_MCP_SERVERS, 
            tool_interceptors
        )
        # __aenter__() is no longer needed; return directly
        return client
    
    # Singleton mode: return the existing instance if present
    if _mcp_client is None:
        logger.info("Initializing global MCP client...")
        _mcp_client = _create_mcp_client(
            servers or DEFAULT_MCP_SERVERS, 
            tool_interceptors
        )
        # __aenter__() is no longer needed; use directly
        logger.info("Global MCP client initialized")
    
    return _mcp_client


async def get_mcp_client_with_retry(
    servers: Optional[Dict[str, Dict[str, str]]] = None,
    tool_interceptors: Optional[List] = None,
    force_new: bool = False
) -> MultiServerMCPClient:
    """
    Get or initialize MCP client with retry support
    
    This is a singleton pattern so the app has one MCP client unless force_new=True
    The retry interceptor is automatically prepended to the interceptor list
    
    Args:
        servers: MCP server config,defaults to DEFAULT_MCP_SERVERS
        tool_interceptors: custom tool interceptor list appended after retry interceptor
        force_new: whether to force creating a new instance for special cases such as different config
    
    Returns:
        MultiServerMCPClient: MCP client instance with retry support
    """
    # Build interceptor list with retry interceptor first
    interceptors = [retry_interceptor]
    if tool_interceptors:
        interceptors.extend(tool_interceptors)
    
    return await get_mcp_client(
        servers=servers,
        tool_interceptors=interceptors,
        force_new=force_new
    )


def _create_mcp_client(
    servers: Dict[str, Dict[str, str]],
    tool_interceptors: Optional[List] = None
) -> MultiServerMCPClient:
    """
    Create MCP client instance
    
    Args:
        servers: MCP server config
        tool_interceptors: tool interceptor list
    
    Returns:
        MultiServerMCPClient: uninitialized client instance
    """
    # MultiServerMCPClient accepts the servers config dict as the first argument
    # Format: {server_name: {"transport": "...", "url": "..."}}
    kwargs: Dict[str, Any] = {}
    
    if tool_interceptors:
        kwargs["tool_interceptors"] = tool_interceptors
    
    # The first argument is the servers config and is passed directly
    return MultiServerMCPClient(servers, **kwargs)  # type: ignore[arg-type]


def suggest_mcp_transport(url: str, transport: str) -> str | None:
    """Return a suggestion when URL and transport clearly mismatch; do not rewrite config automatically."""
    lower_url = url.lower()
    if "/sse" in lower_url and transport.replace("_", "-") in (
        "streamable-http",
        "http",
    ):
        return (
            f"MCP URL contains /sse/ but transport={transport!r},"
            "hosted endpoints such as Tencent Cloud should use transport=sse"
        )
    if transport == "sse" and "/mcp" in lower_url and "/sse" not in lower_url:
        return (
            f"MCP URL is a local FastMCP path but transport={transport!r},"
            "local services usually should use transport=streamable-http"
        )
    return None
