import json
import logging
import requests
from abc import abstractmethod
from typing import Any, Tuple, Optional, Dict, List

import pandas as pd
from duckduckgo_search import DDGS

from yaaaf.components.agents.artefacts import Artefact
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note
from yaaaf.server.config import get_config

from .base import ToolExecutor

_logger = logging.getLogger(__name__)


class WebSearchExecutor(ToolExecutor):
    """Base executor for web search operations."""

    async def prepare_context(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> Dict[str, Any]:
        """Prepare context for web search.

        Web search doesn't need special context preparation.
        """
        return {}

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract search query from response.

        Looks for search queries between ```text tags.

        Args:
            response: The agent's response

        Returns:
            The search query or None
        """
        return get_first_text_between_tags(response, "text", "text")

    @abstractmethod
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform the actual search.

        Args:
            query: The search query

        Returns:
            List of search results
        """
        pass

    async def execute_operation(
        self, instruction: str, context: Dict[str, Any]
    ) -> Tuple[Any, Optional[str]]:
        """Execute web search.

        Args:
            instruction: The search query
            context: The prepared context (not used)

        Returns:
            Tuple of (search results, error message)
        """
        try:
            results = await self.search(instruction)
            if results:
                return results, None
            else:
                return None, "No search results found"
        except Exception as e:
            _logger.error(f"Search error: {str(e)}")
            return None, str(e)

    def validate_result(self, result: Any) -> bool:
        """Validate search results.

        Args:
            result: The search results

        Returns:
            True if valid results
        """
        return result is not None and isinstance(result, list) and len(result) > 0

    def transform_to_artifact(
        self, result: Any, instruction: str, artifact_id: str
    ) -> Artefact:
        """Transform search results to table artifact.

        Args:
            result: The search results list
            instruction: The search query
            artifact_id: The ID for the artifact

        Returns:
            A table Artefact with search results
        """
        # Convert results to DataFrame
        df = pd.DataFrame(result)

        # Ensure consistent column order
        expected_columns = ["title", "href", "body"]
        if all(col in df.columns for col in expected_columns):
            # Reorder columns and rename href to url
            df = df[expected_columns]
            df = df.rename(columns={"href": "url"})

        return Artefact(
            type=Artefact.Types.TABLE,
            description=f"Web search results for: {instruction}",
            code=instruction,  # Store the search query
            data=df,  # Store the DataFrame
            id=artifact_id,
        )


class DDGSExecutor(WebSearchExecutor):
    """DuckDuckGo search executor."""

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform DuckDuckGo search.

        Args:
            query: The search query

        Returns:
            List of search results
        """
        try:
            results = DDGS().text(query, max_results=20)
            # Convert generator to list
            return list(results)
        except Exception as e:
            _logger.error(f"DDGS search error: {str(e)}")
            raise


class BraveExecutor(WebSearchExecutor):
    """Brave search executor."""

    def __init__(self):
        """Initialize with Brave API key from config."""
        config = get_config()
        self._api_key = config.api_keys.brave_search_api_key
        if not self._api_key:
            raise ValueError(
                "Brave Search API key is required but not found in configuration. "
                "Please set 'api_keys.brave_search_api_key' in your config."
            )
        self._base_url = "https://api.search.brave.com/res/v1/web/search"

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform Brave search.

        Args:
            query: The search query

        Returns:
            List of search results
        """
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }

        params = {
            "q": query,
            "count": 20,
        }

        try:
            response = requests.get(
                self._base_url, headers=headers, params=params, timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # Extract web results
            web_results = data.get("web", {}).get("results", [])

            # Format results to match expected structure
            formatted_results = []
            for result in web_results:
                formatted_results.append(
                    {
                        "title": result.get("title", ""),
                        "href": result.get("url", ""),
                        "body": result.get("description", ""),
                    }
                )

            return formatted_results

        except requests.exceptions.RequestException as e:
            _logger.error(f"Brave search request error: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            _logger.error(f"Brave search JSON decode error: {str(e)}")
            raise
