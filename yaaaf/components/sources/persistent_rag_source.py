import pickle
import os
import logging
from typing import Dict, List
from yaaaf.components.sources.rag_source import RAGSource

_logger = logging.getLogger(__name__)


class PersistentRAGSource(RAGSource):
    """A RAG source that can persist to disk using pickle."""

    def __init__(self, description: str, source_path: str, pickle_path: str):
        """Initialize persistent RAG source.

        Args:
            description: Description of the source
            source_path: Source path identifier
            pickle_path: Path to pickle file for persistence
        """
        super().__init__(description, source_path)
        self.pickle_path = pickle_path
        self._load_from_pickle()

    def _load_from_pickle(self):
        """Load the RAG source state from pickle file if it exists."""
        if os.path.exists(self.pickle_path):
            try:
                with open(self.pickle_path, "rb") as f:
                    data = pickle.load(f)
                    self._vector_db = data.get("vector_db", self._vector_db)
                    self._id_to_chunk = data.get("id_to_chunk", self._id_to_chunk)
                    _logger.info(
                        f"Loaded persistent RAG source from {self.pickle_path} with {len(self._id_to_chunk)} chunks"
                    )
            except Exception as e:
                _logger.warning(
                    f"Failed to load persistent RAG source from {self.pickle_path}: {e}"
                )
                _logger.info("Starting with empty RAG source")
        else:
            _logger.info(
                f"No existing persistent RAG source found at {self.pickle_path}, starting fresh"
            )

    def _save_to_pickle(self):
        """Save the current RAG source state to pickle file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.pickle_path), exist_ok=True)

            data = {
                "vector_db": self._vector_db,
                "id_to_chunk": self._id_to_chunk,
                "description": self._description,
                "source_path": self.source_path,
            }

            with open(self.pickle_path, "wb") as f:
                pickle.dump(data, f)
            _logger.info(
                f"Saved persistent RAG source to {self.pickle_path} with {len(self._id_to_chunk)} chunks"
            )
        except Exception as e:
            _logger.error(
                f"Failed to save persistent RAG source to {self.pickle_path}: {e}"
            )

    def add_text(self, text: str):
        """Add text and save to pickle."""
        super().add_text(text)
        self._save_to_pickle()

    def add_pdf(
        self,
        pdf_content: bytes,
        filename: str = "uploaded.pdf",
        pages_per_chunk: int = 1,
    ):
        """Add PDF and save to pickle."""
        super().add_pdf(pdf_content, filename, pages_per_chunk)
        self._save_to_pickle()

    def get_document_count(self) -> int:
        """Get the number of documents/chunks in the source."""
        return len(self._id_to_chunk)

    def clear(self):
        """Clear all documents and save."""
        self._vector_db = self.__class__.__bases__[
            0
        ]._vector_db.__class__()  # Reset vector db
        self._id_to_chunk.clear()
        self._save_to_pickle()
        _logger.info(f"Cleared persistent RAG source at {self.pickle_path}")

    def get_all_documents(self) -> List[Dict[str, str]]:
        """Get all documents with their IDs and content."""
        documents = []
        for doc_id, content in self._id_to_chunk.items():
            # Try to extract filename/title from content
            title = "Untitled Document"
            preview = content[:200] + "..." if len(content) > 200 else content

            # Look for filename patterns in content
            if content.startswith("[") and "]" in content:
                bracket_end = content.find("]")
                if bracket_end != -1:
                    title = content[1:bracket_end]

            documents.append(
                {
                    "id": doc_id,
                    "title": title,
                    "content": content,
                    "preview": preview,
                    "size": len(content),
                }
            )

        return documents
