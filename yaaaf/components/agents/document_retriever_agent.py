import logging
from typing import List

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import DocumentRetrieverExecutor
from yaaaf.components.agents.prompts import document_retriever_agent_prompt_template
from yaaaf.components.client import BaseClient
from yaaaf.components.extractors.chunk_extractor import ChunkExtractor
from yaaaf.components.sources.rag_source import RAGSource

_logger = logging.getLogger(__name__)


class DocumentRetrieverAgent(ToolBasedAgent):
    """Agent that retrieves documents using RAG sources."""

    def __init__(self, client: BaseClient, sources: List[RAGSource]):
        """Initialize document retriever agent."""
        chunk_extractor = ChunkExtractor(client)
        super().__init__(client, DocumentRetrieverExecutor(sources, chunk_extractor))
        self._system_prompt = document_retriever_agent_prompt_template
        self._output_tag = "```retrieved"
        self._sources = sources
        
        _logger.info(f"DocumentRetrieverAgent initialized with {len(sources)} sources:")
        for i, source in enumerate(sources):
            _logger.info(f"  {i}: {source.get_description()}")

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Retrieves relevant documents using RAG sources"

    def get_description(self) -> str:
        return f"""
Document Retriever agent: {self.get_info()}.
This agent can:
- Search through document collections
- Retrieve relevant text chunks
- Find information in knowledge bases
- Extract context from documents

To call this agent write {self.get_opening_tag()} DOCUMENT_SEARCH_QUERY {self.get_closing_tag()}
Provide a clear search query for the information you need.
        """