import base64
import os
from io import StringIO

import sys

import matplotlib
import re

from typing import List, Dict, Optional
from src.components.agents.base_agent import BaseAgent
from src.components.client import BaseClient
from src.components.data_types import PromptTemplate, Messages
from src.components.agents.prompts import visualization_agent_prompt_template

matplotlib.use('Agg')


class VisualizationAgent(BaseAgent):
    _system_prompt: PromptTemplate = visualization_agent_prompt_template
    _completing_tags: List[str] = ["<complete/>"]
    _output_tag = "<code>"
    _stop_sequences = _completing_tags
    _max_steps = 5
    _hash_to_images_dict: Dict[str, str] = {}

    def __init__(self, client: BaseClient):
        self._client = client

    def query(self, messages: Messages, message_queue: Optional[List[str]] = None) -> str:
        image_name: str = str(hash(str(messages))).replace("-", "") + ".png"
        messages = messages.add_system_prompt(
            self._system_prompt.complete(filename=image_name)
        )
        for _ in range(self._max_steps):
            answer = self._client.predict(messages=messages, stop_sequences=self._stop_sequences)
            messages.add_assistant_utterance(answer)
            matches = re.findall(
                rf"{self._output_tag}(.+?){self._output_tag.replace('<','</')}",
                answer,
                re.DOTALL | re.MULTILINE,
            )
            if not matches:
                matches = re.findall(
                    rf"```python(.+?)```",
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
                except Exception as e:
                    print(e)
                    code_result = f"Error while executing the code above.\nThis exception is raised {str(e)}"

            if self.is_complete(answer):
                break

            messages.add_assistant_utterance(
                f"The result is:\n\n{code_result}\n\n.Think if you need to do more otherwise output {self._completing_tags[0]}.\n"
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