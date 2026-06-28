
"""Document-related data models"""

from typing import Optional

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Document chunk model"""

    content: str = Field(..., description="Chunk content")
    start_index: int = Field(..., description="Chunk start position in original document")
    end_index: int = Field(..., description="Chunk end position in original document")
    chunk_index: int = Field(..., description="Chunk index, starting from 0")
    title: Optional[str] = Field(None, description="Section title for the chunk")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "content": "This is a document content snippet...",
                "start_index": 0,
                "end_index": 100,
                "chunk_index": 0,
                "title": "Chapter 1",
            }
        }
