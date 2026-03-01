import uuid
import logging
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel

from config import settings
from models.schemas import IngestResponse, JobStatusResponse, IngestStatus
from services.document_processor import document_processor
from services.chunking_service import ChunkingService
from services.vector_store import vector_store_service

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)

# In-memory job store (resets on restart; acceptable for single-instance Docker)
_jobs: Dict[str, Dict[str, Any]] = {}


class URLIngestRequest(BaseModel):
    url: str


def _get_chunking_service() -> ChunkingService:
    return ChunkingService(embeddings=vector_store_service.get_embeddings())


# ---------------------------------------------------------------------------
# Background ingestion tasks
# ---------------------------------------------------------------------------


async def _ingest_file_task(job_id: str, file_bytes: bytes, filename: str):
    _jobs[job_id]["status"] = IngestStatus.PROCESSING
    _jobs[job_id]["message"] = "Loading and parsing document..."

    try:
        documents, source_type = document_processor.load_file(file_bytes, filename)
        _jobs[job_id]["message"] = "Chunking document..."

        chunker = _get_chunking_service()
        chunks = chunker.chunk_documents(documents, source_type)
        _jobs[job_id]["message"] = "Embedding and storing chunks..."

        ids = vector_store_service.add_documents(chunks)

        _jobs[job_id].update(
            {
                "status": IngestStatus.COMPLETED,
                "message": f"Successfully ingested '{filename}'.",
                "chunks_created": len(ids),
                "source": filename,
            }
        )
        logger.info(f"[job={job_id}] Ingestion complete: {len(ids)} chunks from '{filename}'.")

    except Exception as exc:
        logger.exception(f"[job={job_id}] Ingestion failed: {exc}")
        _jobs[job_id].update(
            {
                "status": IngestStatus.FAILED,
                "message": "Ingestion failed.",
                "error": str(exc),
            }
        )


async def _ingest_url_task(job_id: str, url: str):
    _jobs[job_id]["status"] = IngestStatus.PROCESSING
    _jobs[job_id]["message"] = "Fetching web page..."

    try:
        documents, source_type = document_processor.load_url(url)
        _jobs[job_id]["message"] = "Chunking web content..."

        chunker = _get_chunking_service()
        chunks = chunker.chunk_documents(documents, source_type)
        _jobs[job_id]["message"] = "Embedding and storing chunks..."

        ids = vector_store_service.add_documents(chunks)

        _jobs[job_id].update(
            {
                "status": IngestStatus.COMPLETED,
                "message": f"Successfully ingested URL: {url}",
                "chunks_created": len(ids),
                "source": url,
            }
        )
        logger.info(f"[job={job_id}] Ingestion complete: {len(ids)} chunks from '{url}'.")

    except Exception as exc:
        logger.exception(f"[job={job_id}] URL ingestion failed: {exc}")
        _jobs[job_id].update(
            {
                "status": IngestStatus.FAILED,
                "message": "Ingestion failed.",
                "error": str(exc),
            }
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/document", response_model=IngestResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a PDF or Word document for ingestion into the RAG pipeline."""
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    file_bytes = await file.read()

    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB} MB.",
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": IngestStatus.PENDING,
        "message": "Job queued.",
        "chunks_created": None,
        "source": file.filename,
        "error": None,
    }

    # Read file bytes before handing off to background (stream closes after response)
    background_tasks.add_task(_ingest_file_task, job_id, file_bytes, file.filename)

    return IngestResponse(
        job_id=job_id,
        status=IngestStatus.PENDING,
        message="Job queued. Poll /ingest/status/{job_id} for progress.",
    )


@router.post("/url", response_model=IngestResponse)
async def ingest_url(
    payload: URLIngestRequest,
    background_tasks: BackgroundTasks,
):
    """Provide a URL to scrape and ingest into the RAG pipeline."""
    if not payload.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": IngestStatus.PENDING,
        "message": "Job queued.",
        "chunks_created": None,
        "source": payload.url,
        "error": None,
    }

    background_tasks.add_task(_ingest_url_task, job_id, payload.url)

    return IngestResponse(
        job_id=job_id,
        status=IngestStatus.PENDING,
        message="Job queued. Poll /ingest/status/{job_id} for progress.",
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll ingestion job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        message=job["message"],
        chunks_created=job.get("chunks_created"),
        source=job.get("source"),
        error=job.get("error"),
    )
