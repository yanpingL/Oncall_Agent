
"""Vector search service module"""

from typing import Any, Dict, List

from loguru import logger
from pymilvus import Collection

from app.core.milvus_client import milvus_manager
from app.services.vector_embedding_service import vector_embedding_service


class SearchResult:
    """Search result class"""

    def __init__(
        self,
        id: str,
        content: str,
        score: float,
        metadata: Dict[str, Any],
    ):
        self.id = id
        self.content = content
        self.score = score
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


class VectorSearchService:
    """Vector search service for searching similar vectors in Milvus"""

    def __init__(self):
        """Initialize vector search service"""
        logger.info("Vector search service initialized")

    def search_similar_documents(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """
        Search similar documents

        Args:
            query: Query text
            top_k: Return the top K most similar results

        Returns:
            List[SearchResult]: Search result list

        Raises:
            RuntimeError: Raised when search fails
        """
        try:
            logger.info(f"Starting similar document search, query: {query}, topK: {top_k}")

            # 1. Vectorize query text
            query_vector = vector_embedding_service.embed_query(query)
            logger.debug(f"Query vector generated successfully, dimension: {len(query_vector)}")

            # 2. Get collection
            collection: Collection = milvus_manager.get_collection()

            # 3. Build search parameters
            search_params = {
                "metric_type": "L2",  # Euclidean distance
                "params": {"nprobe": 10},
            }

            # 4. Execute search
            results = collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=["id", "content", "metadata"],
            )

            # 5. Parse search results
            search_results = []
            for hits in results:
                for hit in hits:
                    result = SearchResult(
                        id=hit.entity.get("id"),
                        content=hit.entity.get("content"),
                        score=hit.distance,  # L2 distance; lower is more similar
                        metadata=hit.entity.get("metadata", {}),
                    )
                    search_results.append(result)

            logger.info(f"Search completed, found {len(search_results)} similar documents")
            return search_results

        except Exception as e:
            logger.error(f"Failed to search similar documents: {e}")
            raise RuntimeError(f"Search failed: {e}") from e


# Global singleton
vector_search_service = VectorSearchService()
