"""
RAG Retriever
=============
The Retriever is the interface used by agents to query the Vector Store.

WHY DO WE NEED A RETRIEVER?
Instead of exposing the raw vector database queries directly to the agents, the
retriever provides a simplified semantic search interface. It converts search queries 
(like a website domain, page name, or a test failure scenario) into vectors, retrieves 
the most relevant documents, formats them, and returns them as plain text or structured
objects that the LLMs can easily read.

HOW IT FITS IN THE PIPELINE:
  Planner Agent -> "Find test strategies for an e-commerce catalog page" ->
  [Retriever] -> queries VectorStore -> returns list of matching past test patterns.
"""

from langchain_core.documents import Document       # LangChain's Document class
from app.rag.vector_store import vector_store       # Our FAISS VectorStore singleton


class RAGRetriever:
    """
    Handles retrieval of historical testing data to guide planning and writing.
    
    It searches the local FAISS vector database for past test plans, test cases,
    and self-healing actions that match the current website under test.
    """

    def retrieve_similar_test_plans(self, website_description: str, limit: int = 3) -> str:
        """
        Retrieves similar past test plans based on a description of the website.

        This helps the Planner Agent study how similar websites were tested in
        previous runs (e.g. if we are testing a login form, we retrieve other 
        login forms we have tested before).

        Args:
            website_description: A textual description of the website or current page
            limit: Maximum number of past plans to retrieve (default: 3)

        Returns:
            A formatted text string containing similar past test plan examples.
        """
        # RAG is an optional enhancement; a provider outage must not stop a test run.
        try:
            docs = vector_store.similarity_search(query=website_description, k=limit)
        except Exception as exc:
            print(f"[Warning] Similar-plan retrieval skipped: {exc}")
            return "No similar historical test plans found."
        
        # Filter docs to only look for 'test_plan' metadata type
        test_plans = [doc for doc in docs if doc.metadata.get("type") == "test_plan"]

        if not test_plans:
            return "No similar historical test plans found."

        # Format the retrieved documents into a clean string for the LLM prompt
        formatted_examples = []
        for i, doc in enumerate(test_plans, 1):
            url = doc.metadata.get("url", "Unknown URL")
            content = doc.page_content
            formatted_examples.append(
                f"--- Example {i} (URL: {url}) ---\n"
                f"Website Description: {doc.metadata.get('description', '')}\n"
                f"Test Plan:\n{content}\n"
            )

        return "\n".join(formatted_examples)

    def retrieve_healing_history(self, failure_message: str, limit: int = 2) -> list[dict]:
        """
        Retrieves past self-healing attempts that fixed similar test errors.

        If a selector fails (e.g. "Unable to click #login-btn"), the Self-Healing
        Agent uses this method to see what alternative selector worked in the past.

        Args:
            failure_message: The error/failure message from the test execution
            limit: Maximum number of healing solutions to retrieve

        Returns:
            A list of dictionary objects representing past successful healing cases.
        """
        # RAG is an optional enhancement; a provider outage must not stop healing.
        try:
            docs = vector_store.similarity_search(query=failure_message, k=limit)
        except Exception as exc:
            print(f"[Warning] Healing-history retrieval skipped: {exc}")
            return []
        
        # Filter documents to only include past successful healing events
        healing_history = [doc for doc in docs if doc.metadata.get("type") == "healing" and doc.metadata.get("successful") is True]

        results = []
        for doc in healing_history:
            results.append({
                "original_selector": doc.metadata.get("original_selector", ""),
                "action": doc.metadata.get("action", ""),
                "error": doc.page_content,
                "healed_selector": doc.metadata.get("healed_selector", ""),
                "strategy": doc.metadata.get("strategy", ""),
            })

        return results


# Module singleton
rag_retriever = RAGRetriever()
