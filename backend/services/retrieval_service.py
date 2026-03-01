import logging
from typing import List, Tuple

from langchain_core.documents import Document

from config import settings
from services.vector_store import vector_store_service
from services.feedback_service import feedback_service

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Retrieves the top-K most relevant chunks using cosine similarity,
    then re-ranks them using stored RLHF feedback scores.

    Final score formula:
        combined = SIMILARITY_WEIGHT * sim_score
                 + FEEDBACK_WEIGHT * normalized_feedback_score

    where normalized_feedback_score = (net_score + 1) / 2  ∈ [0, 1]
    """

    async def retrieve(
        self, query: str
    ) -> List[Tuple[Document, float, str]]:
        """
        Returns up to K (doc, combined_score, chunk_id) tuples, sorted
        by descending combined score.
        """
        k_candidates = settings.RETRIEVAL_CANDIDATES
        k_final = settings.RETRIEVAL_K

        # Step 1: Broad retrieval (2×K candidates)
        candidates = vector_store_service.similarity_search_with_scores(
            query, k=k_candidates
        )
        if not candidates:
            logger.info("No candidates found in vector store.")
            return []

        # Step 2: Collect chunk IDs
        chunk_ids = [
            doc.metadata.get("chunk_id", f"unknown_{i}")
            for i, (doc, _) in enumerate(candidates)
        ]

        # Step 3: Fetch RLHF scores from SQLite
        feedback_scores = await feedback_service.get_chunk_scores(chunk_ids)

        # Step 4: Compute combined score and re-rank
        ranked: List[Tuple[Document, float, str]] = []
        for (doc, sim_score), chunk_id in zip(candidates, chunk_ids):
            net_score = feedback_scores.get(chunk_id, 0.0)
            normalized_feedback = (net_score + 1) / 2  # map [-1,1] → [0,1]
            combined = (
                settings.SIMILARITY_WEIGHT * sim_score
                + settings.FEEDBACK_WEIGHT * normalized_feedback
            )
            ranked.append((doc, combined, chunk_id))

        ranked.sort(key=lambda x: x[1], reverse=True)
        top_k = ranked[:k_final]

        logger.info(
            f"Retrieved {len(top_k)} chunks for query (top sim={top_k[0][1]:.3f})"
            if top_k
            else "Retrieved 0 chunks."
        )
        return top_k


retrieval_service = RetrievalService()
