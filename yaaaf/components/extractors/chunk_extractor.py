import logging
import json
from typing import List, Dict, Any

from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.components.extractors.base_extractor import BaseExtractor

_logger = logging.getLogger(__name__)

chunk_extractor_prompt = PromptTemplate(
    prompt="""
You are a chunk extractor. Your task is to identify and extract relevant text chunks from a document that are related to a specific query.

Given the following text and query, extract the most relevant chunks of text that directly answer or relate to the query.

Text:
{text}

Query: {query}

Instructions:
1. Identify text chunks that are directly relevant to the query
2. Each chunk should be a coherent piece of text (sentences or paragraphs)
3. Extract the exact text verbatim from the input - do not paraphrase or modify
4. Include position information (page number, section, or paragraph number if available)
5. Return results as a JSON array with the format:
   [{{\"relevant_chunk_text\": \"exact text from input\", \"position_in_document\": \"page/section identifier\"}}]

If no relevant chunks are found, return an empty array [].
Only return the JSON array, no other text.
"""
)


class ChunkExtractor(BaseExtractor):
    """
    ChunkExtractor extracts relevant text chunks from a document based on a query.
    """

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client

    async def extract(self, text: str, query: str) -> List[Dict[str, Any]]:
        """
        Extract relevant chunks from text based on query.

        Args:
            text: The input text to extract chunks from
            query: The query to match against

        Returns:
            List of dictionaries with keys:
            - relevant_chunk_text: Exact text from input
            - position_in_document: Position identifier (page, section, etc.)
        """
        try:
            instructions = Messages().add_system_prompt(
                chunk_extractor_prompt.complete(text=text, query=query)
            )

            response = await self._client.predict(instructions)
            result_text = response.message.strip()

            # Parse JSON response
            try:
                # Clean up the response - sometimes LLMs add extra text
                result_text = result_text.strip()

                # Try to find JSON in the response
                json_start = result_text.find("[")
                json_end = result_text.rfind("]") + 1

                if json_start >= 0 and json_end > json_start:
                    json_text = result_text[json_start:json_end]
                else:
                    json_text = result_text

                results = json.loads(json_text)
                if not isinstance(results, list):
                    _logger.warning(f"Expected list but got {type(results)}")
                    return []

                # Validate structure of results
                validated_results = []
                for item in results:
                    if (
                        isinstance(item, dict)
                        and "relevant_chunk_text" in item
                        and "position_in_document" in item
                    ):
                        validated_results.append(item)
                    else:
                        _logger.warning(f"Invalid result format: {item}")

                return validated_results

            except json.JSONDecodeError as e:
                _logger.error(f"Failed to parse JSON response: {e}")
                _logger.error(f"Raw response: {result_text}")
                return []

        except Exception as e:
            _logger.error(f"Chunk extraction failed: {e}")
            _logger.debug(f"Error type: {type(e)}")
            _logger.debug(f"Error args: {e.args}")
            return []

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this extractor does."""
        return "Extracts relevant text chunks from documents based on queries"
