import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import ingest, chat, feedback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-LLM RAG Agent",
    description=(
        "A RAG pipeline with semantic chunking, RLHF-based re-ranking, "
        "and intelligent LLM routing (OpenAI ↔ Gemini)."
    ),
    version="1.0.0",
)

# CORS — allow the React frontend (and any origin in dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(feedback.router)


@app.on_event("startup")
async def startup():
    logger.info("Initializing database...")
    os.makedirs("./data", exist_ok=True)
    await init_db()
    logger.info("Database ready.")


@app.get("/health")
async def health():
    return {"status": "ok"}
