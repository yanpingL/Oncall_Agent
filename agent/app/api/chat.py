
"""Chat API

Provides normal and streaming chat APIs based on the RAG Agent
"""

import json
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from app.models.request import ChatRequest, ClearRequest
from app.models.response import SessionInfoResponse, ApiResponse
from app.agent.mcp_client import format_exception_chain
from app.services.rag_agent_service import rag_agent_service
from loguru import logger

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    """Quick chat API
    {
        "code": 200,
        "message": "success",
        "data": {
            "success": true,
            "answer": "answer content",
            "errorMessage": null
        }
    }

    Args:
        request: Chat request

    Returns:
        Unified chat response format
    """
    try:
        logger.info(f"[session {request.id}] received quick chat request: {request.question}")
        answer = await rag_agent_service.query(
            request.question,
            session_id=request.id
        )

        logger.info(f"[session {request.id}] quick chat completed")

        return {
            "code": 200,
            "message": "success",
            "data": {
                "success": True,
                "answer": answer,
                "errorMessage": None
            }
        }

    except Exception as e:
        logger.error(f"Chat APIerror: {e}")
        return {
            "code": 500,
            "message": "error",
            "data": {
                "success": False,
                "answer": None,
                "errorMessage": str(e)
            }
        }


@router.post("/chat_stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat API based on RAG Agent and SSE

    Returns SSE format with the data field as JSON:

    Tool call event:
    event: message
    data: {"type":"tool_call","data":{"tool":"tool name","status":"start|end","input":{...}}}

    Content streaming event:
    event: message
    data: {"type":"content","data":"content chunk"}

    Completion event:
    event: message
    data: {"type":"done","data":{"answer":"Complete answer","tool_calls":[...]}}

    Args:
        request: Chat request

    Returns:
        SSE event stream
    """
    logger.info(f"[session {request.id}] received streaming chat request: {request.question}")

    async def event_generator():
        try:
            async for chunk in rag_agent_service.query_stream(request.question, session_id=request.id):
                chunk_type = chunk.get("type", "unknown")
                chunk_data = chunk.get("data", None)

                # Handle debug message type, newly added
                if chunk_type == "debug":
                    # Debug info can be sent or ignored
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "debug",
                            "node": chunk.get("node", "unknown"),
                            "message_type": chunk.get("message_type", "unknown")
                        }, ensure_ascii=False)
                    }
                elif chunk_type == "tool_call":
                    # Send tool-call event, optional; frontend can show tool-call status
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "tool_call",
                            "data": chunk_data
                        }, ensure_ascii=False)
                    }
                elif chunk_type == "search_results":
                    # Send retrieval results, optional; frontend can ignore
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "search_results",
                            "data": chunk_data
                        }, ensure_ascii=False)
                    }
                elif chunk_type == "content":
                    # Send content chunk; important: data must be a JSON string
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "content",
                            "data": chunk_data
                        }, ensure_ascii=False)
                    }
                elif chunk_type == "complete":
                    # Send completion signal
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "done",
                            "data": chunk_data
                        }, ensure_ascii=False)
                    }
                elif chunk_type == "error":
                    # Send error information
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "error",
                            "data": str(chunk_data)
                        }, ensure_ascii=False)
                    }

            logger.info(f"[session {request.id}] streaming chat completed")

        except Exception as e:
            logger.error(f"streaming chat API error: {format_exception_chain(e)}")
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "data": str(e)
                }, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())


@router.post("/chat/clear", response_model=ApiResponse)
async def clear_session(request: ClearRequest):
    """Clear session history

    Args:
        request: clear request

    Returns:
        operation result
    """
    try:
        success = rag_agent_service.clear_session(request.session_id)
        logger.info(f"Clear session: {request.session_id}, result: {success}")

        return ApiResponse(
            status="success" if success else "error",
            message="Session cleared" if success else "Failed to clear session",
            data=None
        )

    except Exception as e:
        logger.error(f"clear session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/session/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str) -> SessionInfoResponse:
    """Query session history

    Args:
        session_id: Session ID

    Returns:
        session info
    """
    try:
        history = rag_agent_service.get_session_history(session_id)

        return SessionInfoResponse(
            session_id=session_id,
            message_count=len(history),
            history=history
        )

    except Exception as e:
        logger.error(f"get session info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
