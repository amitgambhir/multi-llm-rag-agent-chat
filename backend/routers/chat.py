import uuid
import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from models.schemas import (
    ChatRequest,
    ChatResponse,
    Source,
    ClearHistoryRequest,
    ClearHistoryResponse,
)
from services.retrieval_service import retrieval_service
from services.llm_gateway import llm_gateway
from services.feedback_service import feedback_service

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# In-memory conversation histories keyed by session_id
_histories: Dict[str, List[Dict]] = {}

_MAX_HISTORY_TURNS = 10  # keep last N human+assistant pairs


def _trim_history(history: List[Dict]) -> List[Dict]:
    """Keep only the most recent N turns."""
    max_msgs = _MAX_HISTORY_TURNS * 2
    return history[-max_msgs:] if len(history) > max_msgs else history


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    """
    Main chat endpoint.
    1. Retrieves relevant chunks (cosine similarity + RLHF re-rank).
    2. Routes to the appropriate LLM based on query complexity.
    3. Returns the answer with sources and metadata.
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    history = _histories.get(payload.session_id, [])

    # Retrieval
    chunks = await retrieval_service.retrieve(payload.query)
    if not chunks:
        logger.info("No relevant chunks found; answering without context.")

    # LLM generation
    answer, llm_used, complexity_score = await llm_gateway.generate(
        query=payload.query,
        chunks=chunks,
        chat_history=history,
    )

    # Build response
    response_id = str(uuid.uuid4())
    chunk_ids = [cid for _, _, cid in chunks]

    sources = [
        Source(
            content=doc.page_content,
            source=doc.metadata.get("source", doc.metadata.get("file_name", "unknown")),
            score=round(score, 4),
            chunk_id=cid,
        )
        for doc, score, cid in chunks
    ]

    # Persist response so feedback can link back to it
    await feedback_service.save_response(
        response_id=response_id,
        query=payload.query,
        answer=answer,
        llm_used=llm_used,
        chunk_ids=chunk_ids,
        complexity_score=complexity_score,
        session_id=payload.session_id,
    )

    # Update conversation history
    history.append({"role": "human", "content": payload.query})
    history.append({"role": "assistant", "content": answer})
    _histories[payload.session_id] = _trim_history(history)

    return ChatResponse(
        response_id=response_id,
        answer=answer,
        sources=sources,
        llm_used=llm_used,
        complexity_score=round(complexity_score, 4),
        chunk_ids=chunk_ids,
        session_id=payload.session_id,
    )


@router.post("/clear", response_model=ClearHistoryResponse)
async def clear_history(payload: ClearHistoryRequest):
    """Clear the conversation history for a given session."""
    if payload.session_id in _histories:
        del _histories[payload.session_id]
        return ClearHistoryResponse(
            success=True, message="Chat history cleared."
        )
    return ClearHistoryResponse(
        success=True, message="No history found for this session."
    )
