import logging

from fastapi import APIRouter, HTTPException

from models.schemas import FeedbackRequest, FeedbackResponse
from services.feedback_service import feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest):
    """
    Accept thumbs-up (+1) or thumbs-down (-1) feedback for a response.
    Updates per-chunk RLHF scores used in future retrievals.
    """
    if payload.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 (up) or -1 (down).")

    if not payload.chunk_ids:
        raise HTTPException(status_code=400, detail="chunk_ids cannot be empty.")

    await feedback_service.record_feedback(
        response_id=payload.response_id,
        rating=int(payload.rating),
        query=payload.query,
        chunk_ids=payload.chunk_ids,
    )

    action = "recorded. Relevant documents boosted." if payload.rating == 1 \
        else "recorded. Relevant documents down-ranked."

    return FeedbackResponse(success=True, message=f"Feedback {action}")
