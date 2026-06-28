
"""RAG Agent service based on LangGraph."""

from typing import Annotated, Any, AsyncGenerator, Dict, Sequence

from langchain.agents import create_agent
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from loguru import logger
from typing_extensions import TypedDict

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import (
    get_mcp_client_with_retry,
    load_mcp_tools_safe,
    format_exception_chain,
    suggest_mcp_transport,
)

class AgentState(TypedDict):
    """Agent state"""
    messages: Annotated[Sequence[BaseMessage], add_messages]


def trim_messages_middleware(state: AgentState) -> dict[str, Any] | None:
    """
    Trim message history and keep only recent messages to fit the context window

    Strategy:
    - Keep the first system message
    - Keep the latest 6 messages, about 3 turns
    - Do not trim when there are 7 or fewer messages

    Args:
        state: Agent state

    Returns:
        Dictionary containing trimmed messages, or None if no trimming is needed
    """
    # The list of message object obtained from the AgentState object
    messages = state["messages"]

    # No trimming needed when message count is small
    if len(messages) <= 7:
        return None

    # Extract first system message
    first_msg = messages[0]

    # Keep latest 6 messages, ensuring complete turns
    recent_messages = messages[-6:] if len(messages) % 2 == 0 else messages[-7:]

    # Build new message list
    new_messages = [first_msg] + list(recent_messages)

    logger.debug(f"Trimmed message history: {len(messages)} -> {len(new_messages)} items")


    # clear all messages, then replace them with trimmed messages
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *new_messages
        ]
    }


