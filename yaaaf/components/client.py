import requests
import json

from typing import Optional, List

from yaaaf.components.agents.tokens_utils import strip_thought_tokens


class BaseClient:
    async def predict(
        self, messages: "Messages", stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Predicts the next message based on the input messages and stop sequences.

        :param messages: The input messages.
        :param stop_sequences: Optional list of stop sequences.
        :return: The predicted message.
        """
        pass


class OllamaClient(BaseClient):
    """Client for Ollama API."""

    def __init__(
        self,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.host = host

    async def predict(
        self, messages: "Messages", stop_sequences: Optional[List[str]] = None
    ) -> str:
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": messages.model_dump()["utterances"],
            "options": {
                "stop": stop_sequences,
            },
            "stream": False,
        }
        response = requests.post(
            f"{self.host}/api/chat", headers=headers, data=json.dumps(data)
        )
        if response.status_code == 200:
            return strip_thought_tokens(json.loads(response.text)["message"]["content"])
        else:
            raise Exception(f"Error: {response.status_code}, {response.text}")

