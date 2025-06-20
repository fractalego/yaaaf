import os
import json
import requests
from io import StringIO
from typing import Optional, List, Dict

import pandas as pd

from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.prompts import brave_search_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.components.decorators import handle_exceptions
from yaaaf.server.config import get_config

_path = os.path.dirname(os.path.abspath(__file__))


class BraveSearchAgent(BaseAgent):
    _system_prompt: PromptTemplate = brave_search_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```text"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client
        # Get API key from config
        config = get_config()
        self._api_key = config.api_keys.brave_search_api_key
        if not self._api_key:
            raise ValueError(
                "Brave Search API key is required but not found in configuration. Please set 'api_keys.brave_search_api_key' in your config."
            )

    def _search_brave(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Search using Brave Search API
        """
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }
        params = {"q": query, "count": max_results}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            results = []

            # Parse Brave Search response format
            if "web" in data and "results" in data["web"]:
                for result in data["web"]["results"][:max_results]:
                    results.append(
                        {
                            "title": result.get("title", ""),
                            "body": result.get("description", ""),
                            "href": result.get("url", ""),
                        }
                    )

            return results

        except requests.RequestException as e:
            print(f"Error calling Brave Search API: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing Brave Search response: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in Brave Search: {e}")
            return []

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        search_query = ""
        current_output: str | pd.DataFrame = "No output"

        for _ in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            if self.is_complete(answer) or answer.strip() == "":
                break

            search_query: str = get_first_text_between_tags(
                answer, self._output_tag, "```"
            )

            query_results: List[Dict[str, str]] = self._search_brave(
                search_query, max_results=5
            )

            if query_results:
                current_output = pd.DataFrame(
                    [
                        [result["title"], result["body"], result["href"]]
                        for result in query_results
                    ],
                    columns=["Title", "Summary", "URL"],
                )

                messages = messages.add_user_utterance(
                    f"The web search query was {answer}.\n\nThe result of this query is {current_output}.\n\n\n"
                    f"If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"If there are errors correct the query accordingly.\n"
                )
            else:
                messages = messages.add_user_utterance(
                    f"The query is {answer} but there are no results from the Brave Search. Try again. If there are errors correct the query accordingly."
                )

        if isinstance(current_output, str):
            return current_output.replace(task_completed_tag, "")

        df_info_output = StringIO()
        web_search_id = create_hash(str(messages))
        current_output.info(verbose=True, buf=df_info_output)
        self._storage.store_artefact(
            web_search_id,
            Artefact(
                type=Artefact.Types.TABLE,
                data=current_output,
                description=df_info_output.getvalue(),
                code=search_query,
            ),
        )
        return f"The result is in this artifact <artefact type='brave-search-result'>{web_search_id}</artefact>."

    @staticmethod
    def get_info() -> str:
        return "This agent calls the Brave Search engine and outputs the results."

    def get_description(self) -> str:
        return f"""
Brave Web Search agent: {self.get_info()}
This agent provides an interface to Brave Search engine.
To call this agent write {self.get_opening_tag()} INFORMATION TO RETRIEVE {self.get_closing_tag()}
Just write in clear and brief English the information you need to retrieve between these tags. 
        """
