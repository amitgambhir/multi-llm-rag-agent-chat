import logging
from typing import List

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """
    ChromaDB-backed vector store using HuggingFace embeddings.

    The underlying store can be swapped by replacing this class's
    `_store` with any LangChain VectorStore implementation.
    """

    def __init__(self):
        self._embeddings: HuggingFaceEmbeddings | None = None
        self._store: Chroma | None = None

    # ------------------------------------------------------------------
    # Initialization (lazy, singleton)
    # ------------------------------------------------------------------

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings

    def get_store(self) -> Chroma:
        if self._store is None:
            logger.info(
                f"Connecting to ChromaDB at '{settings.CHROMA_PERSIST_DIR}', "
                f"collection='{settings.CHROMA_COLLECTION_NAME}'"
            )
            self._store = Chroma(
                collection_name=settings.CHROMA_COLLECTION_NAME,
                embedding_function=self._get_embeddings(),
                persist_directory=settings.CHROMA_PERSIST_DIR,
                collection_metadata={"hnsw:space": "cosine"},
            )
        return self._store

    def get_embeddings(self) -> HuggingFaceEmbeddings:
        return self._get_embeddings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_documents(self, chunks: List[Document]) -> List[str]:
        """
        Add chunks to the vector store.
        Uses chunk_id from metadata as the ChromaDB document ID.
        Returns list of stored IDs.
        """
        store = self.get_store()
        ids = [chunk.metadata["chunk_id"] for chunk in chunks]
        store.add_documents(documents=chunks, ids=ids)
        logger.info(f"Added {len(chunks)} chunks to vector store.")
        return ids

    def similarity_search_with_scores(
        self, query: str, k: int
    ) -> list[tuple[Document, float]]:
        """
        Return top-k documents with relevance scores in [0, 1].
        Higher score = more relevant.
        """
        store = self.get_store()
        return store.similarity_search_with_relevance_scores(query, k=k)

    def document_count(self) -> int:
        """Return total number of documents stored."""
        store = self.get_store()
        return store._collection.count()


vector_store_service = VectorStoreService()
