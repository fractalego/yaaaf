import logging
import mdpd
import re
import pandas as pd

from typing import Optional, List, Dict

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate, Note
from yaaaf.components.agents.prompts import document_retriever_agent_prompt_template
from yaaaf.components.sources.rag_source import RAGSource
from yaaaf.components.decorators import handle_exceptions
from yaaaf.components.extractors.chunk_extractor import ChunkExtractor

_logger = logging.getLogger(__name__)


class DocumentRetrieverAgent(BaseAgent):
    _system_prompt: PromptTemplate = document_retriever_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```retrieved"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient, sources: List[RAGSource]):
        super().__init__()
        self._client = client
        self._folders_description = "\n".join(
            [
                f"Folder index: {index} -> {source.get_description()}"
                for index, source in enumerate(sources)
            ]
        )
        self._sources = sources
        self._chunk_extractor = ChunkExtractor(client)
        _logger.info(f"DocumentRetrieverAgent initialized with {len(sources)} sources:")
        for index, source in enumerate(sources):
            doc_count = getattr(source, "get_document_count", lambda: "unknown")()
            _logger.info(
                f"  Source {index}: {source.get_description()} ({doc_count} documents)"
            )

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        """
        This agent decides which sources to use for the query and then iterates through the relevant sources to retrieve information.
        """
        messages = messages.add_system_prompt(
            self._system_prompt.complete(folders=self._folders_description)
        )
        all_retrieved_nodes = []
        all_sources = []
        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            answer = response.message

            if notes is not None and step_idx > 0:
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Document Retrieval Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            if self.is_complete(answer) or answer.strip() == "":
                break

            matches = re.findall(
                rf"{self._output_tag}(.+)```",
                answer,
                re.DOTALL | re.MULTILINE,
            )

            if matches:
                df = mdpd.from_md(matches[0])
                retrievers_and_queries_dict: Dict[str, str] = df.to_dict("list")
                answer = ""
                for index, query in zip(
                    retrievers_and_queries_dict["folder_index"],
                    retrievers_and_queries_dict["query"],
                ):
                    source = self._sources[int(index)]
                    _logger.info(
                        f"Querying source {index} ({source.get_description()}) with query: '{query}'"
                    )
                    retrieved_nodes = source.get_data(query)
                    _logger.info(
                        f"Retrieved {len(retrieved_nodes)} nodes from source {index}"
                    )
                    all_retrieved_nodes.extend(retrieved_nodes)
                    all_sources.extend([source.source_path] * len(retrieved_nodes))
                    answer += f"Folder index: {index} -> {retrieved_nodes}\n"

                current_output = all_retrieved_nodes.copy()
                messages = messages.add_user_utterance(
                    f"The answer is {answer}.\n\nThe output of this query is {current_output}.\n\n\n"
                    f"If the user's answer is answered write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"Otherwise, try to understand from the answer how to modify the query and get better results.\n"
                )
            else:
                messages = messages.add_user_utterance(
                    f"The answer is {answer} but there is no table.\n"
                    f"If the user's answer is answered write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"Otherwise, try to understand from the answer how to modify the query and get better results.\n"
                )

        df = pd.DataFrame(
            {"retrieved text chunks": all_retrieved_nodes, "source": all_sources}
        )
        df = df.drop_duplicates().reset_index(drop=True)
        df = await self._apply_chunk_extraction(df, messages)
        retrieval_id: str = str(hash(str(messages))).replace("-", "")
        self._storage.store_artefact(
            retrieval_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description=str(messages),
                data=df,
                id=retrieval_id,
            ),
        )
        return f"The result is in this artefact <artefact type='table'>{retrieval_id}</artefact>"

    async def _apply_chunk_extraction(
        self, df: pd.DataFrame, messages: Messages
    ) -> pd.DataFrame:
        """Apply chunk extraction to retrieved documents and return aggregated results."""
        if df.empty:
            return pd.DataFrame(
                columns=["retrieved_text", "document_name", "position_in_document"]
            )

        # Extract the user query from messages
        query = (
            str(messages).split("user:")[-1].strip() if "user:" in str(messages) else ""
        )

        aggregated_results = []

        for _, row in df.iterrows():
            text = row["retrieved text chunks"]
            source = row["source"]

            try:
                # Apply chunk extraction
                chunks = await self._chunk_extractor.extract(text, query)

                # Convert to desired format
                for chunk in chunks:
                    aggregated_results.append(
                        {
                            "retrieved_text": chunk["relevant_chunk_text"],
                            "document_name": source,
                            "position_in_document": chunk["position_in_document"],
                        }
                    )
            except Exception as e:
                _logger.warning(f"Chunk extraction failed for source {source}: {e}")
                # Fallback: use original text
                aggregated_results.append(
                    {
                        "retrieved_text": text,
                        "document_name": source,
                        "position_in_document": "unknown",
                    }
                )

        return pd.DataFrame(aggregated_results)

    def get_status_info(self) -> str:
        """Report status information about available document sources."""
        if not self._sources:
            return "No document sources available"

        status_parts = []
        status_parts.append(f"Available document sources ({len(self._sources)} total):")

        for i, source in enumerate(self._sources, 1):
            # Get source description and path info
            description = source.get_description()
            source_path = getattr(source, "source_path", "Unknown path")

            # Format source info
            if source_path.startswith("uploaded_"):
                source_type = "Uploaded file"
            else:
                source_type = "File/Directory"

            status_parts.append(f"  {i}. {source_type}: {description}")

        return "\n".join(status_parts)

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent searches document sources and retrieves relevant information"

    def get_description(self) -> str:
        return f"""
Document Retriever agent: {self.get_info()}.
Each source is a folder containing a list of documents.
This agent accepts a query in plain English and returns relevant document chunks from the sources.
These document chunks provide the information needed to answer the user's question.
        """
