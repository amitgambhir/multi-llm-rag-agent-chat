import hashlib
import logging
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Adaptive chunking parameters keyed by source type
CHUNK_PARAMS = {
    "pdf": {
        "chunk_size": 1000,
        "chunk_overlap": 150,
        "semantic_threshold": 85,  # percentile
    },
    "word": {
        "chunk_size": 800,
        "chunk_overlap": 100,
        "semantic_threshold": 80,
    },
    "url": {
        "chunk_size": 500,
        "chunk_overlap": 75,
        "semantic_threshold": 75,
    },
    "default": {
        "chunk_size": 800,
        "chunk_overlap": 120,
        "semantic_threshold": 80,
    },
}


def _generate_chunk_id(chunk: Document) -> str:
    """Generate a stable, deterministic ID for a chunk based on its content and source."""
    source = chunk.metadata.get("source", chunk.metadata.get("file_name", "unknown"))
    content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()[:12]
    return f"{source}__{content_hash}"


class ChunkingService:
    """
    Semantic + adaptive chunking pipeline.

    Strategy:
    1. Try SemanticChunker (requires embeddings) for true semantic splitting.
    2. If semantic chunking produces oversized chunks, apply a secondary
       RecursiveCharacterTextSplitter pass.
    3. Fall back entirely to RecursiveCharacterTextSplitter on any error.
    """

    def __init__(self, embeddings):
        self._embeddings = embeddings

    def chunk_documents(
        self, documents: List[Document], source_type: str
    ) -> List[Document]:
        params = CHUNK_PARAMS.get(source_type, CHUNK_PARAMS["default"])
        chunks = self._semantic_chunk(documents, params)
        chunks = self._assign_chunk_ids(chunks)
        logger.info(
            f"Chunked {len(documents)} document(s) → {len(chunks)} chunks "
            f"(source_type={source_type})"
        )
        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _semantic_chunk(self, documents: List[Document], params: dict) -> List[Document]:
        """
        Attempt semantic chunking, with adaptive breakpoint threshold.
        Falls back to recursive splitter on failure.
        """
        try:
            # Import here so the service still works if langchain_experimental
            # is not installed (falls through to fallback).
            from langchain_experimental.text_splitter import SemanticChunker

            semantic_splitter = SemanticChunker(
                self._embeddings,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=params["semantic_threshold"],
            )
            chunks = semantic_splitter.split_documents(documents)

            # Secondary pass: ensure no chunk exceeds 2x the target size.
            max_allowed = params["chunk_size"] * 2
            oversized = any(len(c.page_content) > max_allowed for c in chunks)
            if oversized:
                chunks = self._recursive_split(
                    chunks, params["chunk_size"], params["chunk_overlap"]
                )

            return chunks

        except Exception as exc:
            logger.warning(
                f"Semantic chunking failed ({exc}); falling back to "
                "RecursiveCharacterTextSplitter."
            )
            return self._recursive_split(
                documents, params["chunk_size"], params["chunk_overlap"]
            )

    @staticmethod
    def _recursive_split(
        documents: List[Document], chunk_size: int, chunk_overlap: int
    ) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_documents(documents)

    @staticmethod
    def _assign_chunk_ids(chunks: List[Document]) -> List[Document]:
        """Inject a stable chunk_id into each chunk's metadata."""
        for chunk in chunks:
            chunk.metadata["chunk_id"] = _generate_chunk_id(chunk)
        return chunks
