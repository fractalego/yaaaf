from typing import Optional, List


class BaseAgent:
    def query(
        self, messages: "Messages", message_queue: Optional[List[str]] = None
    ) -> str:
        pass

    def get_name(self) -> str:
        return self.__class__.__name__

    def get_description(self) -> str:
        return "This is just a Base agent. All it does is to say 'Unknown agent'."

    def get_opening_tag(self) -> str:
        return "<unknown-agent>"

    def get_closing_tag(self) -> str:
        return "</unknown-agent>"

    def is_complete(self, answer: str) -> bool:
        if any(tag in answer for tag in self._completing_tags):
            return True

        return False

    def clean_answer(self, answer: str) -> str:
        return answer
