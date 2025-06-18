import numpy as np

from nltk import download
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from typing import List, Tuple
from rank_bm25 import BM25Okapi

download("stopwords")
download("punkt_tab")


class BM25LocalDB:
    def __init__(self):
        self._indices = []
        self._texts = []
        self._bm25 = None
        self._stopwords = stopwords.words("english")

    def add_text_and_index(self, text: str, index: str):
        self._indices.append(index)
        self._texts.append(word_tokenize(text))

    def get_indices_from_text(
        self, text: str, topn: int
    ) -> Tuple[List[str], List[str]]:
        scores = self._bm25.get_scores(word_tokenize(text))
        best_n = np.argsort(-scores)[:topn]
        return [self._indices[i] for i in best_n], scores[:topn]

    def build(self):
        if self._bm25 is None:
            del self._bm25
        self._bm25 = BM25Okapi(self._texts)
