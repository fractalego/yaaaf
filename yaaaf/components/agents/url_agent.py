import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from typing import Optional, List
from urllib.parse import urljoin, urlparse

from yaaaf.components.agents.artefacts import ArtefactStorage, Artefact
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.prompts import url_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate, Note
from yaaaf.components.decorators import handle_exceptions


class URLAgent(BaseAgent):
    _system_prompt: PromptTemplate = url_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```url"
    _stop_sequences = [task_completed_tag]
    _max_steps = 1
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client

    def _fetch_url_content(self, url: str) -> str:
        """Fetch and parse content from a URL."""
        try:
            # Set headers to mimic a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()

            # Parse HTML content
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)

            return text[:10000]  # Limit to first 10k characters

        except requests.exceptions.Timeout:
            return "The website is not accessible from my deployment location (timeout after 3 seconds)"
        except Exception as e:
            return f"Error fetching URL {url}: {str(e)}"

    def _extract_url_and_instruction(self, text: str) -> tuple[str, str]:
        """Extract URL and instruction from the agents arguments."""
        try:
            url, instruction = text.strip().split("|", 1)

        except ValueError:
            return "", ""

        return url.strip(), instruction.strip()

    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        current_output = "No output"
        url, instruction = self._extract_url_and_instruction(
            messages.utterances[-1].content
        )
        if not url or not instruction:
            return (
                f"Could not parse URL and instruction from the input. "
                f"Please provide the URL and instruction in the format:\n"
                f"URL_HERE | INSTRUCTION_HERE"
            )

        for step_idx in range(self._max_steps):
            content = self._fetch_url_content(url)
            new_messages = Messages().add_system_prompt(self._system_prompt.complete(
                url=url,
                content=content,
            ))
            new_messages = new_messages.add_user_utterance(instruction)
            response = await self._client.predict(
                messages=new_messages, stop_sequences=self._stop_sequences
            )
            answer = response.message
            current_output = answer

            if (
                notes is not None and step_idx > 0
            ):  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[URL Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            if self.is_complete(answer) or answer.strip() == "":
                break

            messages = messages.add_user_utterance(
                f"URL processed: {url}\nInstruction: {instruction}\nResult: {current_output}\n\n"
                f"If this answers the user's request, write {self._completing_tags[0]} at the beginning of your response.\n"
                f"Otherwise, provide additional instructions or try a different approach."
            )

        return current_output.replace(task_completed_tag, "")

    @staticmethod
    def get_info() -> str:
        return "This agent fetches content from URLs and analyzes it based on instructions."

    def get_description(self) -> str:
        return f"""
URL Analysis agent: {self.get_info()}
This agent can extract information from web pages or find relevant URLs within the content.
To call this agent write {self.get_opening_tag()} URL_TO_ANALYZE | INSTRUCTION_FOR_ANALYSIS {self.get_closing_tag()}
The agent will either return:
1. Text that answers your instruction based on the URL content
2. A table of URLs found in the content that might be relevant to your instruction
        """
