"""Request data models

Define Pydantic models for API requests
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request"""

    id: str = Field(..., description="Session ID", alias="Id")
    question: str = Field(..., description="User question", alias="Question")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "Id": "session-123",
                "Question": "What is a vector database?"
            }
        }


class ClearRequest(BaseModel):
    """Clear session request"""

    session_id: str = Field(..., description="Session ID", alias="sessionId")

    class Config:
        populate_by_name = True
