import logging
from typing import Dict, Any, Optional, Tuple, List

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.executors.base import ToolExecutor
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.data_types import Messages, Note
from yaaaf.components.extractors.chunk_extractor import ChunkExtractor
from yaaaf.components.sources.rag_source import RAGSource

_logger = logging.getLogger(__name__)


class DocumentRetrieverExecutor(ToolExecutor):
    """Executor for document retrieval using RAG sources."""

    def __init__(self, sources: List[RAGSource], chunk_extractor: ChunkExtractor):
        """Initialize document retriever executor."""
        self._storage = ArtefactStorage()
        self._sources = sources
        self._chunk_extractor = chunk_extractor
        self._folders_description = "\n".join(
            [
                f"Folder index: {index} -> {source.get_description()}"
                for index, source in enumerate(sources)
            ]
        )
        
    async def prepare_context(self, messages: Messages, notes: Optional[list[Note]] = None) -> Dict[str, Any]:
        """Prepare context for document retrieval."""
        return {
            "messages": messages,
            "notes": notes or [],
            "sources": self._sources,
            "folders_description": self._folders_description
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract retrieval query from response."""
        return get_first_text_between_tags(response, "```retrieved", "```")

    async def execute_operation(self, instruction: str, context: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
        """Execute document retrieval."""
        try:
            query = instruction.strip()
            sources = context["sources"]
            
            # Extract chunks using the chunk extractor
            chunks_text = await self._chunk_extractor.extract(query, "")
            
            if not chunks_text or chunks_text.strip() == "":
                return None, "No relevant documents found for the query"
            
            # Create retrieved document content
            retrieved_content = {
                "query": query,
                "content": chunks_text,
                "sources_count": len(sources)
            }
            
            return retrieved_content, None
            
        except Exception as e:
            error_msg = f"Error retrieving documents for '{instruction}': {str(e)}"
            _logger.error(error_msg)
            return None, error_msg

    def validate_result(self, result: Any) -> bool:
        """Validate document retrieval result."""
        return (result is not None and 
                isinstance(result, dict) and 
                "content" in result and 
                "query" in result)

    def transform_to_artifact(self, result: Any, instruction: str, artifact_id: str) -> Artefact:
        """Transform retrieved documents to artifact."""
        return Artefact(
            id=artifact_id,
            type="text",
            code=result["content"],  # Use 'code' field for text content
            description=f"Retrieved documents for query: {result['query']}"
        )