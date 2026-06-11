"""Configuration management module

Use Pydantic Settings for type-safe configuration management
"""

from typing import Dict, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application config"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application config
    app_name: str = "SuperBizAgent"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9900

    # LLM provider
    llm_provider: str = "dashscope"  # dashscope | openai

    # DashScope config
    dashscope_api_key: str = ""  # Default empty string; should be loaded from environment variables in practice
    dashscope_model: str = "qwen-max"
    dashscope_embedding_model: str = "text-embedding-v4"  # v4 supports multiple dimensions, default 1024

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.4-nano"

    # Milvus config
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_timeout: int = 10000  # milliseconds

    # RAG config
    rag_top_k: int = 3
    # Optional override for the current provider default chat model; empty means LLMFactory selects by provider
    rag_model: str = ""

    # Document chunking config
    chunk_max_size: int = 800
    chunk_overlap: int = 100

    # MCP service config (transport: stdio | sse | streamable-http)
    # Tencent Cloud hosted MCP URLs usually contain /sse/ and should use sse; local FastMCP uses streamable-http
    mcp_cls_transport: str = "streamable-http"
    mcp_cls_url: str = "http://localhost:8003/mcp"
    mcp_monitor_transport: str = "streamable-http"
    mcp_monitor_url: str = "http://localhost:8004/mcp"

    # Prometheus
    prometheus_base_url: str = "http://127.0.0.1:9090"
    prometheus_request_timeout: float = 10.0

    @property
    def mcp_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get full MCP server config"""
        return {
            "cls": {
                "transport": self.mcp_cls_transport,
                "url": self.mcp_cls_url,
            },
            "monitor": {
                "transport": self.mcp_monitor_transport,
                "url": self.mcp_monitor_url,
            }
        }

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        """Accept common environment names accidentally supplied as DEBUG."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value


# Global config instance
config = Settings()
