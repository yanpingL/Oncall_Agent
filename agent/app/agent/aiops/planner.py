
"""
Planner node: create an execution plan.
Implemented based on the official LangGraph tutorial.
"""

import re
from textwrap import dedent
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS, retrieve_knowledge
from app.agent.mcp_client import get_mcp_client_with_retry
from .state import PlanExecuteState
from .utils import format_tools_description


class Plan(BaseModel):
    """Planner output format."""
    """
    Defines a field named [steps], its type is a list of strings. Eg. valid value:
    Plan(steps=[
        "Check Prometheus alerts",
        "Analyze abnormal metrics",
        "Provide remediation recommendations"
    ])

    Field() mean: Pydantic helper used to add extra information or rules to a model field. Only a metadata
    for the steps, not part of the steps.
    """
    steps: List[str] = Field(
        description="The ordered steps required to complete the task. Each step should build on the previous one."
    )


def _normalize_plan_steps(plan_steps: List[str]) -> List[str]:
    """Split a single multi-step blob into individual numbered steps when needed."""
    split_steps: List[str] = []
    for raw_step in plan_steps:
        if not isinstance(raw_step, str):
            continue
        step = raw_step.strip()
        if not step or step.startswith("description_used_by_reasoning"):
            continue

        markers = list(re.finditer(r"(?m)(?=^\s*(?:Step|Step)\s*\d+\s*[::])", step))
        if len(markers) <= 1:
            split_steps.append(step)
            continue

        for index, marker in enumerate(markers):
            start = marker.start()
            end = markers[index + 1].start() if index + 1 < len(markers) else len(step)
            part = step[start:end].strip()
            if part:
                split_steps.append(part)

    return split_steps


# Planner prompt.
planner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent("""
                You are an expert planner. Break complex tasks into executable steps.

                Available tools, for planning reference:

                {tools_description}

                Note: your responsibility is to create the plan. The Executor performs the actual tool calls.

                {experience_context}

                For the given task, create a simple step-by-step plan. The plan should:
                - Break the task into logically independent steps
                - Clearly state which tools each step should use, if tools are needed, and preferably include the parameters needed by those tools
                - Preserve clear dependencies between steps
                - Make every step specific and actionable
                - **If relevant experience documents are available, use their methods and steps as planning references**

                Example input: "Analyze the current system performance issue"
                Example output, assuming matching tools exist:
                Step 1: Use the get_metrics tool to collect CPU and memory usage
                Step 2: Use the query_logs tool to inspect recent error logs
                Step 3: Use the query_database tool to analyze slow query logs
                Step 4: Combine the information above into a performance analysis report
            """).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)


async def planner(state: PlanExecuteState) -> Dict[str, Any]:
    """
    Planner node: generate an execution plan from user input.

    Flow:
    1. Query internal documents for relevant experience and best practices.
    2. Create an execution plan based on experience documents and available tools.
    """
    logger.info("=== Planner: creating execution plan ===")

    input_text = state.get("input", "")
    logger.info(f"User input: {input_text}")

    try:
        # Step 1: Query internal documents for relevant experience.
        logger.info("Querying internal documents for relevant experience...")
        experience_docs = ""
        try:
            # retrieve_knowledge uses response_format="content_and_artifact".
            # ainvoke() returns only content as a string, not a tuple.
            context_str = await retrieve_knowledge.ainvoke({"query": input_text})
            if context_str and context_str.strip():
                experience_docs = context_str
                logger.info(f"Found relevant experience documents, length: {len(experience_docs)}")
            else:
                logger.info("No relevant experience documents found")
        except Exception as e:
            logger.warning(f"Failed to query internal documents: {e}")

        # Step 2: Get available tools.
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

        # Step 3: Format experience document context.
        """
        [experience_context] is declared inside the [if else] block, but
        as long as every possible branch assigns a value to if, then it's safe to use it outside the block.
        """
        if experience_docs:
            experience_context = dedent(f"""
                ## Relevant Experience Documents

                The following relevant experience and best practices were retrieved from the knowledge base. Use them as references when creating the execution plan:

                {experience_docs}

                ---
            """).strip()
        else:
            experience_context = ""

        # Step 4: Create the LLM and generate the plan.
        llm = llm_factory.create_chat_model(
            model=config.rag_model,
            temperature=0,
            streaming=False,
        )

        # Here the | means "pipe the output of the left side into the right side"
        # llm.with_structured_output(Plan) wraps the LLM so its response is parsed into a Plan object.
        planner_chain = planner_prompt | llm.with_structured_output(Plan)

        # Call the LLM to generate the plan.
        plan_result = await planner_chain.ainvoke({
            "messages": [("user", input_text)],
            "tools_description": tools_description,
            "experience_context": experience_context
        })

        # Extract step list.
        if isinstance(plan_result, Plan):
            plan_steps = plan_result.steps
        else:
            # If a dict is returned, extract the steps field.
            plan_steps = plan_result.get("steps", [])  # type: ignore

        plan_steps = _normalize_plan_steps(plan_steps)

        logger.info(f"Plan generated with {len(plan_steps)} steps")
        # enumerate() is a built-in function that returns a tuple containing a count (from start=1 by default) and the value
        # enumerate(plan_stpes, 1) --> Loop through each step in plan_steps, and start from 1
        for i, step in enumerate(plan_steps, 1):
            logger.info(f"  Step {i}: {step}")

        return {"plan": plan_steps}

    except Exception as e:
        # e: the exception that was caught
        # exc_info=True: tells the logger to include the full traceback to help debug where the error happened
        logger.error(f"Failed to generate plan: {e}", exc_info=True)
        # Return a default plan.
        return {
            "plan": [
                "Collect relevant information",
                "Analyze the data",
                "Generate the report"
            ]
        }
