from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM API Keys
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # Embedding model (HuggingFace, no API key needed)
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "rag_documents"

    # Retrieval
    RETRIEVAL_K: int = 3
    RETRIEVAL_CANDIDATES: int = 6  # K * 2 for RLHF re-ranking

    # LLM models
    OPENAI_MODEL: str = "gpt-5"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Complexity threshold: >= this → OpenAI, < this → Gemini
    COMPLEXITY_THRESHOLD: float = 0.4

    # RLHF score weights
    SIMILARITY_WEIGHT: float = 0.7
    FEEDBACK_WEIGHT: float = 0.3

    # Feedback DB
    FEEDBACK_DB_PATH: str = "./data/feedback.db"

    # Max upload size (MB)
    MAX_FILE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
