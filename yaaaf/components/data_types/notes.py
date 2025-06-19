import re
from typing import Optional
from pydantic import BaseModel


class Note(BaseModel):
    message: str
    artefact_id: Optional[str] = None
    agent_name: Optional[str] = None
    model_name: Optional[str] = None

    def __repr__(self):
        return f"Note(message={self.message[:50]}..., artefact_id={self.artefact_id}, agent_name={self.agent_name}, model_name={self.model_name})"

    def __str__(self):
        return self.__repr__()

    def add_artefact_id(self, artefact_id: str) -> "Note":
        self.artefact_id = artefact_id
        return self

    def add_message(self, message: str) -> "Note":
        self.message = message
        return self

    @staticmethod
    def extract_agent_name_from_tags(text: str) -> Optional[str]:
        """Extract agent name from agent tags in the text (e.g., <sqlagent>...</sqlagent>)"""
        # Look for agent tags (excluding artefact and completion tags)
        agent_tag_pattern = r"<(\w+agent)>"
        matches = re.findall(agent_tag_pattern, text, re.IGNORECASE)
        return matches[0] if matches else None

    @staticmethod
    def clean_agent_tags(text: str) -> str:
        """Remove agent opening and closing tags while preserving artefact and completion tags"""
        # Remove agent tags (ending with 'agent') but keep artefact and completion tags
        # This preserves <artefact>, <taskcompleted>, etc.
        cleaned_text = re.sub(r"</?(\w*agent)>", "", text, flags=re.IGNORECASE)
        return cleaned_text.strip()

    def set_message_cleaned(self, message: str) -> "Note":
        """Set message after cleaning agent tags"""
        self.message = self.clean_agent_tags(message)
        return self
