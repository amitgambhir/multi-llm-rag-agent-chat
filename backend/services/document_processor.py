import os
import tempfile
import logging
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    WebBaseLoader,
)

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles loading of PDF, Word, and web page documents."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}

    def load_pdf(self, file_path: str) -> Tuple[List[Document], str]:
        """Load a PDF file and return documents with source type."""
        logger.info(f"Loading PDF: {file_path}")
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        for doc in documents:
            doc.metadata["source_type"] = "pdf"
            doc.metadata["file_name"] = os.path.basename(file_path)
        return documents, "pdf"

    def load_word(self, file_path: str) -> Tuple[List[Document], str]:
        """Load a Word document and return documents with source type."""
        logger.info(f"Loading Word document: {file_path}")
        loader = Docx2txtLoader(file_path)
        documents = loader.load()
        for doc in documents:
            doc.metadata["source_type"] = "word"
            doc.metadata["file_name"] = os.path.basename(file_path)
        return documents, "word"

    def load_url(self, url: str) -> Tuple[List[Document], str]:
        """Load a web page by URL and return documents with source type."""
        logger.info(f"Loading URL: {url}")
        loader = WebBaseLoader(
            web_paths=[url],
            bs_kwargs={"features": "html.parser"},
        )
        documents = loader.load()
        for doc in documents:
            doc.metadata["source_type"] = "url"
            doc.metadata["source"] = url
        return documents, "url"

    def load_file(self, file_bytes: bytes, filename: str) -> Tuple[List[Document], str]:
        """
        Save uploaded file bytes to a temp file and load it.
        Returns (documents, source_type).
        """
        ext = os.path.splitext(filename)[1].lower()

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            if ext == ".pdf":
                return self.load_pdf(tmp_path)
            elif ext in (".docx", ".doc"):
                return self.load_word(tmp_path)
        finally:
            os.unlink(tmp_path)

        raise ValueError(f"Unhandled extension: {ext}")


document_processor = DocumentProcessor()
