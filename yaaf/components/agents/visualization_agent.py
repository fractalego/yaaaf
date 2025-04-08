import base64
import os

import sys
import matplotlib
import re
import numpy as np

from io import StringIO
from typing import List, Dict, Optional
from yaaf.components.agents.base_agent import BaseAgent
from yaaf.components.client import BaseClient
from yaaf.components.data_types import PromptTemplate, Messages
from yaaf.components.agents.prompts import visualization_agent_prompt_template

matplotlib.use("Agg")


class VisualizationAgent(BaseAgent):
    _system_prompt: PromptTemplate = visualization_agent_prompt_template
    _completing_tags: List[str] = ["<task-completed/>"]
    _output_tag = "```python"
    _stop_sequences = _completing_tags
    _max_steps = 5
    _hash_to_images_dict: Dict[str, str] = {}

    def __init__(self, client: BaseClient):
        self._client = client

    def query(
        self, messages: Messages, message_queue: Optional[List[str]] = None
    ) -> str:
        image_name: str = str(hash(str(messages))).replace("-", "") + ".png"
        messages = messages.add_system_prompt(
            self._system_prompt.complete(filename=image_name)
        )
        for _ in range(self._max_steps):
            answer = self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            messages.add_assistant_utterance(answer)
            matches = re.findall(
                rf"{self._output_tag}(.+)```",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            code_result = "No code found"
            if matches:
                code = matches[0]
                try:
                    old_stdout = sys.stdout
                    redirected_output = sys.stdout = StringIO()
                    exec(code)
                    sys.stdout = old_stdout
                    code_result = redirected_output.getvalue()
                    if code_result.strip() == "":
                        code_result = ""
                except Exception as e:
                    print(e)
                    code_result = f"Error while executing the code above.\nThis exception is raised {str(e)}"
                    answer = str(code_result)

            if (
                self.is_complete(answer)
                or answer.strip() == ""
                or code_result.strip() == ""
            ):
                break

            messages.add_assistant_utterance(
                f"The result is: {code_result}. If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
            )

        with open(image_name, "rb") as file:
            base64_image = base64.b64encode(file.read())
            self._hash_to_images_dict[image_name] = base64_image.decode("ascii")
        os.remove(image_name)
        return f"![Image](data:image/png;base64,{image_name})"

    def clean_answer(self, answer: str) -> str:
        replaced_answer = str(answer)
        for filename, base64_image in self._hash_to_images_dict.items():
            replaced_answer = replaced_answer.replace(filename, base64_image)
        return replaced_answer

    def get_description(self) -> str:
        return f"""
Visualization agent: This agent creates the relevant visualization in the format of a graph plot using a markdown table.
To call this agent write {self.get_opening_tag()} MARKDOWN TABLE ABOUT WHAT TO PLOT {self.get_closing_tag()}
The information about what to plot will be then used by the agent.
        """

    def get_opening_tag(self) -> str:
        return "<visualization-agent>"

    def get_closing_tag(self) -> str:
        return "</visualization-agent>"
