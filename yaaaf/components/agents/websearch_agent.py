import os

import pandas as pd

from duckduckgo_search import DDGS
from typing import Optional, List, Dict

from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.prompts import duckduckgo_search_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.components.decorators import handle_exceptions
from yaaaf.components.agents.web_utils import fetch_url_content

_path = os.path.dirname(os.path.abspath(__file__))


class DuckDuckGoSearchAgent(BaseAgent):
    _system_prompt: PromptTemplate = duckduckgo_search_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```text"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        search_query = ""

        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            if self.is_complete(answer) or answer.strip() == "":
                break

            search_query: str = get_first_text_between_tags(
                answer, self._output_tag, "```"
            )

            # Get search results using DuckDuckGo
            try:
                query_results: List[Dict[str, str]] = DDGS().text(
                    search_query, max_results=5
                )
            except Exception as e:
                messages = messages.add_user_utterance(
                    f"Error searching DuckDuckGo for '{search_query}': {str(e)}. Try a different search query."
                )
                continue

            if not query_results:
                messages = messages.add_user_utterance(
                    f"The query '{search_query}' returned no results from DuckDuckGo. Try a different search query."
                )
                continue

            # Browse the top URLs and extract relevant information
            browsed_results = []
            for i, result in enumerate(query_results[:3]):  # Browse top 3 results
                url = result["href"]
                title = result["title"]
                summary = result["body"]

                # Fetch the page content
                content = fetch_url_content(url)

                if not content.startswith("Error"):
                    # Analyze the content using LLM to extract relevant information
                    analysis_prompt = f"""
                    Based on the search query: "{search_query}"
                    
                    Page Title: {title}
                    URL: {url}
                    Page Content: {content}
                    
                    Extract the most relevant information that answers the search query. 
                    Focus on factual information, key findings, and important details.
                    Keep the response concise but informative (max 300 words).
                    """

                    analysis_messages = Messages().add_user_utterance(analysis_prompt)
                    relevant_info = await self._client.predict(
                        messages=analysis_messages
                    )

                    browsed_results.append(
                        {
                            "Title": title,
                            "URL": url,
                            "Summary": summary,
                            "Key_Information": relevant_info.strip(),
                            "Source": f"Retrieved from {url}",
                        }
                    )
                else:
                    # If we can't fetch content, use the search summary
                    browsed_results.append(
                        {
                            "Title": title,
                            "URL": url,
                            "Summary": summary,
                            "Key_Information": summary,
                            "Source": f"Retrieved from {url}",
                        }
                    )

            if browsed_results:
                # Create comprehensive table with browsed content
                result_df = pd.DataFrame(browsed_results)

                # Generate a comprehensive answer with citations
                final_answer_prompt = f"""
                Based on the search query: "{search_query}"
                
                I have gathered information from multiple sources. Here's what I found:
                
                {result_df.to_string(index=False)}
                
                Please provide a comprehensive answer to the search query, citing the specific sources (URLs) where each piece of information was found.
                Format your answer clearly and include citations like [Source: URL].
                """

                final_messages = Messages().add_user_utterance(final_answer_prompt)
                comprehensive_answer = await self._client.predict(
                    messages=final_messages
                )

                # Store the results table as an artifact
                web_search_id = create_hash(str(messages) + search_query)
                self._storage.store_artefact(
                    web_search_id,
                    Artefact(
                        type=Artefact.Types.TABLE,
                        data=result_df,
                        description=f"DuckDuckGo Search results with browsed content for query: {search_query}",
                        code=search_query,
                    ),
                )

                # Return both the answer and the table reference
                return f"{comprehensive_answer}\n\nDetailed results table: <artefact type='called-tools-table'>{web_search_id}</artefact>"
            else:
                messages = messages.add_user_utterance(
                    f"Could not retrieve detailed information from any URLs for query '{search_query}'. Try a different approach."
                )

        return (
            "Could not complete the search and analysis. Please try a different query."
        )

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return "This agent searches the web using DuckDuckGo, browses the top results, and provides comprehensive answers with citations."

    def get_description(self) -> str:
        return f"""
Web Search agent: {self.get_info()}
This agent performs web searches using DuckDuckGo, automatically browses the top 3 results to extract detailed information, and provides comprehensive answers with proper citations.
Results are returned both as a formatted answer with citations and as a detailed table showing all sources.
To call this agent write {self.get_opening_tag()} INFORMATION TO RETRIEVE {self.get_closing_tag()}
Just write in clear and brief English the information you need to retrieve between these tags. 
        """
