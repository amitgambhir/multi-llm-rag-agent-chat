import json
import logging
from typing import Dict, List

import aiosqlite

from config import settings

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Manages RLHF feedback storage and retrieval.

    Feedback is stored in SQLite and used to adjust retrieval scores:
      combined_score = SIMILARITY_WEIGHT * sim_score
                     + FEEDBACK_WEIGHT * normalized_feedback_score

    net_score ∈ [-1, 1]; normalized to [0, 1] before weighting.
    """

    async def save_response(
        self,
        response_id: str,
        query: str,
        answer: str,
        llm_used: str,
        chunk_ids: List[str],
        complexity_score: float,
        session_id: str,
    ) -> None:
        """Persist a response record so feedback can be linked to its chunks."""
        async with aiosqlite.connect(settings.FEEDBACK_DB_PATH) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO responses
                    (response_id, query, answer, llm_used, chunk_ids, complexity_score, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id,
                    query,
                    answer,
                    llm_used,
                    json.dumps(chunk_ids),
                    complexity_score,
                    session_id,
                ),
            )
            await db.commit()

    async def record_feedback(
        self,
        response_id: str,
        rating: int,
        query: str,
        chunk_ids: List[str],
    ) -> None:
        """
        Persist a feedback event and update per-chunk scores.
        rating: +1 = thumbs up, -1 = thumbs down
        """
        async with aiosqlite.connect(settings.FEEDBACK_DB_PATH) as db:
            # Log the raw event
            await db.execute(
                """
                INSERT INTO feedback_events (response_id, rating, query, chunk_ids)
                VALUES (?, ?, ?, ?)
                """,
                (response_id, rating, query, json.dumps(chunk_ids)),
            )

            # Update per-chunk aggregates
            for chunk_id in chunk_ids:
                if rating == 1:
                    await db.execute(
                        """
                        INSERT INTO chunk_feedback (chunk_id, positive_count, negative_count)
                        VALUES (?, 1, 0)
                        ON CONFLICT(chunk_id) DO UPDATE SET
                            positive_count = positive_count + 1,
                            net_score = CAST(positive_count + 1 - negative_count AS REAL)
                                      / (positive_count + 1 + negative_count + 1),
                            last_updated = CURRENT_TIMESTAMP
                        """,
                        (chunk_id,),
                    )
                else:
                    await db.execute(
                        """
                        INSERT INTO chunk_feedback (chunk_id, positive_count, negative_count)
                        VALUES (?, 0, 1)
                        ON CONFLICT(chunk_id) DO UPDATE SET
                            negative_count = negative_count + 1,
                            net_score = CAST(positive_count - negative_count - 1 AS REAL)
                                      / (positive_count + negative_count + 1 + 1),
                            last_updated = CURRENT_TIMESTAMP
                        """,
                        (chunk_id,),
                    )

            await db.commit()
        logger.info(
            f"Recorded feedback (rating={rating}) for {len(chunk_ids)} chunks "
            f"via response '{response_id}'."
        )

    async def get_chunk_scores(self, chunk_ids: List[str]) -> Dict[str, float]:
        """
        Return net_score ∈ [-1, 1] for each chunk_id.
        Chunks with no feedback default to 0.0 (neutral).
        """
        if not chunk_ids:
            return {}

        placeholders = ",".join("?" * len(chunk_ids))
        async with aiosqlite.connect(settings.FEEDBACK_DB_PATH) as db:
            async with db.execute(
                f"SELECT chunk_id, net_score FROM chunk_feedback WHERE chunk_id IN ({placeholders})",
                chunk_ids,
            ) as cursor:
                rows = await cursor.fetchall()

        scores = {row[0]: row[1] for row in rows}
        # Fill missing with neutral score
        for cid in chunk_ids:
            scores.setdefault(cid, 0.0)
        return scores


feedback_service = FeedbackService()
