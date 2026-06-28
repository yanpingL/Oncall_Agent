
"""
Executor node: execute one plan step.
Implemented based on the official LangGraph tutorial.
"""

import json
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import get_mcp_client_with_retry, format_exception_chain
from .state import PlanExecuteState


def _format_past_steps(past_steps: list[tuple]) -> str:
    """Build a compact execution history for the current executor step."""
    if not past_steps:
        return "No steps have been executed yet."

    formatted = []
    for index, (step, result) in enumerate(past_steps, 1):
        result_text = str(result)
        if len(result_text) > 1200:
            result_text = result_text[:1200] + "\n...(result truncated)"
        formatted.append(f"Step {index}: {step}\nResult:\n{result_text}")
    return "\n\n".join(formatted)


def _tool_call_names(llm_response: Any) -> list[str]:
    """Extract requested tool names from an AIMessage-like response."""
    tool_calls = getattr(llm_response, "tool_calls", None) or []
    names: list[str] = []
    for call in tool_calls:
        if isinstance(call, dict):
            names.append(str(call.get("name", "")))
        else:
            names.append(str(getattr(call, "name", "")))
    return [name for name in names if name]


def _tool_call_field(tool_call: Any, field: str, default: Any = None) -> Any:
    """Read a field from LangChain tool call dicts or objects."""
    if isinstance(tool_call, dict):
        return tool_call.get(field, default)
    return getattr(tool_call, field, default)


def _serialize_tool_result(result: Any) -> str:
    """Convert arbitrary tool output into text safe for an LLM ToolMessage."""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except TypeError:
        return str(result)


def _make_tool_message(tool_call: Any, content: str, *, status: str = "success") -> ToolMessage:
    """Create a ToolMessage while preserving the tool_call_id expected by chat models."""
    tool_call_id = _tool_call_field(tool_call, "id") or _tool_call_field(tool_call, "tool_call_id") or "unknown_tool_call"
    tool_name = str(_tool_call_field(tool_call, "name", "unknown_tool"))
    return ToolMessage(
        content=content,
        tool_call_id=str(tool_call_id),
        name=tool_name,
        status=status,  # type: ignore[arg-type]
    )


async def _run_tool_call_safely(tool_call: Any, tools_by_name: dict[str, Any]) -> ToolMessage:
    """Run one requested tool call and convert every failure into a ToolMessage."""
    tool_name = str(_tool_call_field(tool_call, "name", "") or "")
    args = _tool_call_field(tool_call, "args", {}) or {}

    if not tool_name:
        return _make_tool_message(tool_call, "Tool call failed: missing tool name.", status="error")

    tool = tools_by_name.get(tool_name)
    if tool is None:
        return _make_tool_message(
            tool_call,
            f"Tool call failed: tool {tool_name!r} is not in the current available tool list.",
            status="error",
        )

    if not isinstance(args, dict):
        return _make_tool_message(
            tool_call,
            f"Tool call failed: arguments for tool {tool_name} must be an object/dict, got {type(args).__name__}.",
            status="error",
        )

    try:
        logger.info(f"Safely executing tool call: {tool_name}, argument keys: {list(args.keys())}")
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(args)
        else:
            result = tool.invoke(args)
        return _make_tool_message(tool_call, _serialize_tool_result(result))
    except BaseException as e:
        error_details = format_exception_chain(e)
        logger.warning(f"Tool {tool_name} failed and was converted to a tool message: {error_details}")
        return _make_tool_message(
            tool_call,
            f"Tool {tool_name} failed: {error_details}",
            status="error",
        )


async def _run_tool_calls_safely(tool_calls: list[Any], all_tools: list[Any]) -> list[ToolMessage]:
    """Run tool calls one by one so one failing MCP call cannot crash the graph."""
    tools_by_name = {
        tool.name: tool
        for tool in all_tools
        if hasattr(tool, "name")
    }
    messages: list[ToolMessage] = []
    for tool_call in tool_calls:
        messages.append(await _run_tool_call_safely(tool_call, tools_by_name))
    return messages


async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Executor node: execute the next step in the plan.
    
    Uses LangGraph tool-calling behavior to handle tool calls.
    """
    logger.info("=== Executor: executing step ===")

    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    # Do nothing if the plan is empty.
    if not plan:
        logger.info("Plan is empty; skipping execution")
        return {}

    # Take the first step.
    task = plan[0]
    logger.info(f"Current task: {task}")

    try:
        # Get local tools.
        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)

        # Get MCP tools.
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        logger.info(f"Available tools: local {len(local_tools)} + MCP {len(mcp_tools)}")

        # Combine all tools.
        all_tools = local_tools + mcp_tools

        # Create the LLM with bound tools.
        llm = llm_factory.create_chat_model(
            model=config.rag_model,
            temperature=0,
            streaming=False,
        )
        llm_with_tools = llm.bind_tools(all_tools)

        # Build messages using only the current step to avoid interference from the original task.
        messages = [
            SystemMessage(content="""You are a capable assistant responsible for executing specific task steps.

You may use available tools to complete the task. For each step:
1. Understand the goal of the step.
2. Select appropriate tools. If a tool is already specified, use that tool.
3. Call tools to obtain information.
4. Return the execution result.

Notes:
- If a tool call fails, explain the failure reason.
- Do not fabricate data. Return only information actually obtained.
- Before calling tools that depend on previous results, confirm that the required parameters exist in executed steps.
- If no log evidence is obtained, state directly that evidence is insufficient.
- Keep execution results clear and accurate.
- Focus on the current step and do not consider other tasks."""),
            HumanMessage(content=f"Executed steps and results:\n{_format_past_steps(past_steps)}"),
            HumanMessage(content=f"Please execute this task: {task}")
        ]

        # Step 1: The LLM decides whether to call tools.
        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"LLM response type: {type(llm_response)}")

        # Step 2: Execute tool calls if any were requested.
        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            tool_names = _tool_call_names(llm_response)
            logger.info(f"Detected {len(llm_response.tool_calls)} tool calls: {tool_names}")
            
            # Execute tools one by one. Avoid batching MCP tools with ToolNode because
            # a single adapter/parser exception can escape as a TaskGroup and stop the graph.
            messages.append(llm_response)
            tool_messages = await _run_tool_calls_safely(llm_response.tool_calls, all_tools)
            
            # Step 3: Return tool results to the LLM to generate the final answer.
            messages.extend(tool_messages)
            final_response = await llm_with_tools.ainvoke(messages)
            result = final_response.content if hasattr(final_response, 'content') else str(final_response)
        else:
            # No tool call; use the LLM output directly.
            logger.info("LLM did not call tools; returning result directly")
            result = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        if not str(result).strip():
            result = "This step produced no valid output; mark this step as insufficient evidence in later analysis."

        logger.info(f"Step execution completed, result length: {len(result)}")

        # Return updates: remove executed step and append execution history.
        return {
            "plan": plan[1:],  # Remove the first step.
            "past_steps": [(task, result)],  # Appended with operator.add.
        }

    except BaseException as e:
        error_details = format_exception_chain(e)
        logger.error(f"Step execution failed: {error_details}", exc_info=True)
        return {
            "plan": plan[1:],
            "past_steps": [(task, f"Execution failed: {error_details}")],
        }
