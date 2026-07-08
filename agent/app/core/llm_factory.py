
"""LLM factory

Supported model providers, by changing only base_url and api_key:
- Alibaba Cloud DashScope: https://dashscope.aliyuncs.com/compatible-mode/v1
- OpenAI: https://api.openai.com/v1
- Azure OpenAI: https://{resource}.openai.azure.com
- Other OpenAI API-compatible services
"""

from langchain_openai import ChatOpenAI
from app.config import config


class LLMFactory:
    """LLM factory - using OpenAI-compatible mode"""

    # Alibaba Cloud DashScope OpenAI-compatible URL
    DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    @staticmethod
    def create_chat_model(
        model: str | None = None,
        temperature: float = 0.7,
        streaming: bool = True,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> ChatOpenAI:

        provider = config.llm_provider.lower()

        if provider == "openai":
            model = model or config.openai_model
            base_url = base_url or config.openai_base_url
            api_key = api_key or config.openai_api_key
            extra_body = None

        else:
            model = model or config.dashscope_model
            base_url = base_url or LLMFactory.DASHSCOPE_BASE_URL
            api_key = api_key or config.dashscope_api_key
            extra_body = {"stream": streaming}

        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
            base_url=base_url,
            api_key=api_key,
            extra_body=extra_body if extra_body else None,
        )

        return llm

# Global LLM factory instance
llm_factory = LLMFactory()
