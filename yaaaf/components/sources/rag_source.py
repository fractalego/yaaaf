import hashlib
from typing import List, Dict

from yaaaf.components.retrievers.local_vector_db import BM25LocalDB
from yaaaf.components.sources.base_source import BaseSource

try:
    import PyPDF2

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class RAGSource(BaseSource):
    def __init__(self, description: str, source_path: str):
        self._vector_db = BM25LocalDB()
        self._id_to_chunk: Dict[str, str] = {}
        self._description = description
        self.source_path = source_path

    def add_text(self, text: str):
        node_id: str = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self._vector_db.add_text_and_index(text, node_id)
        self._id_to_chunk[node_id] = text

    def add_pdf(
        self,
        pdf_content: bytes,
        filename: str = "uploaded.pdf",
        pages_per_chunk: int = 1,
    ):
        """Add PDF content by extracting text with configurable chunking.

        Args:
            pdf_content: PDF file content as bytes
            filename: Name of the PDF file
            pages_per_chunk: Number of pages per chunk. -1 means all pages in one chunk.
        """
        if not PDF_SUPPORT:
            raise ImportError(
                "PyPDF2 is required for PDF processing. Install with: pip install PyPDF2"
            )

        try:
            # Create a temporary file-like object from bytes
            from io import BytesIO

            pdf_stream = BytesIO(pdf_content)

            # Read PDF and extract text from all pages
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            pages_text = []

            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():  # Only include non-empty pages
                    pages_text.append((page_num, page_text))

            if not pages_text:
                return  # No content to add

            if pages_per_chunk == -1:
                # All pages in one chunk
                all_text_parts = []
                page_numbers = []
                for page_num, page_text in pages_text:
                    all_text_parts.append(f"[Page {page_num}]\n{page_text}")
                    page_numbers.append(str(page_num))

                combined_content = (
                    f"[{filename} - Pages {page_numbers[0]}-{page_numbers[-1]}]"
                    + "\n\n".join(all_text_parts)
                )

                # Add as single chunk
                node_id: str = hashlib.sha256(
                    combined_content.encode("utf-8")
                ).hexdigest()
                self._vector_db.add_text_and_index(combined_content, node_id)
                self._id_to_chunk[node_id] = combined_content

            else:
                # Group pages into chunks
                for chunk_start in range(0, len(pages_text), pages_per_chunk):
                    chunk_pages = pages_text[
                        chunk_start : chunk_start + pages_per_chunk
                    ]

                    chunk_text_parts = []
                    page_numbers = []
                    for page_num, page_text in chunk_pages:
                        chunk_text_parts.append(f"[Page {page_num}]\n{page_text}")
                        page_numbers.append(str(page_num))

                    # Create chunk identifier
                    if len(page_numbers) == 1:
                        chunk_identifier = f"[{filename} - Page {page_numbers[0]}]"
                    else:
                        chunk_identifier = (
                            f"[{filename} - Pages {page_numbers[0]}-{page_numbers[-1]}]"
                        )

                    chunk_content = f"{chunk_identifier}\n\n" + "\n\n".join(
                        chunk_text_parts
                    )

                    # Add chunk
                    node_id: str = hashlib.sha256(
                        chunk_content.encode("utf-8")
                    ).hexdigest()
                    self._vector_db.add_text_and_index(chunk_content, node_id)
                    self._id_to_chunk[node_id] = chunk_content

        except Exception as e:
            raise Exception(f"Error processing PDF {filename}: {str(e)}")

    def get_data(self, query: str, topn: int = 10) -> List[str]:
        text_ids_and_thresholds = self._vector_db.get_indices_from_text(
            query, topn=topn
        )
        to_return: List[str] = []
        for index in text_ids_and_thresholds[0]:
            to_return.append(self._id_to_chunk[index])
        return to_return

    def get_description(self) -> str:
        self._vector_db.build()
        return self._description

    def get_document_count(self) -> int:
        """Get the number of documents/chunks in the source."""
        return len(self._id_to_chunk)
