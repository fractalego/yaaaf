import mdpd
import re
import pandas as pd

from typing import Optional, List, Dict

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.components.agents.prompts import rag_agent_prompt_template
from yaaaf.components.sources.rag_source import RAGSource
from yaaaf.components.decorators import handle_exceptions


class RAGAgent(BaseAgent):
    _system_prompt: PromptTemplate = rag_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```retrieved"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient, sources: List[RAGSource]):
        self._client = client
        self._folders_description = "\n".join(
            [
                f"Folder index: {index} -> {source.get_description()}"
                for index, source in enumerate(sources)
            ]
        )
        self._sources = sources

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(folders=self._folders_description)
        )
        all_retrieved_nodes = []
        all_sources = []
        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
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
                    retrieved_nodes = source.get_data(query)
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
        rag_id: str = str(hash(str(messages))).replace("-", "")
        self._storage.store_artefact(
            rag_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description=str(messages),
                data=df,
                id=rag_id,
            ),
        )
        return (
            f"The result is in this artefact <artefact type='table'>{rag_id}</artefact>"
        )

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return (
            "This agent queries the RAG sources and retrieves the relevant information"
        )

    def get_description(self) -> str:
        return f"""
RAG agent: {self.get_info()}.
Each source is a folder containing a list of documents.
This agent accepts a query in plain English and returns the relevant documents from the sources.
These documents provide the information needed to answer the user's question.
        """
