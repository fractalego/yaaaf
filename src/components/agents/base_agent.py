from typing import Optional, List


class BaseAgent:
    def query(self, messages: "Messages", message_queue: Optional[List[str]] = None) -> str:
        pass

    def get_name(self) -> str:
        return self.__class__.__name__

    def is_complete(self, answer: str) -> bool:
        if any(tag in answer for tag in self._completing_tags):
            return True

        return False

    def clean_answer(self, answer: str) -> str:
        return answer