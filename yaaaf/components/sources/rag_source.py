import hashlib
import os
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

    def add_pdf(self, pdf_content: bytes, filename: str = "uploaded.pdf"):
        """Add PDF content by extracting text page by page."""
        if not PDF_SUPPORT:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")
        
        try:
            # Create a temporary file-like object from bytes
            from io import BytesIO
            pdf_stream = BytesIO(pdf_content)
            
            # Read PDF and extract text page by page
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():  # Only add non-empty pages
                    # Create unique identifier for each page
                    page_identifier = f"{filename}_page_{page_num}"
                    page_content = f"[Page {page_num} of {filename}]\n{page_text}"
                    
                    # Add page content as separate chunk
                    node_id: str = hashlib.sha256(page_content.encode("utf-8")).hexdigest()
                    self._vector_db.add_text_and_index(page_content, node_id)
                    self._id_to_chunk[node_id] = page_content
                    
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
