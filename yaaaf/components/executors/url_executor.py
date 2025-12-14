import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, Tuple

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note

_logger = logging.getLogger(__name__)


class URLExecutor(ToolExecutor):
    """Executor for URL fetching and content extraction."""

    def __init__(self):
        """Initialize URL executor."""
        self._storage = ArtefactStorage()
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for URL fetching."""
        return {
            "messages": messages,
            "notes": notes or []
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract URL from response."""
        return get_first_text_between_tags(response, "```url", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Fetch and parse URL content."""
        try:
            url = instruction.strip()
            
            # Set headers to mimic a real browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # Fetch the URL with timeout
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract meaningful text content
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text and clean it up
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text_content = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Limit content length to prevent excessive token usage
            if len(text_content) > 10000:
                text_content = text_content[:10000] + "\n... (content truncated)"
            
            return {
                "url": url,
                "title": soup.title.string if soup.title else "No title",
                "content": text_content
            }, None
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout fetching URL: {instruction}"
            _logger.error(error_msg)
            return None, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching URL '{instruction}': {str(e)}"
            _logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Error parsing content from '{instruction}': {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def validate_result(self, result: Any) -> bool:
        """Validate URL fetch result."""
        return (result is not None and 
                isinstance(result, dict) and 
                "content" in result and 
                "url" in result)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform URL content to artifact."""
        return Artefact(
            id=artifact_id,
            type="text",
            code=result["content"],  # Use 'code' field for text content
            description=f"Content from {result['url']}: {result.get('title', 'No title')}"
        )