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
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.components.decorators import handle_exceptions


class URLAgent(BaseAgent):
    _system_prompt: PromptTemplate = url_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```url"
    _stop_sequences = [task_completed_tag]
    _max_steps = 3
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        self._client = client

    def _fetch_url_content(self, url: str) -> str:
        """Fetch and parse content from a URL."""
        try:
            # Set headers to mimic a real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=30)
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

        except Exception as e:
            return f"Error fetching URL {url}: {str(e)}"

    def _extract_urls_from_content(self, content: str, base_url: str) -> List[str]:
        """Extract URLs from content."""
        urls = []

        # Parse content as HTML to find links
        try:
            soup = BeautifulSoup(content, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)
                if urlparse(absolute_url).scheme in ["http", "https"]:
                    urls.append(absolute_url)
        except Exception:
            # If HTML parsing fails, try regex
            url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, content)

        return list(set(urls))  # Remove duplicates

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(self._system_prompt)
        url = ""
        instruction = ""
        current_output = "No output"

        for step in range(self._max_steps):
            answer = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )

            if self.is_complete(answer) or answer.strip() == "":
                break

            # Extract URL and instruction from the agent's response
            url_and_instruction = get_first_text_between_tags(
                answer, self._output_tag, "```"
            )

            if url_and_instruction:
                lines = url_and_instruction.strip().split("\n", 1)
                if len(lines) >= 2:
                    url = lines[0].strip()
                    instruction = lines[1].strip()
                elif len(lines) == 1:
                    # If only one line, assume it's a URL and use a default instruction
                    url = lines[0].strip()
                    instruction = "Extract relevant information from this page"

                # Fetch URL content
                content = self._fetch_url_content(url)

                if content.startswith("Error"):
                    messages = messages.add_user_utterance(
                        f"Failed to fetch URL: {content}. Please try a different approach or URL."
                    )
                    continue

                # Analyze content with the instruction
                analysis_prompt = f"""
                URL: {url}
                Instruction: {instruction}
                
                Content from the URL:
                {content}
                
                Based on the instruction "{instruction}", please analyze the content and respond with either:
                1. Text that answers the instruction, OR
                2. A markdown table with URLs that might answer the instruction
                
                If you find URLs in the content that are relevant to the instruction, create a table with columns: URL | Description
                If you can answer the instruction directly from the content, provide the answer as text.
                """

                # Process the content based on instruction
                extracted_urls = self._extract_urls_from_content(content, url)

                if (
                    extracted_urls
                    and "find" in instruction.lower()
                    or "search" in instruction.lower()
                    or "look for" in instruction.lower()
                ):
                    # Create table of URLs
                    url_data = []
                    for found_url in extracted_urls[:20]:  # Limit to 20 URLs
                        # Try to get a description from link text or use URL
                        description = f"Link found on {urlparse(url).netloc}"
                        url_data.append([found_url, description])

                    if url_data:
                        current_output = pd.DataFrame(
                            url_data, columns=["URL", "Description"]
                        )
                    else:
                        current_output = (
                            f"No relevant URLs found for instruction: {instruction}"
                        )
                else:
                    # Return text analysis
                    analysis_messages = Messages().add_user_utterance(analysis_prompt)
                    current_output = await self._client.predict(
                        messages=analysis_messages
                    )

                messages = messages.add_user_utterance(
                    f"URL processed: {url}\nInstruction: {instruction}\nResult: {current_output}\n\n"
                    f"If this answers the user's request, write {self._completing_tags[0]} at the beginning of your response.\n"
                    f"Otherwise, provide additional instructions or try a different approach."
                )
            else:
                messages = messages.add_user_utterance(
                    f"Could not parse URL and instruction from: {answer}. "
                    f"Please provide the URL and instruction in the format:\n"
                    f"```url\nURL_HERE\nINSTRUCTION_HERE\n```"
                )

        # Handle output based on type
        if isinstance(current_output, pd.DataFrame):
            # Store as artifact
            url_agent_id = create_hash(f"{url}_{instruction}")
            self._storage.store_artefact(
                url_agent_id,
                Artefact(
                    type=Artefact.Types.TABLE,
                    data=current_output,
                    description=f"URLs extracted from {url} for instruction: {instruction}",
                    code=f"URL: {url}\nInstruction: {instruction}",
                ),
            )
            return f"The result is in this artifact <artefact type='url-analysis'>{url_agent_id}</artefact>"
        else:
            # Return text directly
            return current_output.replace(task_completed_tag, "")

    @staticmethod
    def get_info() -> str:
        return "This agent fetches content from URLs and analyzes it based on instructions."

    def get_description(self) -> str:
        return f"""
URL Analysis agent: {self.get_info()}
This agent can extract information from web pages or find relevant URLs within the content.
To call this agent write {self.get_opening_tag()} URL_TO_ANALYZE INSTRUCTION_FOR_ANALYSIS {self.get_closing_tag()}
The agent will either return:
1. Text that answers your instruction based on the URL content
2. A table of URLs found in the content that might be relevant to your instruction
        """
