from typing import Optional, List, TYPE_CHECKING

from yaaaf.components.data_types import Note

if TYPE_CHECKING:
    from yaaaf.components.data_types import Messages


class BaseAgent:
    def __init__(self):
        self._budget = 2  # Default budget for most agents
        self._original_budget = 2  # Keep track of original budget for reset

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
        return f"{self.get_info()}. This is just a Base agent. All it does is to say 'Unknown agent'. Budget: {self._budget} calls."

    def get_budget(self) -> int:
        """Get the current budget (remaining calls) for this agent."""
        return self._budget

    def consume_budget(self) -> bool:
        """Consume one budget token. Returns True if budget was available, False if exhausted."""
        if self._budget > 0:
            self._budget -= 1
            return True
        return False

    def reset_budget(self) -> None:
        """Reset budget to original value for a new query."""
        self._budget = self._original_budget

    def set_budget(self, budget: int) -> None:
        """Set the budget for this agent."""
        self._budget = budget
        self._original_budget = budget

    def get_opening_tag(self) -> str:
        return f"<{self.get_name()}>"

    def get_closing_tag(self) -> str:
        return f"</{self.get_name()}>"

    def is_complete(self, answer: str) -> bool:
        if any(tag in answer for tag in self._completing_tags):
            return True

        return False
