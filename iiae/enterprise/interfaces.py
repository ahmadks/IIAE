"""
Enterprise Integration Interfaces

Protocol definitions for RAG backends and LLM implementations.
"""

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class RAGBackend(Protocol):
    """
    Protocol for RAG (Retrieval Augmented Generation) backends.

    Any RAG system (Pinecone, Weaviate, Elasticsearch, etc.) can implement this.
    """

    def retrieve(self, query: str) -> str:
        """
        Retrieve context/documents for the given query.

        Args:
            query: User query or question

        Returns:
            Retrieved context as string
        """
        ...


@runtime_checkable
class LLMBackend(Protocol):
    """
    Protocol for LLM (Large Language Model) backends.

    Any LLM (OpenAI, Azure, Claude, Gemini, Bedrock, etc.) can implement this.
    """

    def generate(self, prompt: str, context: str) -> str:
        """
        Generate response for prompt using context.

        Args:
            prompt: User question/instruction
            context: Retrieved context from RAG

        Returns:
            Generated response as string
        """
        ...
