import hashlib
from typing import List, Dict

from src.components.retrievers.base_retriever import BaseRetriever
from src.components.retrievers.local_vector_db import BM25LocalDB


class LocalRetriever(BaseRetriever):
    def __init__(self):
        self._vector_db = BM25LocalDB()
        self._id_to_chunk: Dict[str, str] = {}

    def add_text(self, text: str):
        node_id: str = hashlib.sha256(text.encode('utf-8')).hexdigest()
        self._vector_db.add_text_and_index(text, node_id)
        self._id_to_chunk[node_id] = text

    def retrieve(self, query: str, topn: int = 10) -> List[str]:
        text_ids_and_thresholds = self._vector_db.get_indices_from_text(query, topn=topn)
        to_return: List[str] = []
        for index in text_ids_and_thresholds[0]:
            to_return.append(self._id_to_chunk[index])
        return to_return