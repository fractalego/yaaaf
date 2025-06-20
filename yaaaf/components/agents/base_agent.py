from typing import Optional, List, TYPE_CHECKING

from yaaaf.components.data_types import Note

if TYPE_CHECKING:
    from yaaaf.components.data_types import Messages


class BaseAgent:
    async def query(
        self, messages: "Messages", notes: Optional[List[Note]] = None
    ) -> str:
        pass

    def get_name(self) -> str:
        return self.__class__.__name__.lower()

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "Base agent with no specific functionality"

    def get_description(self) -> str:
        return f"{self.get_info()}. This is just a Base agent. All it does is to say 'Unknown agent'."

    def get_opening_tag(self) -> str:
        return f"<{self.get_name()}>"

    def get_closing_tag(self) -> str:
        return f"</{self.get_name()}>"

    def is_complete(self, answer: str) -> bool:
        if any(tag in answer for tag in self._completing_tags):
            return True

        return False
