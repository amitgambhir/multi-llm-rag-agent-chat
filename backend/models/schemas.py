from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class IngestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestResponse(BaseModel):
    job_id: str
    status: IngestStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: IngestStatus
    message: str
    chunks_created: Optional[int] = None
    source: Optional[str] = None
    error: Optional[str] = None


class ChatRequest(BaseModel):
    query: str
    session_id: str


class Source(BaseModel):
    content: str
    source: str
    score: float
    chunk_id: str


class ChatResponse(BaseModel):
    response_id: str
    answer: str
    sources: List[Source]
    llm_used: str
    complexity_score: float
    chunk_ids: List[str]
    session_id: str


class FeedbackRating(int, Enum):
    THUMBS_UP = 1
    THUMBS_DOWN = -1


class FeedbackRequest(BaseModel):
    response_id: str
    rating: FeedbackRating
    query: str
    chunk_ids: List[str]


class FeedbackResponse(BaseModel):
    success: bool
    message: str


class ClearHistoryRequest(BaseModel):
    session_id: str


class ClearHistoryResponse(BaseModel):
    success: bool
    message: str
