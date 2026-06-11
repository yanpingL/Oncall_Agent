"""
Executor 节点：执行单个步骤
基于 LangGraph 官方教程实现
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
        return "暂无已执行步骤。"

    formatted = []
    for index, (step, result) in enumerate(past_steps, 1):
        result_text = str(result)
        if len(result_text) > 1200:
            result_text = result_text[:1200] + "\n...（结果已截断）"
        formatted.append(f"步骤{index}: {step}\n结果:\n{result_text}")
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
        return _make_tool_message(tool_call, "工具调用失败：缺少工具名称。", status="error")

    tool = tools_by_name.get(tool_name)
    if tool is None:
        return _make_tool_message(
            tool_call,
            f"工具调用失败：工具 {tool_name!r} 不在当前可用工具列表中。",
            status="error",
        )

    if not isinstance(args, dict):
        return _make_tool_message(
            tool_call,
            f"工具调用失败：工具 {tool_name} 的参数必须是对象/dict，实际为 {type(args).__name__}。",
            status="error",
        )

    try:
        logger.info(f"安全执行工具调用: {tool_name}, 参数键: {list(args.keys())}")
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(args)
        else:
            result = tool.invoke(args)
        return _make_tool_message(tool_call, _serialize_tool_result(result))
    except BaseException as e:
        error_details = format_exception_chain(e)
        logger.warning(f"工具 {tool_name} 执行失败，已转换为工具消息: {error_details}")
        return _make_tool_message(
            tool_call,
            f"工具 {tool_name} 执行失败：{error_details}",
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
    执行节点：执行计划中的下一个步骤
    
    使用 LangGraph 的 ToolNode 自动处理工具调用
    """
    logger.info("=== Executor：执行步骤 ===")

    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    # 如果计划为空，不执行
    if not plan:
        logger.info("计划为空，跳过执行")
        return {}

    # 取出第一个步骤
    task = plan[0]
    logger.info(f"当前任务: {task}")

    try:
        # 获取本地工具
        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)

        # 获取 MCP 工具
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()
        logger.info(f"可用工具数量: 本地 {len(local_tools)} + MCP {len(mcp_tools)}")

        # 合并所有工具
        all_tools = local_tools + mcp_tools

        # 创建 LLM（绑定工具）
        llm = llm_factory.create_chat_model(
            model=config.rag_model,
            temperature=0,
            streaming=False,
        )
        llm_with_tools = llm.bind_tools(all_tools)

        # 构建消息（只包含当前步骤，避免原始任务干扰）
        messages = [
            SystemMessage(content="""你是一个能力强大的助手，负责执行具体的任务步骤。

你可以使用各种工具来完成任务。对于每个步骤：
1. 理解步骤的目标
2. 选择合适的工具，如果已经指定了工具，则使用指定的工具
3. 调用工具获取信息
4. 返回执行结果

注意：
- 如果工具调用失败，请说明失败原因
- 不要编造数据，只返回实际获取的信息
- 调用依赖前置结果的工具前，必须先确认已执行步骤中存在必需参数
- 如果没有获得日志证据，请直接说明证据不足
- 执行结果要清晰、准确
- 专注于当前步骤，不要考虑其他任务"""),
            HumanMessage(content=f"已执行步骤和结果:\n{_format_past_steps(past_steps)}"),
            HumanMessage(content=f"请执行以下任务: {task}")
        ]

        # 第一步：LLM 决定是否调用工具
        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"LLM 响应类型: {type(llm_response)}")

        # 第二步：如果有工具调用，执行工具
        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            tool_names = _tool_call_names(llm_response)
            logger.info(f"检测到 {len(llm_response.tool_calls)} 个工具调用: {tool_names}")
            
            # 逐个安全执行工具。不要用 ToolNode 批量执行 MCP 工具，否则单个
            # adapter/parser 异常可能以 TaskGroup 形式逃逸并终止整个图。
            messages.append(llm_response)
            tool_messages = await _run_tool_calls_safely(llm_response.tool_calls, all_tools)
            
            # 第三步：将工具结果返回给 LLM 生成最终答案
            messages.extend(tool_messages)
            final_response = await llm_with_tools.ainvoke(messages)
            result = final_response.content if hasattr(final_response, 'content') else str(final_response)
        else:
            # 没有工具调用，直接使用 LLM 的输出
            logger.info("LLM 未调用工具，直接返回结果")
            result = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        if not str(result).strip():
            result = "本步骤未获得有效输出；请在后续分析中标记该步骤证据不足。"

        logger.info(f"步骤执行完成，结果长度: {len(result)}")

        # 返回更新：移除已执行的步骤，添加执行历史
        return {
            "plan": plan[1:],  # 移除第一个步骤
            "past_steps": [(task, result)],  # 使用 operator.add 追加
        }

    except BaseException as e:
        error_details = format_exception_chain(e)
        logger.error(f"执行步骤失败: {error_details}", exc_info=True)
        return {
            "plan": plan[1:],
            "past_steps": [(task, f"执行失败: {error_details}")],
        }
