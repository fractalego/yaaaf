import base64
import logging
import os
import sys
import matplotlib


from io import StringIO
from typing import List, Optional

from yaaaf.components.agents.artefact_utils import (
    get_table_and_model_from_artefacts,
    get_artefacts_from_utterance_content,
    create_prompt_from_artefacts,
)
from yaaaf.components.extractors.artefact_extractor import ArtefactExtractor
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.hash_utils import create_hash
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.agents.texts import no_artefact_text
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Note, Tool, ToolFunction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
from yaaaf.components.agents.prompts import (
    visualization_agent_prompt_template_without_model,
    visualization_agent_prompt_template_with_model,
)
from yaaaf.components.decorators import handle_exceptions

_logger = logging.getLogger(__name__)
matplotlib.use("Agg")


class VisualizationAgent(BaseAgent):
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```python"
    _stop_sequences = _completing_tags
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient):
        super().__init__()
        self._client = client
        self._artefact_extractor = ArtefactExtractor(client)


    @handle_exceptions
    async def query(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> str:
        last_utterance = messages.utterances[-1]
        artefact_list: List[Artefact] = get_artefacts_from_utterance_content(
            last_utterance.content
        )
        
        # Try to extract artefacts from notes if none found in utterance
        artefact_list = await self._try_extract_artefacts_from_notes(
            artefact_list, last_utterance, notes
        )
        
        if not artefact_list:
            return no_artefact_text

        image_id: str = create_hash(str(messages))
        image_name: str = image_id + ".png"
        messages = messages.add_system_prompt(
            create_prompt_from_artefacts(
                artefact_list,
                image_name,
                visualization_agent_prompt_template_with_model,
                visualization_agent_prompt_template_without_model,
            )
        )
        df, model = get_table_and_model_from_artefacts(artefact_list)
        code = ""
        for step_idx in range(self._max_steps):
            response = await self._client.predict(
                messages=messages, stop_sequences=self._stop_sequences
            )
            answer = response.message

            # Log internal thinking step
            if (
                notes is not None and step_idx > 0
            ):  # Skip first step to avoid duplication with orchestrator
                model_name = getattr(self._client, "model", None)
                internal_note = Note(
                    message=f"[Visualization Step {step_idx}] {answer}",
                    artefact_id=None,
                    agent_name=self.get_name(),
                    model_name=model_name,
                    internal=True,
                )
                notes.append(internal_note)

            messages.add_assistant_utterance(answer)
            code = get_first_text_between_tags(answer, self._output_tag, "```")
            code_result = "No code found"
            if code:
                old_stdout = sys.stdout
                redirected_output = sys.stdout = StringIO()
                global_variables = globals().copy()
                global_variables.update({"dataframe": df, "sklearn_model": model})
                exec(code, global_variables)
                sys.stdout = old_stdout
                code_result = redirected_output.getvalue()
                if code_result.strip() == "":
                    code_result = ""

            if (
                self.is_complete(answer)
                or answer.strip() == ""
                or code_result.strip() == ""
            ):
                break

            feedback_message = f"The result is: {code_result}. If there are no errors write {self._completing_tags[0]} at the beginning of your answer.\n"
            self._add_internal_message(
                feedback_message, notes, "Visualization Feedback"
            )
            messages.add_assistant_utterance(feedback_message)

        if not os.path.exists(image_name):
            return "No image was generated. Please try again."

        with open(image_name, "rb") as file:
            base64_image: str = base64.b64encode(file.read()).decode("ascii")
            self._storage.store_artefact(
                image_id,
                Artefact(
                    type=Artefact.Types.IMAGE,
                    image=base64_image,
                    description=str(messages),
                    code=code,
                    data=df,
                    id=image_id,
                ),
            )
            os.remove(image_name)

        result = f"The result is in this artefact <artefact type='image'>{image_id}</artefact>"

        if notes is not None:
            model_name = getattr(self._client, "model", None)
            note = Note(
                message=result,
                artefact_id=image_id,
                agent_name=self.get_name(),
                model_name=model_name,
            )
            notes.append(note)

        return result

    @staticmethod
    def get_info() -> str:
        """Get a brief high-level description of what this agent does."""
        return (
            "This agent creates charts, graphs, and visualizations from tabular data"
        )

    def get_description(self) -> str:
        return f"{self.get_info()}. Provide clear instructions describing what to plot and what aspects of the data to visualize. The agent will create appropriate charts, graphs, or visualizations based on your instructions."

    def get_tool(self) -> Tool:
        """
        Get a tool representation of this agent.
        
        Returns:
            Tool: A tool data model that can be used to call this agent
        """
        return Tool(
            type="function",
            function=ToolFunction(
                name=self.get_name(),
                description=self.get_info(),
                parameters={
                    "type": "object",
                    "properties": {
                        "instruction": {
                            "type": "string",
                            "description": self.get_description()
                        },
                        "artefact_id": {
                            "type": "string",
                            "description": "ID of the artefact containing table with numerical data for visualization"
                        }
                    },
                    "required": ["instruction", "artefact_id"]
                }
            )
        )
