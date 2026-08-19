"""
RAG Vector Store
================
A vector store is a specialized database that stores text ALONGSIDE its embedding vector.
It enables fast semantic similarity search — "find me texts similar to this query."

WHAT IS FAISS?
FAISS (Facebook AI Similarity Search) is a library for efficient similarity search.
It stores vectors in a local index file (no separate server needed).

When you call similarity_search("login button"):
  1. FAISS embeds "login button" → gets a vector
  2. Compares that vector against ALL stored vectors (using math, very fast)
  3. Returns the k stored texts whose vectors are CLOSEST to the query vector

WHY LOCAL FAISS (vs. cloud vector DBs like Pinecone, Weaviate)?
  - Zero setup: no server, no account, no billing
  - Perfect for development and single-machine deployments
  - Data stays private (no cloud transmission)
  - Fast for small-to-medium collections (< 1M documents)

WHAT DO WE STORE IN THE VECTOR STORE?
  - Past test plans (so future runs learn from previous ones)
  - Past self-healing fixes (so the healer knows what worked before)
  - Known element patterns (common login forms, checkout flows, etc.)
"""

import os  # For checking if the index file exists and creating directories

from langchain_community.vectorstores import FAISS  # FAISS vector store implementation
from langchain_core.documents import Document       # LangChain's document wrapper type

from app.config.settings import settings           # For rag_index_path setting
from app.rag.embeddings import get_embedding_model  # Our embedding function


class VectorStore:
    """
    Wraps FAISS to provide a simple interface for adding and searching documents.

    The vector store is LAZY — it only loads (or creates) the FAISS index
    the first time you try to use it. This avoids startup delays.
    """

    def __init__(self):
        # The base directory where the FAISS index files are saved
        # From settings: rag_index_path = "data/vector_store"
        self.index_path = settings.rag_index_path

        # Get the embedding model (used to convert text ↔ vectors)
        self.embeddings = get_embedding_model()

        # The FAISS index — None until first use (lazy loading)
        self._store: FAISS | None = None

    def _load_or_create(self) -> FAISS:
        """
        Returns the FAISS vector store, loading from disk or creating a new one.

        LAZY LOADING PATTERN:
        We check if _store is already loaded. If yes, return immediately.
        If not, try to load from disk. If no disk file, create a fresh index.

        This means the first call to any method is slightly slower
        (loading/creating the index), but subsequent calls are instant.

        Returns:
            An initialized FAISS vector store instance
        """

        # Return the cached store if already loaded
        if self._store is not None:
            return self._store

        # Check if we have a saved FAISS index on disk
        # FAISS saves two files: index.faiss and index.pkl
        if os.path.exists(self.index_path):
            # Load the existing index from disk
            # allow_dangerous_deserialization=True is required because FAISS uses
            # Python's pickle format internally, which has security implications
            # (only load indexes you created yourself — never load untrusted indexes)
            self._store = FAISS.load_local(
                folder_path=self.index_path,          # Where the files are saved
                embeddings=self.embeddings,           # Must use the same embedding model
                allow_dangerous_deserialization=True, # Required for pickle loading
            )

        else:
            # No saved index — create a fresh one
            # FAISS requires at least ONE document to initialize
            # We add a harmless placeholder that won't appear in real searches
            placeholder = Document(
                page_content="Initialization placeholder — ignore this document.",
                metadata={"type": "placeholder", "ignore": True},
            )

            # from_documents() embeds the document and creates the FAISS index
            self._store = FAISS.from_documents(
                documents=[placeholder],
                embedding=self.embeddings,
            )

            # Save immediately so the index persists across restarts
            # Create parent directories if they don't exist
            os.makedirs(
                os.path.dirname(self.index_path) if os.path.dirname(self.index_path) else ".",
                exist_ok=True,  # Don't fail if directory already exists
            )
            self._store.save_local(self.index_path)

        return self._store

    def add_documents(self, documents: list[Document]) -> None:
        """
        Adds new documents to the vector store and saves the updated index.

        Each document is embedded (converted to a vector) and added to the
        FAISS index. After adding, the index is saved to disk.

        Args:
            documents: List of Document objects to add.
                       Each Document has:
                         - page_content: The text to embed and store
                         - metadata: Any additional data (run_id, url, etc.)
        """

        store = self._load_or_create()  # Ensure the store is loaded

        # add_documents() embeds each document and inserts into the FAISS index
        store.add_documents(documents)

        # Persist the updated index to disk
        # (without this, changes are lost when the process exits)
        store.save_local(self.index_path)

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        """
        Finds the k most semantically similar documents to the query text.

        Args:
            query: The text to search for similar documents.
                   e.g. "e-commerce site with login and product catalog"
            k: How many similar documents to return (default: 5)

        Returns:
            List of Documents, sorted by similarity (most similar first).
            Returns empty list if the store has no documents.
        """

        store = self._load_or_create()  # Ensure the store is loaded

        # similarity_search() does:
        # 1. Embeds the query text → query_vector
        # 2. Computes cosine similarity between query_vector and all stored vectors
        # 3. Returns the k documents with highest similarity scores
        return store.similarity_search(query=query, k=k)


# -------------------------------------------------------------------------
# MODULE-LEVEL SINGLETON
# One VectorStore instance shared across the entire application.
# This avoids loading the FAISS index multiple times.
# -------------------------------------------------------------------------
vector_store = VectorStore()
