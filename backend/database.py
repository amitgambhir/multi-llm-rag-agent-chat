import aiosqlite
import os
from config import settings


async def init_db():
    """Initialize SQLite database with required tables."""
    os.makedirs(os.path.dirname(settings.FEEDBACK_DB_PATH), exist_ok=True)

    async with aiosqlite.connect(settings.FEEDBACK_DB_PATH) as db:
        # Store feedback per chunk
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chunk_feedback (
                chunk_id TEXT PRIMARY KEY,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                net_score REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Store response metadata for linking feedback to chunks
        await db.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                response_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                answer TEXT NOT NULL,
                llm_used TEXT NOT NULL,
                chunk_ids TEXT NOT NULL,
                complexity_score REAL,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Store raw feedback events for audit/analysis
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                query TEXT,
                chunk_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (response_id) REFERENCES responses(response_id)
            )
        """)

        await db.commit()


async def get_db():
    """Get database connection."""
    return aiosqlite.connect(settings.FEEDBACK_DB_PATH)
