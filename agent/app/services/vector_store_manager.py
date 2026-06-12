"""Vector store manager that wraps Milvus VectorStore operations"""

from typing import List

from langchain_core.documents import Document
from langchain_milvus import Milvus
from loguru import logger

from app.config import config
from app.core.milvus_client import milvus_manager
from app.services.vector_embedding_service import vector_embedding_service


# Use the biz collection consistently
COLLECTION_NAME = "biz"


class VectorStoreManager:
    """Vector store manager"""

    def __init__(self):
        """Initialize vector store manager"""
        self.vector_store = None
        self.collection_name = COLLECTION_NAME

    def _initialize_vector_store(self):
        """Initialize Milvus VectorStore"""
        if self.vector_store is not None:
            return self.vector_store

        try:
            # A connection must be established before PyMilvus/langchain_milvus accesses Collection,
            # otherwise ConnectionNotExistException: should create connection first can occur.
            # (This runs during module import, before milvus_manager.connect in the FastAPI lifespan.)
            _ = milvus_manager.connect()

            connection_args = {
                "uri": f"http://{config.milvus_host}:{config.milvus_port}",
            }

            # Create LangChain Milvus VectorStore
            # Use the biz collection with field mapping: text_field -> content, vector_field -> vector
            self.vector_store = Milvus(
                embedding_function=vector_embedding_service,
                collection_name=self.collection_name,
                connection_args=connection_args,
                auto_id=False,  # Use custom IDs
                drop_old=False,
                text_field="content",  # Store text content in the content field
                vector_field="vector",  # Store vectors in the vector field
                primary_field="id",  # Primary key field
                metadata_field="metadata",  # Metadata field
            )

            logger.info(
                f"VectorStore initialized successfully: {config.milvus_host}:{config.milvus_port}, "
                f"collection: {self.collection_name}"
            )
            return self.vector_store

        except Exception as e:
            logger.error(f"VectorStore initialization failed: {e}")
            raise

    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        Add documents to the vector store in batch with automatic batch embedding

        Args:
            documents: Document list

        Returns:
            List[str]: Document ID list
        """
        try:
            vector_store = self.get_vector_store()
            import time
            import uuid
            start_time = time.time()

            # Generate a unique ID for each document because auto_id=False
            ids = [str(uuid.uuid4()) for _ in documents]

            # LangChain Milvus add_documents automatically calls embedding_function
            # and processes in batches for better performance
            result_ids = vector_store.add_documents(documents, ids=ids)

            elapsed = time.time() - start_time
            logger.info(
                f"Batch added {len(documents)} documents to VectorStore, "
                f"elapsed: {elapsed:.2f}s, average: {elapsed/len(documents):.2f}s/item"
            )
            return result_ids
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def delete_by_source(self, file_path: str) -> int:
        """
        Delete all documents for the specified file

        Args:
            file_path: File path

        Returns:
            int: Number of deleted documents
        """
        try:
            # Use milvus_manager to get the connected collection
            collection = milvus_manager.get_collection()
            
            # metadata is a JSON field; use JSON path query syntax
            # _source is the source file path of the document
            expr = f'metadata["_source"] == "{file_path}"'
            
            result = collection.delete(expr)
            deleted_count = result.delete_count if hasattr(result, "delete_count") else 0
            
            logger.info(f"Deleted old file data: {file_path}, deleted count: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.warning(f"Failed to delete old data, possibly first indexing: {e}")
            return 0

    def get_vector_store(self) -> Milvus:
        """
        Get VectorStore instance

        Returns:
            Milvus: VectorStore instance
        """
        if self.vector_store is None:
            self._initialize_vector_store()
        return self.vector_store

    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """
        Similarity search

        Args:
            query: Query text
            k: Number of results to return

        Returns:
            List[Document]: Relevant document list
        """
        try:
            vector_store = self.get_vector_store()
            docs = vector_store.similarity_search(query, k=k)
            logger.debug(f"Similarity search completed: query='{query}', result count={len(docs)}")
            return docs
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []


# Global singleton
vector_store_manager = VectorStoreManager()
