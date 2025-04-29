import logging
from typing import Optional, Dict

import pandas as pd
import sklearn

from pydantic import BaseModel#
from singleton_decorator import singleton

_logger = logging.getLogger(__name__)


class Artefact(BaseModel):
    model: Optional[sklearn.base.BaseEstimator] = None
    data: Optional[pd.DataFrame] = None
    code: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    type: Optional[str] = None
    id: Optional[str] = None

    class Types:
        TABLE = "table"
        IMAGE = "image"
        MODEL = "model"

    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True


@singleton
class ArtefactStorage:
    def __init__(self):
        self.hash_to_artefact_dict: Dict[str, Artefact] = {}

    def store_artefact(self, hash_key: str, artefact: Artefact):
        self.hash_to_artefact_dict[hash_key] = artefact

    def retrieve_artefact(self, hash_key: str) -> Optional[Artefact]:
        if hash_key not in self.hash_to_artefact_dict:
            _logger.warning(f"Artefact with hash {hash_key} not found.")
            raise ValueError(f"Artefact with hash {hash_key} not found.")
        return self.hash_to_artefact_dict.get(hash_key)