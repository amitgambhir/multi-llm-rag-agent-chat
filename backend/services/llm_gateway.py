import logging
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Complexity scoring constants (tweak here without touching logic)
# ---------------------------------------------------------------------------

_HIGH_COMPLEXITY_TERMS = {
    "troubleshoot", "debug", "diagnose", "configure", "implement", "optimize",
    "architecture", "security", "authentication", "performance", "integrate",
    "deploy", "infrastructure", "encryption", "algorithm", "latency",
    "scaling", "microservices", "kubernetes", "docker", "ci/cd", "devops",
    "regression", "bottleneck", "memory leak", "deadlock", "concurrency",
    "thread", "async", "race condition", "vulnerability", "exploit",
}

_MEDIUM_COMPLEXITY_TERMS = {
    "error", "install", "setup", "api", "database", "server", "network",
    "connection", "protocol", "version", "update", "migrate", "backup",
    "restore", "monitor", "log", "trace",
}

_SIMPLE_STARTERS = (
    "what is", "who is", "when is", "where is", "define ", "what are",
    "who are", "list ", "name ", "what does", "what do",
)

_ANALYTICAL_TERMS = {
    "compare", "contrast", "analyze", "evaluate", "assess",
    "difference between", "advantages", "disadvantages", "trade-off",
    "pros and cons", "best practice", "recommend", "which is better",
}

_RAG_SYSTEM_PROMPT = """You are a knowledgeable assistant that answers questions \
based strictly on the provided context.

CONTEXT (retrieved from the knowledge base):
{context}

Instructions:
- Answer ONLY based on the context above.
- If the context does not contain enough information, clearly say so.
- Be concise and accurate.
- Cite the source when relevant."""


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def calculate_complexity(query: str) -> float:
    """
    Return a complexity score in [0.0, 1.0].
    >= settings.COMPLEXITY_THRESHOLD  →  route to OpenAI
    <  settings.COMPLEXITY_THRESHOLD  →  route to Gemini
    """
    score = 0.0
    q = query.lower()
    words = query.split()

    # Length factor (contributes up to 0.20)
    score += min(len(words) / 50.0, 1.0) * 0.20

    # High-complexity keywords (+0.12 each, capped at 0.36)
    high_hits = sum(1 for t in _HIGH_COMPLEXITY_TERMS if t in q)
    score += min(high_hits * 0.12, 0.36)

    # Medium-complexity keywords (+0.06 each, capped at 0.18)
    med_hits = sum(1 for t in _MEDIUM_COMPLEXITY_TERMS if t in q)
    score += min(med_hits * 0.06, 0.18)

    # Simple question starters (–0.20 once)
    if any(q.startswith(s) for s in _SIMPLE_STARTERS):
        score -= 0.20

    # Analytical / comparative language (+0.12 each, capped at 0.24)
    analytical_hits = sum(1 for t in _ANALYTICAL_TERMS if t in q)
    score += min(analytical_hits * 0.12, 0.24)

    # Complex question starters (+0.15)
    if q.startswith(("why", "how to", "how do", "how can", "how does")):
        score += 0.15
    elif q.startswith(("what", "who", "when", "where")):
        score -= 0.05

    # Multiple questions (+0.15 per extra "?")
    extra_questions = max(query.count("?") - 1, 0)
    score += extra_questions * 0.15

    return max(0.0, min(1.0, score))


def _build_llm(complexity_score: float):
    """Instantiate the appropriate LangChain chat model based on complexity."""
    if complexity_score >= settings.COMPLEXITY_THRESHOLD:
        logger.info(
            f"Routing to OpenAI ({settings.OPENAI_MODEL}), complexity={complexity_score:.2f}"
        )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.2,
        ), settings.OPENAI_MODEL

    else:
        logger.info(
            f"Routing to Gemini ({settings.GEMINI_MODEL}), complexity={complexity_score:.2f}"
        )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2,
        ), settings.GEMINI_MODEL


def _format_context(chunks: List[Tuple[Document, float, str]]) -> str:
    """Build a readable context string from retrieved chunks."""
    parts = []
    for i, (doc, score, _) in enumerate(chunks, 1):
        source = doc.metadata.get("source", doc.metadata.get("file_name", "unknown"))
        parts.append(
            f"[{i}] Source: {source} (relevance: {score:.2f})\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)


def _format_history(history: list) -> list:
    """Convert session history dicts to LangChain message objects."""
    messages = []
    for msg in history:
        if msg["role"] == "human":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    return messages


# ---------------------------------------------------------------------------
# LLM Gateway
# ---------------------------------------------------------------------------


class LLMGateway:
    """
    Orchestrates complexity scoring, LLM routing, and RAG response generation.
    """

    async def generate(
        self,
        query: str,
        chunks: List[Tuple[Document, float, str]],
        chat_history: list,
    ) -> Tuple[str, str, float]:
        """
        Generate a response using the appropriate LLM.

        Returns:
            (answer, llm_model_name, complexity_score)
        """
        complexity_score = calculate_complexity(query)
        llm, llm_name = _build_llm(complexity_score)

        context = _format_context(chunks)
        history_messages = _format_history(chat_history)

        prompt = ChatPromptTemplate.from_messages([
            ("system", _RAG_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])

        chain = prompt | llm | StrOutputParser()

        answer = await chain.ainvoke({
            "context": context,
            "chat_history": history_messages,
            "question": query,
        })

        return answer, llm_name, complexity_score


llm_gateway = LLMGateway()
