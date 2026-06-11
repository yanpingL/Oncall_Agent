"""Vector embedding service module based on the LangChain Embeddings interface"""

from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI
from loguru import logger

from app.config import config


class DashScopeEmbeddings(Embeddings):
    """Alibaba Cloud DashScope Text Embedding in OpenAI-compatible mode
    
    Implements the standard LangChain Embeddings interface:
    - embed_documents(texts: List[str]) → List[List[float]]: Embed documents in batches
    - embed_query(text: str) → List[float]: Embed a single query
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-v4",
        dimensions: int = 1024,
    ):
        """
        Initialize DashScope Embeddings
        
        Args:
            api_key: DashScope API Key
            model: Embedding model name
            dimensions: Vector dimension
        """
        if not api_key or api_key == "your-api-key-here":
            raise ValueError("Please set the DASHSCOPE_API_KEY environment variable")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = model
        self.dimensions = dimensions
        
        # Print initialization information
        masked_key = self._mask_api_key(api_key)
        logger.info(
            f"DashScope Embeddings initialized - "
            f"model: {model}, dimension: {dimensions}, API Key: {masked_key}"
        )

    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        """Mask API key for logging"""
        if len(api_key) > 8:
            return f"{api_key[:8]}...{api_key[-4:]}"
        return "***"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed documents in batcheslist (LangChain standard interface)
        
        Args:
            texts: Text list
            
        Returns:
            List[List[float]]: Embedding vector list
        """
        if not texts:
            return []
        
        try:
            logger.info(f"Embedding {len(texts)} documents")
            
            # Call API in batch
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
                encoding_format="float"
            )
            
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Batch embedding completed, dimension: {len(embeddings[0])}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            raise RuntimeError(f"Batch embedding failed: {e}") from e

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single querytext (LangChain standard interface)
        
        Args:
            text: Query text
            
        Returns:
            List[float]: embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Query text cannot be empty")
        
        try:
            logger.debug(f"Embedding query, length: {len(text)} characters")
            
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Query embedding completed, dimension: {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise RuntimeError(f"Query embedding failed: {e}") from e


# Global singleton
vector_embedding_service = DashScopeEmbeddings(
    api_key=config.dashscope_api_key,
    model=config.dashscope_embedding_model,
    dimensions=1024
)
