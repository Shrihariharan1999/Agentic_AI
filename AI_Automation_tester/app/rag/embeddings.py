"""
RAG Embeddings
==============
Embeddings convert text into numeric vectors that capture semantic meaning.

WHAT IS AN EMBEDDING?
An embedding model takes any text string and outputs a list of numbers
(a "vector" or "embedding"). The key property is:
  - SIMILAR texts produce SIMILAR vectors (close together in vector space)
  - DIFFERENT texts produce DIFFERENT vectors (far apart in vector space)

Example:
  "Click the login button"    → [0.12, 0.81, 0.34, 0.09, ...]  ← very similar vectors
  "Press the sign-in button"  → [0.11, 0.79, 0.36, 0.08, ...]  ↗
  "The weather is sunny"      → [0.91, 0.02, 0.78, 0.55, ...]  ← very different vector

WHY DO WE USE EMBEDDINGS?
We use embeddings for RAG (Retrieval-Augmented Generation):
1. Store past test cases as embeddings in a vector store
2. When generating new tests for a similar site, embed the site description
3. Find the CLOSEST past test cases in vector space (similar websites)
4. Inject those examples into the LLM prompt for better test generation

This is "learning from history" without retraining the model.
"""

from langchain_openai import OpenAIEmbeddings  # OpenAI-compatible embedding client

from app.config.settings import settings       # Our settings (NVIDIA API key)


def get_embedding_model() -> OpenAIEmbeddings:
    """
    Creates and returns a configured embedding model.

    We use NVIDIA's embedding API which is OpenAI-compatible,
    so we can use LangChain's OpenAIEmbeddings client with a custom base URL.

    EMBEDDING DIMENSIONS:
    The output vector for nvidia/llama-3.2-nv-embedqa-1b-v2 has 2048 dimensions.
    Each dimension is a float32 number. So one embedded text = 2048 numbers.

    Returns:
        OpenAIEmbeddings: Configured to use NVIDIA's embedding endpoint
    """

    return OpenAIEmbeddings(
        # The NVIDIA embedding model
        # "nv-embedqa" = NVIDIA's embedding model optimized for Q&A retrieval
        model="nvidia/llama-3.2-nv-embedqa-1b-v2",

        # Use the same NVIDIA API key as the chat models
        api_key=settings.nvidia_api_key,

        # Override the base URL to point to NVIDIA's OpenAI-compatible API
        # Without this, OpenAIEmbeddings would call OpenAI's servers
        base_url=settings.nvidia_base_url,
    )