class RagAgentService:
    """RAG Agent service using LangGraph and the unified LLM factory."""

    def __init__(self, streaming: bool = True):
        """Initialize RAG Agent service

        Args:
            streaming: Whether streaming output is enabled, default True
        """
        self.model_name = config.rag_model
        self.streaming = streaming
        self.system_prompt = self._build_system_prompt()


        self.model = llm_factory.create_chat_model(
            model=self.model_name,
            temperature=0.7,
            streaming=streaming,
        )

        # Define base tools using the same default local tools as the AIOps Planner/Executor
        self.tools = list(DEFAULT_LOCAL_AGENT_TOOLS)

        # MCP client, lazily initialized and globally managed
        self.mcp_tools: list = []

        # Use temporary in-process memory to store agent conversation checkpoints.
        self.checkpointer = MemorySaver()

        # Agent initialization, completed in async method
        self.agent = None
        self._agent_initialized = False

        logger.info(
            f"RAG Agent service initialized, model={self.model_name}, streaming={streaming}"
        )

    async def _initialize_agent(self):
        """Asynchronously initialize the Agent including MCP tools"""
        if self._agent_initialized:
            return

        for name, server in config.mcp_servers.items():
            hint = suggest_mcp_transport(
                str(server.get("url", "")),
                str(server.get("transport", "")),
            )
            if hint:
                logger.warning(f"MCP config [{name}]: {hint}")

        mcp_client = await get_mcp_client_with_retry()
        mcp_tools, mcp_err = await load_mcp_tools_safe(mcp_client)
        if mcp_err:
            logger.warning(
                f"Failed to load MCP tools; continuing with local tools only:\n{mcp_err}"
            )
            self.mcp_tools = []
        else:
            self.mcp_tools = mcp_tools
            logger.info(f"Successfully loaded {len(mcp_tools)} MCP tools")

        all_tools = self.tools + self.mcp_tools

        self.agent = create_agent(
            self.model,
            tools=all_tools,
            checkpointer=self.checkpointer,
        )

        self._agent_initialized = True


        if all_tools:
            # If the tool object has a name attribute, use tool name
            # Else convert the whole tool object to a string
            tool_names = [tool.name if hasattr(tool, "name") else str(tool) for tool in all_tools]
            logger.info(f"Available tool list: {', '.join(tool_names)}")

    def _build_system_prompt(self) -> str:
        """
        Build system prompt

        Note: LangChain automatically passes tool information to the LLM,
        so the system prompt does not need to list concrete tools.

        Returns:
            str: system prompt
        """
        # Extract the extra space from each line
        from textwrap import dedent

        return dedent("""
            You are a professional AI assistant that can use multiple tools to help users solve problems.

            Working principles:
            1. Understand user needs and choose appropriate tools to complete the task
            2. Use relevant tools proactively when real-time information or domain knowledge is needed
            3. Provide accurate and professional answers based on tool results
            4. If tools cannot provide enough information, tell the user honestly

            Response requirements:
            - Keep a friendly and professional tone
            - Be concise and highlight key points
            - Stay factual and do not fabricate information
            - Clearly state uncertainty when present

            Use available tools flexibly based on the user question and provide high-quality help.
        """).strip()
        # strip() remove extra blank line from the beginning and the end of the prompt

    async def query(
        self,
        question: str,
        session_id: str,
    ) -> str:
        """
        Handle user questions in non-streaming mode and return a complete answer

        Args:
            question: User question
            session_id: Session ID used as thread_id

        Returns:
            str: Complete answer
        """
        try:
            await self._initialize_agent()

            logger.info(f"[session {session_id}] RAG Agent received non-streaming query: {question}")

            # Build message list with system prompt and user question
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question)
            ]

            # Build Agent input
            agent_input = {"messages": messages}

            # Configure thread_id for session persistence
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }

            result = await self.agent.ainvoke(
                input=agent_input,
                config=config_dict,
            )

            # Extract final answer
            messages_result = result.get("messages", [])
            if messages_result:
                last_message = messages_result[-1]
                answer = last_message.content if hasattr(last_message, 'content') else str(last_message)

                # Log tool calls
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    tool_names = [tc.get("name", "unknown") for tc in last_message.tool_calls]
                    logger.info(f"[session {session_id}] Agent called tools: {tool_names}")

                logger.info(f"[session {session_id}] RAG Agent query completed (non-streaming)")
                return answer

            logger.warning(f"[session {session_id}] Agent returned an empty result")
            return ""

        except Exception as e:
            logger.error(
                f"[session {session_id}] RAG Agent query failed (non-streaming): "
                f"{format_exception_chain(e)}"
            )
            raise

    async def query_stream(
        self,
        question: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Handle user questions in streaming mode and return answer chunks

        Args:
            question: User question
            session_id: Session ID used as thread_id

        Yields:
            Dict[str, Any]: Dictionary containing streaming data
                - type: "content" | "tool_call" | "complete" | "error"
                - data: Concrete content
        """
        try:
            await self._initialize_agent()

            logger.info(f"[session {session_id}] RAG Agent received streaming query: {question}")

            # Build message list with system prompt and user question
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=question)
            ]

            # Build Agent input
            agent_input = {"messages": messages}

            # Configure thread_id for session persistence
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }

            async for token, metadata in self.agent.astream(
                input=agent_input,
                config=config_dict,
                stream_mode="messages",
            ):
                # Gets the LangGraph node name from the metadata. If madata is a dictionary, it tries to read:
                # metadata["langgraph_node"], if that key doesn not exist, uses "unknown"
                # If metadta is not a dictionary, also uses "unknown"
                node_name = metadata.get('langgraph_node', 'unknown') if isinstance(metadata, dict) else 'unknown'
                # Gets the class name of the streamed token
                message_type = type(token).__name__

                # Only handle AI-generated message chunks, ignore other token types, like tool message or human msgs
                if message_type in ("AIMessage", "AIMessageChunk"):

                    # Tries to read token.content_blocks. 
                    # If the token does not have content_blocks, use None.
                    content_blocks = getattr(token, 'content_blocks', None)

                    if content_blocks and isinstance(content_blocks, list):
                        for block in content_blocks:
                            # Only handles blocks that are dictionaries and whose type is "text"
                            if isinstance(block, dict) and block.get('type') == 'text':
                                # Gets the actual text from the block.
                                # If there is no "text" key, use an empty string.
                                text_content = block.get('text', '')
                                if text_content:
                                    yield {
                                        "type": "content",
                                        "data": text_content,
                                        "node": node_name
                                    }

            logger.info(f"[session {session_id}] RAG Agent query completed (streaming)")
            yield {"type": "complete"}

        except Exception as e:
            detail = format_exception_chain(e)
            logger.error(
                f"[session {session_id}] RAG Agent query failed (streaming): {detail}"
            )
            yield {"type": "error", "data": detail}

    def get_session_history(self, session_id: str) -> list:
        """
        Get session history from the MemorySaver checkpointer

        Args:
            session_id: Session ID, i.e. thread_id

        Returns:
            list: Message history list [{"role": "user|assistant", "content": "...", "timestamp": "..."}]
        """
        try:
            # Use checkpointer.get to retrieve the latest checkpoint
            config = {"configurable": {"thread_id": session_id}}
            
            # Get latest checkpoint for this thread
            checkpoint_tuple = self.checkpointer.get(config)
            
            if not checkpoint_tuple:
                logger.info(f"Get session history: {session_id}, message count: 0")
                return []
            
            # checkpoint_tuple may be a named tuple or normal tuple; extract checkpoint safely
            # Usually the first element is checkpoint data
            if hasattr(checkpoint_tuple, 'checkpoint'):
                checkpoint_data = checkpoint_tuple.checkpoint  # type: ignore
            else:
                # If it is a normal tuple, the first element is checkpoint
                checkpoint_data = checkpoint_tuple[0] if checkpoint_tuple else {}
            
            # Extract messages from checkpoint
            messages = checkpoint_data.get("channel_values", {}).get("messages", [])
            
            # Convert to frontend format
            history = []
            for msg in messages:
                # Skip system messages
                if isinstance(msg, SystemMessage):
                    continue
                    
                role = "user" if isinstance(msg, HumanMessage) else "assistant"
                content = msg.content if hasattr(msg, 'content') else str(msg)
                
                # Extract timestamp if present
                timestamp = getattr(msg, 'timestamp', None)
                if timestamp:
                    history.append({
                        "role": role,
                        "content": content,
                        "timestamp": timestamp
                    })
                else:
                    from datetime import datetime
                    history.append({
                        "role": role,
                        "content": content,
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.info(f"Get session history: {session_id}, message count: {len(history)}")
            return history
            
        except Exception as e:
            logger.error(f"Failed to get session history: {session_id}, error: {e}")
            return []

    def clear_session(self, session_id: str) -> bool:
        """
        Clear session history from the MemorySaver checkpointer

        Args:
            session_id: Session ID, i.e. thread_id

        Returns:
            bool: Whether successful
        """
        try:
            # Use checkpointer.delete_thread to delete all checkpoints for this thread
            self.checkpointer.delete_thread(session_id)
            
            logger.info(f"Session history cleared: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session history: {session_id}, error: {e}")
            return False

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up RAG Agent service resources...")
            # MCP client is managed by the global manager and does not need manual cleanup
            logger.info("RAG Agent service resources cleaned up")
        except Exception as e:
            logger.error(f"Failed to clean up resources: {e}")


# Global singleton - enable streaming output
rag_agent_service = RagAgentService(streaming=True)
