from typing import Optional
from pydantic import BaseModel

from yaaf.components.agents.artefacts import Artefact


class Note(BaseModel):
    message: str
    artefact: Optional[Artefact]
    agent_name: Optional[str] = None

    def __repr__(self):
        return f"Event(type={self.type}, data={self.data})"

    def __str__(self):
        return self.__repr__()

    def add_artefact(self, artefact: Artefact) -> "Note":
        self.artefact = artefact
        return self

    def add_message(self, message: str) -> "Note":
        self.message = message
        return self