import requests
import json
import logging
from pathlib import Path
from requests.exceptions import ConnectionError, Timeout, RequestException

from typing import Optional, List, TYPE_CHECKING

from yaaaf.components.agents.tokens_utils import strip_thought_tokens

if TYPE_CHECKING:
    from yaaaf.components.data_types import Messages

_logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Exception raised when there's a connection error to Ollama."""

    def __init__(self, host: str, model: str, original_error: Exception):
        self.host = host
        self.model = model
        self.original_error = original_error
        super().__init__(
            f"Failed to connect to Ollama at {host} for model '{model}': {original_error}"
        )


class OllamaResponseError(Exception):
    """Exception raised when Ollama returns an error response."""

    def __init__(self, host: str, model: str, status_code: int, response_text: str):
        self.host = host
        self.model = model
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(
            f"Ollama error at {host} for model '{model}': HTTP {status_code} - {response_text}"
        )


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
        cutoffs_file: Optional[str] = None,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.host = host
        self._training_cutoff_date = None
        self._cutoffs_data = None

        # Log Ollama connection details
        _logger.info(f"Initializing OllamaClient for model '{model}' on host '{host}'")

        # Load cutoffs file
        if cutoffs_file is None:
            # Default to the JSON file in the same directory as this module
            cutoffs_file = Path(__file__).parent / "model_training_cutoffs.json"

        self._load_cutoffs_data(cutoffs_file)

    def _load_cutoffs_data(self, cutoffs_file: Path) -> None:
        """
        Load model training cutoffs data from JSON file.

        Args:
            cutoffs_file: Path to the JSON file containing cutoff dates.
        """
        try:
            with open(cutoffs_file, "r", encoding="utf-8") as f:
                self._cutoffs_data = json.load(f)
            _logger.debug(f"Loaded model training cutoffs from {cutoffs_file}")
        except FileNotFoundError:
            _logger.warning(f"Model training cutoffs file not found: {cutoffs_file}")
            self._cutoffs_data = {"model_training_cutoffs": {}, "pattern_matching": {}}
        except json.JSONDecodeError as e:
            _logger.error(f"Error parsing model training cutoffs JSON: {e}")
            self._cutoffs_data = {"model_training_cutoffs": {}, "pattern_matching": {}}
        except Exception as e:
            _logger.error(f"Error loading model training cutoffs: {e}")
            self._cutoffs_data = {"model_training_cutoffs": {}, "pattern_matching": {}}

    def get_training_cutoff_date(self) -> Optional[str]:
        """
        Get the training data cutoff date for the current model.

        Returns:
            Training cutoff date as a string (e.g., "October 2023") or None if unknown.
        """
        if self._training_cutoff_date is not None:
            return self._training_cutoff_date

        if self._cutoffs_data is None:
            _logger.warning("No cutoffs data loaded")
            return None

        # Check if we have an exact match in the model_training_cutoffs
        exact_cutoffs = self._cutoffs_data.get("model_training_cutoffs", {})
        cutoff_date = exact_cutoffs.get(self.model)
        if cutoff_date:
            self._training_cutoff_date = cutoff_date
            _logger.info(f"Training cutoff date for {self.model}: {cutoff_date}")
            return cutoff_date

        # Try pattern matching from the JSON configuration
        pattern_configs = self._cutoffs_data.get("pattern_matching", {})
        model_lower = self.model.lower()

        for pattern, config in pattern_configs.items():
            if pattern.lower() in model_lower:
                if isinstance(config, dict):
                    # Handle special cases like qwen2.5 with coder variant
                    if pattern.lower() == "qwen2.5":
                        if "coder" in model_lower:
                            cutoff_date = config.get("coder")
                        else:
                            cutoff_date = config.get("default")
                    else:
                        # Future extensibility for other complex patterns
                        cutoff_date = config.get("default")
                else:
                    # Simple string mapping
                    cutoff_date = config

                if cutoff_date:
                    self._training_cutoff_date = cutoff_date
                    _logger.info(
                        f"Inferred training cutoff date for {self.model} via pattern '{pattern}': {cutoff_date}"
                    )
                    return cutoff_date

        _logger.warning(f"Unknown training cutoff date for model: {self.model}")
        return None

    async def predict(
        self, messages: "Messages", stop_sequences: Optional[List[str]] = None
    ) -> str:
        _logger.debug(
            f"Making request to Ollama instance at {self.host} with model '{self.model}'"
        )

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

        try:
            response = requests.post(
                f"{self.host}/api/chat",
                headers=headers,
                data=json.dumps(data),
                timeout=600,
            )
        except ConnectionError as e:
            error_msg = f"Connection refused to Ollama at {self.host}. Please ensure Ollama is running and accessible."
            _logger.error(error_msg)
            raise OllamaConnectionError(self.host, self.model, e)
        except Timeout as e:
            error_msg = f"Timeout connecting to Ollama at {self.host}. The server may be overloaded or unreachable."
            _logger.error(error_msg)
            raise OllamaConnectionError(self.host, self.model, e)
        except RequestException as e:
            error_msg = f"Network error connecting to Ollama at {self.host}: {e}"
            _logger.error(error_msg)
            raise OllamaConnectionError(self.host, self.model, e)

        if response.status_code == 200:
            _logger.debug(f"Successfully received response from {self.host}")
            try:
                response_data = json.loads(response.text)
                return strip_thought_tokens(response_data["message"]["content"])
            except (json.JSONDecodeError, KeyError) as e:
                error_msg = f"Invalid response format from Ollama at {self.host}: {e}"
                _logger.error(error_msg)
                raise OllamaResponseError(
                    self.host, self.model, response.status_code, str(e)
                )
        else:
            _logger.error(
                f"Error response from {self.host}: {response.status_code}, {response.text}"
            )
            raise OllamaResponseError(
                self.host, self.model, response.status_code, response.text
            )
