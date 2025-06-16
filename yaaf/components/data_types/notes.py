from typing import Optional
from pydantic import BaseModel


class Note(BaseModel):
    message: str
    artefact_id: Optional[str] = None
    agent_name: Optional[str] = None

    def __repr__(self):
        return f"Note(message={self.message[:50]}..., artefact_id={self.artefact_id}, agent_name={self.agent_name})"

    def __str__(self):
        return self.__repr__()

    def add_artefact_id(self, artefact_id: str) -> "Note":
        self.artefact_id = artefact_id
        return self

    def add_message(self, message: str) -> "Note":
        self.message = message
        return self