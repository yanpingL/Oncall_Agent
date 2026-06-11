"""
Generic Plan-Execute-Replan service.
Implemented based on the official LangGraph tutorial.
"""

from typing import AsyncGenerator, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from app.agent.aiops import PlanExecuteState, planner, executor, replanner
from app.services.vector_index_service import vector_index_service


# Node name constants
NODE_PLANNER = "planner"
NODE_EXECUTOR = "executor"
NODE_REPLANNER = "replanner"


class AIOpsService:
    """Generic Plan-Execute-Replan service."""

    def __init__(self):
        """Initialize the service."""
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()
        logger.info("Plan-Execute-Replan service initialized")

    def _build_graph(self):
        """Build the Plan-Execute-Replan workflow."""
        logger.info("Building workflow graph...")

        # Create the state graph.
        workflow = StateGraph(PlanExecuteState)

        # Add nodes.
        # Adds a node named [NODE_PLANNER], when this node runs, it calls the [planner] function
        workflow.add_node(NODE_PLANNER, planner)      # Create a plan
        workflow.add_node(NODE_EXECUTOR, executor)  # Execute a step
        workflow.add_node(NODE_REPLANNER, replanner)  # Replan

        # The first step of the graph is the planner
        workflow.set_entry_point(NODE_PLANNER)

        # Define edges.
        workflow.add_edge(NODE_PLANNER, NODE_EXECUTOR)     # planner -> executor
        workflow.add_edge(NODE_EXECUTOR, NODE_REPLANNER)   # executor -> replanner

        # Conditional edges from replanner.
        def should_continue(state: PlanExecuteState) -> str:
            """Decide whether execution should continue."""
            # Stop if the final response has already been generated.
            if state.get("response"):
                logger.info("Final response has been generated; ending workflow")
                return END

            # Continue if there are remaining plan steps.
            plan = state.get("plan", [])
            if plan:
                logger.info(f"Continuing execution with {len(plan)} remaining steps")
                return NODE_EXECUTOR

            # No remaining plan and no response: finish the workflow.
            logger.info("Plan execution completed; preparing final response")
            return END

        """
        After [NODE_REPLANNER] call should_continue(state) function:
        If it returns [NODE_EXEUTOR] --> go to executor node
        If it returns END --> end the workflow
        The graph is roughly 
        Planner -> Executor -> Replanner
              ↑          |
              |          |
              +----------+        
        """
        workflow.add_conditional_edges(
            NODE_REPLANNER,
            should_continue,
            {
                NODE_EXECUTOR: NODE_EXECUTOR,
                END: END
            }
        )

        # Compile the workflow.
        compiled_graph = workflow.compile(checkpointer=self.checkpointer)

        logger.info("Workflow graph built")
        return compiled_graph

    async def execute(
        self,
        user_input: str,
        session_id: str = "default"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the Plan-Execute-Replan workflow.

        Args:
            user_input: User task description
            session_id: Session ID

        Yields:
            Dict[str, Any]: Streaming events
        """
        logger.info(f"[session {session_id}] Starting task: {user_input}")

        try:
            # Initialize state.
            initial_state: PlanExecuteState = {
                "input": user_input,
                "plan": [],
                "past_steps": [],
                "response": ""
            }

            # Stream workflow execution.
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }

            async for event in self.graph.astream(
                input=initial_state,
                config=config_dict,
                stream_mode="updates"
            ):
                # Parse events.
                # node_output is the output of the corresponing node function
                for node_name, node_output in event.items():
                    logger.info(f"Node '{node_name}' emitted an event")

                    # Format different events based on node type.
                    if node_name == NODE_PLANNER:
                        yield self._format_planner_event(node_output)

                    elif node_name == NODE_EXECUTOR:
                        yield self._format_executor_event(node_output)

                    elif node_name == NODE_REPLANNER:
                        yield self._format_replanner_event(node_output)

            # Give me the latest saved graph state for this session_id.
            final_state = self.graph.get_state(config_dict)
            final_response = ""

            # Safely get the response because values can be None.
            # fial_state.values contains the actual state fields
            if final_state and final_state.values:
                final_response = final_state.values.get("response", "")

            knowledge_index = self._store_final_report(final_response, session_id)

            # Send completion event.
            yield {
                "type": "complete",
                "stage": "complete",
                "message": "Task execution completed",
                "response": final_response,
            }

            logger.info(f"[session {session_id}] Task execution completed")

        except Exception as e:
            logger.error(f"[session {session_id}] Task execution failed: {e}", exc_info=True)
            yield {
                "type": "error",
                "stage": "error",
                "message": f"Task execution error: {str(e)}"
            }

    async def diagnose(
        self,
        session_id: str = "default"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        AIOps diagnosis interface, compatible with the legacy API.

        Args:
            session_id: Session ID

        Yields:
            Dict[str, Any]: Streaming diagnosis events
        """
        # Use a fixed AIOps task description.
        from textwrap import dedent
        aiops_task = dedent("""Diagnose whether the current system has active alerts. If alerts exist, analyze their causes in detail and generate a diagnosis report using the following Markdown format:
                ```
                # Alert Analysis Report

                ---

                ## Active Alert List

                | Alert Name | Severity | Target Service | First Triggered At | Latest Triggered At | Status |
                |---------|------|----------|-------------|-------------|------|
                | [Alert 1 name] | [Severity] | [Service name] | [Time] | [Time] | Active |
                | [Alert 2 name] | [Severity] | [Service name] | [Time] | [Time] | Active |

                ---

                ## Root Cause Analysis 1 - [Alert Name]

                ### Alert Details
                - **Severity**: [Severity]
                - **Affected Service**: [Service name]
                - **Duration**: [X minutes]

                ### Symptoms
                [Describe symptoms based on monitoring metrics]

                ### Log Evidence
                [Quote key logs retrieved from tools]

                ### Root Cause Conclusion
                [Root cause derived from evidence]

                ---

                ## Remediation Plan 1 - [Alert Name]

                ### Investigation Steps Performed
                1. [Step 1]
                2. [Step 2]

                ### Recommendations
                [Provide concrete remediation recommendations]

                ### Expected Outcome
                [Explain the expected outcome]

                ---

                ## Root Cause Analysis 2 - [Alert Name]
                [If a second alert exists, repeat the same structure]

                ---

                ## Conclusion

                ### Overall Assessment
                [Summarize all alerts]

                ### Key Findings
                - [Finding 1]
                - [Finding 2]

                ### Follow-up Recommendations
                1. [Recommendation 1]
                2. [Recommendation 2]

                ### Risk Assessment
                [Assess current risk level and impact scope]
                ```

                **Important reminders**:
                - The final output must be pure Markdown text and must not contain a JSON structure.
                - All content must be based on real data returned by tools. Do not fabricate facts.
                - If any step fails, state it honestly in the conclusion instead of skipping it.""")

        async for event in self.execute(aiops_task, session_id):
            # Convert event format for the legacy API.
            if event.get("type") == "complete":
                # Wrap response in the diagnosis format.
                yield {
                    "type": "complete",
                    "stage": "diagnosis_complete",
                    "message": "Diagnosis completed",
                    "diagnosis": {
                        "status": "completed",
                        "report": event.get("response", ""),
                    },
                }
            else:
                yield event

    def _store_final_report(self, final_response: str, session_id: str) -> Dict[str, Any]:
        """Save and index the final diagnosis report."""
        if not final_response or not final_response.strip():
            logger.warning(f"[session {session_id}] Final report is empty; skipping knowledge-base write")
            return {
                "success": False,
                "skipped": True,
                "reason": "empty_report",
            }

        try:
            file_path = vector_index_service.index_aiops_report(
                report=final_response,
                session_id=session_id,
            )
            logger.info(f"[session {session_id}] Final diagnosis report written to knowledge base: {file_path}")
            return {
                "success": True,
                "skipped": False,
                "file_path": file_path,
            }
        except Exception as e:
            logger.error(f"[session {session_id}] Failed to write final diagnosis report to knowledge base: {e}", exc_info=True)
            return {
                "success": False,
                "skipped": False,
                "error": str(e),
            }

    def _format_planner_event(self, state: Dict | None) -> Dict:
        """Format a Planner node event."""
        if not state:
            return {
                "type": "status",
                "stage": "planner",
                "message": "Planner node is running"
            }

        plan = state.get("plan", [])

        return {
            "type": "plan",
            "stage": "plan_created",
            "message": f"Execution plan created with {len(plan)} steps",
            "plan": plan
        }

    def _format_executor_event(self, state: Dict | None) -> Dict:
        """Format an Executor node event."""
        if not state:
            return {
                "type": "status",
                "stage": "executor",
                "message": "Executor node is running"
            }

        plan = state.get("plan", [])
        past_steps = state.get("past_steps", [])

        if past_steps:
            """
            Get the most recent executed step
            past_steps[-1]: means the last item in the list
            Each item is expected to be a pair (step, result)
            last_step, _ --> unpacks the last pair
            eg. past_steps[-1] = ('Search the CPU idice', 'CPU usage 90%')
            """
            last_step, _ = past_steps[-1]
            return {
                "type": "step_complete",
                "stage": "step_executed",
                "message": f"Step executed; {len(plan)} steps remaining",
                "current_step": last_step,
                "remaining_steps": len(plan)
            }
        else:
            return {
                "type": "status",
                "stage": "executor",
                "message": "Starting step execution"
            }

    def _format_replanner_event(self, state: Dict | None) -> Dict:
        """Format a Replanner node event."""
        if not state:
            return {
                "type": "status",
                "stage": "replanner",
                "message": "Replanner node is running"
            }

        response = state.get("response", "")
        plan = state.get("plan", [])

        if response:
            # Final response has been generated.
            return {
                "type": "report",
                "stage": "final_report",
                "message": "Final report generated",
                "report": response
            }
        else:
            # Replanning.
            return {
                "type": "status",
                "stage": "replanner",
                "message": f"Evaluation completed; {'continuing remaining steps' if plan else 'preparing final response'}",
                "remaining_steps": len(plan)
            }


# Global shared static instance
aiops_service = AIOpsService()
