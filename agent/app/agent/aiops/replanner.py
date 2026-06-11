"""
Replanner node: replan or generate the final response.
Implemented based on the official LangGraph tutorial.
"""

from textwrap import dedent
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState
from .utils import format_tools_description


class Response(BaseModel):
    """Final response format."""
    response: str = Field(description="Final response to the user")


class Act(BaseModel):
    """Replanner output format."""
    action: str = Field(
        description="""Next action. Must be one of:
        - 'continue': the current plan is reasonable; continue with the next step
        - 'replan': the current plan needs adjustment; provide a new step list
        - 'respond': the plan is complete and enough information is available; generate the final response"""
    )
    # New step list when action is 'replan'; replaces the current remaining plan.
    new_steps: List[str] = Field(
        default_factory=list,
        description="New step list. If action is 'replan', these steps replace the remaining plan."
    )


# Replanner prompt.
replanner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent("""
                You are a replanning expert. Decide the next action based on completed steps.

                Available tools, for planning reference:

                {tools_description}

                Note: your responsibility is to create or adjust the plan. The Executor performs the actual tool calls.

                You have three choices, listed in priority order:

                **1. 'respond' - enough information is available; generate the final response immediately** [highest priority]
                   - Use case: current information is enough to answer the user
                   - Decision criteria:
                     * At least 3 steps have been executed and key information was obtained
                     * Or at least 5 steps have been executed, regardless of result quality
                     * Or current information fully satisfies the task
                   - Do not wait for "perfect"; respond as soon as the information is good enough

                **2. 'continue' - the current plan is reasonable; continue execution** [second priority]
                   - Use case: the remaining plan is reasonable and necessary
                   - Decision criterion: remaining steps can truly provide key information
                   - If remaining steps are not required, choose respond

                **3. 'replan' - the current plan has serious issues** [lowest priority; use cautiously]
                   - Use case: the original plan is clearly wrong or misses key steps
                   - Strict limits:
                     * The number of new steps must be <= the number of current remaining steps
                     * Prefer simplifying the plan; do not add unnecessary steps
                     * If at least 5 total steps have been executed, replan is forbidden and you must respond

                Evaluation criteria:
                - Is current information enough to solve the user's problem? [most important]
                - Did completed steps successfully obtain core information?
                - Are remaining steps truly required?
                - Have too many steps already been executed (>= 5)? If yes, respond immediately

                Decision priority:
                "Finish first > keep unchanged > adjust the plan"
                "Respond when information is enough; do not chase perfection"
            """).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)

# Final response generation prompt.
response_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent("""
                Generate a comprehensive final response based on the original task and executed step results.

                Response requirements:
                - Clear and structured
                - Based on actual data; do not fabricate
                - If any steps failed, state that honestly
                - Use Markdown format
            """).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)


