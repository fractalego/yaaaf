from typing import Optional, List

from yaaaf.components.data_types import Note


class BaseAgent:
    async def query(
        self, messages: "Messages", notes: Optional[List[Note]] = None
    ) -> str:
        pass

    def get_name(self) -> str:
        return self.__class__.__name__.lower()

    def get_description(self) -> str:
        return "This is just a Base agent. All it does is to say 'Unknown agent'."

    def get_opening_tag(self) -> str:
        return f"<{self.get_name()}>"

    def get_closing_tag(self) -> str:
        return f"</{self.get_name()}>"

    def is_complete(self, answer: str) -> bool:
        if any(tag in answer for tag in self._completing_tags):
            return True

        return False
