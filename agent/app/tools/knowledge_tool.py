
"""Knowledge retrieval tool for retrieving relevant information from the vector database"""

from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from loguru import logger

from app.config import config
from app.services.vector_store_manager import vector_store_manager


@tool(response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """Retrieve relevant information from the knowledge base to answer questions
    
    Use this tool when the user question involves domain knowledge, document content, or references.
    
    Args:
        query: User question or query
        
    Returns:
        Tuple[str, List[Document]]: (formatted context text and original document list)
    """
    try:
        logger.info(f"Knowledge retrieval tool called: query='{query}'")
        
        # Retrieve relevant documents from vector store
        vector_store = vector_store_manager.get_vector_store()
        retriever = vector_store.as_retriever(
            search_kwargs={"k": config.rag_top_k}
        )
        
        docs = retriever.invoke(query)
        
        if not docs:
            logger.warning("No relevant documents retrieved")
            return "No relevant information found.", []
        
        # Format documents as context
        context = format_docs(docs)
        
        logger.info(f"Retrieved {len(docs)} relevant documents")
        return context, docs
        
    except Exception as e:
        logger.error(f"Knowledge retrieval tool call failed: {e}")
        return f"Error while retrieving knowledge: {str(e)}", []


def format_docs(docs: List[Document]) -> str:
    """
    Format document list as context text
    
    Args:
        docs: Document list
        
    Returns:
        str: Formatted context text
    """
    formatted_parts = []
    
    for i, doc in enumerate(docs, 1):
        # Extract metadata
        metadata = doc.metadata
        source = metadata.get("_file_name", "Unknown source")
        
        # Extract heading information if available
        headers = []
        for key in ["h1", "h2", "h3"]:
            if key in metadata and metadata[key]:
                headers.append(metadata[key])
        
        header_str = " > ".join(headers) if headers else ""
        
        # Build formatted text
        formatted = f"【Reference {i}】"
        if header_str:
            formatted += f"\nTitle: {header_str}"
        formatted += f"\nSource: {source}"
        formatted += f"\nContent:\n{doc.page_content}\n"
        
        formatted_parts.append(formatted)
    
    return "\n".join(formatted_parts)
