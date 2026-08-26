"""Research current or external facts using Serper and Tavily fallbacks."""

import os
from langchain_core.tools import tool
import requests
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import BaseModel, Field

load_dotenv()

MAX_RESULTS = 5
MAX_RETRIES = 1


class ResearchResult(BaseModel):
    status: str = Field(description="VERIFIED, UNVERIFIED, or FAILED.")
    answer: str = Field(description="Concise answer supported by research evidence.")
    evidence: list[str] = Field(default_factory=list, description="Key supporting evidence.")
    sources: list[str] = Field(default_factory=list, description="Relevant source URLs.")
    source_quality: str = Field(description="Quality of the sources used.")


class SerperQuotaExceeded(Exception):
    pass


class BrowserResearchAgent:
    """Research assistant that summarizes only evidence returned by search."""

    def __init__(self):
        """Create the language model used to verify search evidence."""
        self.llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

    def _serper_search(self, query: str) -> list[dict]:
        api_key = os.getenv("SERPER_API_KEY")

        if not api_key:
            raise SerperQuotaExceeded("SERPER_API_KEY is not configured.")

        response = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": MAX_RESULTS},
            timeout=20,
        )

        if response.status_code in {402, 403, 429}:
            print(f"[SERPER] HTTP {response.status_code}: {response.text}")
            raise SerperQuotaExceeded(f"Serper unavailable: HTTP {response.status_code}")

        response.raise_for_status()
        return response.json().get("organic", [])[:MAX_RESULTS]

    def _format_results(self, results: list[dict]) -> str:
        return "\n\n".join(
            f"TITLE: {item.get('title', '')}\n"
            f"URL: {item.get('link', '')}\n"
            f"SNIPPET: {item.get('snippet', '')}"
            for item in results
        )

    async def _tavily_search(self, query: str):
        print("[TOOL] Tavily: searching for external evidence")
        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured.")

        client = MultiServerMCPClient(
            {
                "tavily": {
                    "transport": "stdio",
                    "command": "npx.cmd" if os.name == "nt" else "npx",
                    "args": ["-y", "tavily-mcp@latest"],
                    "env": {**os.environ, "TAVILY_API_KEY": api_key},
                }
            },
            tool_name_prefix=False,
            handle_tool_errors=True,
        )

        async with client.session("tavily") as session:
            tools = await load_mcp_tools(session)
            search_tool = next((tool for tool in tools if tool.name == "tavily_search"), None)

            if search_tool is None:
                raise RuntimeError("tavily_search is unavailable.")

            return await search_tool.ainvoke({
                "query": query,
                "max_results": MAX_RESULTS,
            })

    async def _summarize(self, query: str, evidence: str, provider: str) -> dict:
        prompt = f"""
    You are a strict web-evidence verifier.
    Question: {query}
    Provider: {provider}
    Evidence: {evidence}

    Use only supplied evidence; never use memory or invent facts, URLs, dates, or sources. Treat empty, failed, conflicting, or incomplete evidence as unknown. Prefer official, government, academic, reputable news, then industry sources. Snippets are weaker than primary sources. Return VERIFIED only when clearly supported, UNVERIFIED when evidence exists but is weak, and FAILED when insufficient. Include only URLs present in evidence and keep the answer concise.
"""

        print(f"[LLM] Browser verifier: evaluating {provider} search evidence")
        result = self.llm.with_structured_output(ResearchResult).invoke([
            SystemMessage(content="You are a strict evidence verifier."),
            HumanMessage(content=prompt),
        ])

        return result.model_dump()

    async def research(self, query: str) -> dict:
        """Try Serper first and use Tavily when Serper is unavailable."""
        # Serper is the fast primary provider; Tavily is used when it is
        # unavailable or its evidence cannot be verified.
        for attempt in range(MAX_RETRIES + 1):
            try:
                serper_results = self._serper_search(query)

                if serper_results:
                    print("[BROWSER] Using Serper.")
                    result = await self._summarize(query, self._format_results(serper_results), "Serper")

                    if result["status"] == "VERIFIED":
                        return result

                    if attempt < MAX_RETRIES:
                        print("[BROWSER] Serper evidence insufficient; retrying.")
                        continue

                    print("[BROWSER] Serper evidence insufficient; using Tavily fallback.")

                else:
                    print("[BROWSER] Serper returned no results; using Tavily.")

            except SerperQuotaExceeded as exc:
                print(f"[BROWSER] Serper unavailable: {exc}")
                print("[BROWSER] Using Tavily fallback.")

            except Exception as exc:
                print(f"[BROWSER] Serper error: {exc}")
                if attempt < MAX_RETRIES:
                    continue

            try:
                tavily_result = await self._tavily_search(query)
                print("[BROWSER] Using Tavily.")
                result = await self._summarize(query, str(tavily_result), "Tavily")
                return result
            except Exception as exc:
                print(f"[BROWSER] Tavily failed: {exc}")

        return ResearchResult(
            status="FAILED",
            answer="Web research could not be completed.",
            evidence=[],
            sources=[],
            source_quality="Serper and Tavily were unavailable or insufficient.",
        ).model_dump()


@tool
async def browser_research(query: str) -> str:
    """Research current or external web information and return compact evidence."""
    agent = BrowserResearchAgent()
    result = await agent.research(query)

    return (
        f"Status: {result['status']}\n"
        f"Answer: {result['answer']}\n"
        f"Evidence: {result['evidence']}\n"
        f"Sources: {result['sources']}\n"
        f"Source quality: {result['source_quality']}"
    )