async def replanner(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Replanner node: decide whether to continue, adjust the plan, or generate the final response.

    Decisions:
    1. continue - continue the current plan
    2. replan - adjust the plan and replace remaining steps
    3. respond - generate the final response
    """
    logger.info("=== Replanner: replanning ===")

    input_text = state.get("input", "")
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    logger.info(f"Remaining plan steps: {len(plan)}")
    logger.info(f"Executed steps: {len(past_steps)}")

    # Hard limit: if too many steps have been executed, generate the response directly.
    MAX_STEPS = 8
    if len(past_steps) >= MAX_STEPS:
        logger.warning(f"Executed {len(past_steps)} steps, exceeding max limit {MAX_STEPS}; forcing final response")
        llm = llm_factory.create_chat_model(
            model=config.rag_model,
            temperature=0,
            streaming=False,
        )
        return await _generate_response(state, llm)

    # Get available tools.
    try:
        # Get local tools.
        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)

        # Get MCP tools.
        mcp_client = await get_mcp_client_with_retry()
        mcp_tools = await mcp_client.get_tools()

        # Combine all tools.
        all_tools = local_tools + mcp_tools
        logger.info(f"Available tools: local {len(local_tools)} + MCP {len(mcp_tools)}")

        # Format tool descriptions.
        tools_description = format_tools_description(all_tools)
    except Exception as e:
        logger.warning(f"Failed to get tool list: {e}")
        tools_description = "Unable to get tool list"

    # Create the LLM.
    llm = llm_factory.create_chat_model(
        model=config.rag_model,
        temperature=0,
        streaming=False,
    )

    # Format executed steps.
    steps_summary = "\n".join([
        f"Step: {step}\nResult: {result[:300]}..."
        for step, result in past_steps
    ])

    # If there are remaining steps, decide the next action.
    if plan:
        logger.info("Remaining plan exists; evaluating next action")

        replanner_chain = replanner_prompt | llm.with_structured_output(Act)

        try:
            messages = [
                ("user", f"Original task: {input_text}"),
                ("user", f"Executed steps:\n{steps_summary}"),
                ("user", f"Remaining plan: {', '.join(plan)}"),
                ("user", f"Important: {len(past_steps)} steps have been executed. First consider whether information is already sufficient to respond.")
            ]

            act = await replanner_chain.ainvoke({
                "messages": messages,
                "tools_description": tools_description
            })

            # Process returned result.
            if isinstance(act, Act):
                action = act.action
                new_steps = act.new_steps
            else:
                # If a dict is returned.
                action = act.get("action", "continue")  # type: ignore
                new_steps = act.get("new_steps", [])  # type: ignore

            logger.info(f"Replanner decision: {action}")

            if action == "respond":
                logger.info("Decided to generate final response")
                return await _generate_response(state, llm)

            elif action == "replan":
                # Hard limit: new step count cannot exceed current remaining step count.
                if len(new_steps) > len(plan):
                    logger.warning(
                        f"New step count {len(new_steps)} > remaining step count {len(plan)}; "
                        f"truncating to {len(plan)} steps"
                    )
                    new_steps = new_steps[:len(plan)]
                
                # Second check: if at least 5 steps have been executed, replan is forbidden.
                if len(past_steps) >= 5:
                    logger.warning(f"Executed {len(past_steps)} steps; replanning is forbidden, forcing response")
                    return await _generate_response(state, llm)
                
                logger.info(f"Decided to adjust plan, new step count: {len(new_steps)}")
                if new_steps:
                    # Replace remaining plan.
                    return {"plan": new_steps}
                else:
                    logger.warning("Replan selected but no new steps provided; continuing original plan")
                    return {}

            else:  # action == "continue"
                logger.info("Decided to continue current plan")
                return {}  # Continue without changing state.

        except Exception as e:
            logger.error(f"Replanning failed: {e}; continuing remaining plan")
            return {}

    else:
        # No remaining plan; generate final response.
        logger.info("Plan fully executed; generating final response")
        return await _generate_response(state, llm)


async def _generate_response(state: PlanExecuteState, llm: Any) -> Dict[str, Any]:
    """Generate the final response."""
    logger.info("Generating final response...")

    input_text = state.get("input", "")
    past_steps = state.get("past_steps", [])

    # Format execution history.
    execution_history = "\n\n".join([
        f"### Step: {step}\n**Result:**\n{result}"
        for step, result in past_steps
    ])
    # This line actually creates a LangChain Runnable chain object.
    # Represents a pipline: format prompt -> call LLM with the prompt-> parse output into Response
    response_gen = response_prompt | llm.with_structured_output(Response)

    try:
        messages = [
            ("user", f"Original task: {input_text}"),
            ("user", f"Execution history:\n{execution_history}"),
            ("user", "Please generate a comprehensive final response based on the information above.")
        ]

        response_obj = await response_gen.ainvoke({"messages": messages})

        # Process returned result.
        if isinstance(response_obj, Response):
            final_response = response_obj.response
        else:
            # If a dict is returned.
            final_response = response_obj.get("response", "")  # type: ignore

        logger.info(f"Final response generated, length: {len(final_response)}")

        return {"response": final_response}

    except Exception as e:
        logger.error(f"Failed to generate response: {e}")
        # Generate a simple fallback response.
        fallback_response = f"""# Task Execution Result

## Original Task
{input_text}

## Executed Steps
{_format_simple_steps(past_steps)}

## Notes
A system error prevented generating a full response. The information above is what has been collected.
"""
        return {"response": fallback_response}


def _format_simple_steps(past_steps: list) -> str:
    """Format a simple step list."""
    if not past_steps:
        return "None"

    formatted = []
    for i, (step, result) in enumerate(past_steps, 1):
        result_preview = result[:200] + "..." if len(result) > 200 else result
        formatted.append(f"{i}. **{step}**\n   {result_preview}\n")

    return "\n".join(formatted)
