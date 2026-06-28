
"""Response data models

Define Pydantic models for API responses
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ChatResponse(BaseModel):
    """Chat response"""

    answer: str = Field(..., description="AI answer")
    session_id: str = Field(..., description="Session ID")


class SessionInfoResponse(BaseModel):
    """Session info response"""

    session_id: str = Field(..., description="Session ID")
    message_count: int = Field(..., description="message count")
    history: List[Dict[str, str]] = Field(..., description="Historical message list")


class ApiResponse(BaseModel):
    """Generic API response"""

    status: str = Field(..., description="Status")
    message: str = Field(..., description="Message")
    data: Optional[Any] = Field(None, description="Data")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Version")
