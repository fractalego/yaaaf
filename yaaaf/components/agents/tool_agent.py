import mdpd
import re
import pandas as pd
import json

from typing import Optional, List, Dict, Any

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.prompts import tool_agent_prompt_template
from yaaaf.components.agents.settings import task_completed_tag
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, PromptTemplate
from yaaaf.connectors.mcp_connector import MCPTools
from yaaaf.components.decorators import handle_exceptions


class ToolAgent(BaseAgent):
    _system_prompt: PromptTemplate = tool_agent_prompt_template
    _completing_tags: List[str] = [task_completed_tag]
    _output_tag = "```tools"
    _stop_sequences = [task_completed_tag]
    _max_steps = 5
    _storage = ArtefactStorage()

    def __init__(self, client: BaseClient, tools: List[MCPTools]):
        self._client = client
        self._tools_description = "\n".join(
            [
                f"Tool group index {group_index}:\n{tool_group.get_tools_descriptions()}\n\n"
                for group_index, tool_group in enumerate(tools)
            ]
        )
        self._tools = tools

    @handle_exceptions
    async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str:
        messages = messages.add_system_prompt(
            self._system_prompt.complete(tools_descriptions=self._tools_description)
        )
        all_tool_results = []
        all_tool_calls = []

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
                tools_and_args_dict: Dict[str, Any] = df.to_dict("list")
                answer = ""

                for group_index, tool_index, arguments in zip(
                    tools_and_args_dict["group_index"],
                    tools_and_args_dict["tool_index"],
                    tools_and_args_dict["arguments"],
                ):
                    # Parse tool index to get group and tool indices
                    tool_group = self._tools[int(group_index)]
                    tool = tool_group[int(tool_index)]

                    # Parse arguments JSON
                    args = (
                        json.loads(arguments)
                        if isinstance(arguments, str)
                        else arguments
                    )

                    # Call the tool
                    result = await tool_group.call_tool(tool.name, args)
                    all_tool_results.append(result)
                    all_tool_calls.append(f"Tool {tool_index} ({tool.name}): {args}")
                    answer += f"Tool index: {tool_index} -> {result}\n"

                current_output = all_tool_results.copy()
                messages = messages.add_user_utterance(
                    f"The answer is {answer}.\n\nThe output of this query is {current_output}.\n\n\n"
                    f"If the user's answer is answered write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"Otherwise, try to understand from the answer how to modify the tool calls and get better results.\n"
                )
            else:
                messages = messages.add_user_utterance(
                    f"The answer is {answer} but there is no table.\n"
                    f"If the user's answer is answered write {self._completing_tags[0]} at the beginning of your answer.\n"
                    f"Otherwise, try to understand from the answer how to modify the tool calls and get better results.\n"
                )

        df = pd.DataFrame({"tool_calls": all_tool_calls, "results": all_tool_results})
        tool_id: str = str(hash(str(messages))).replace("-", "")
        self._storage.store_artefact(
            tool_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description=str(messages),
                data=df,
                id=tool_id,
            ),
        )
        return f"The result is in this artefact <artefact type='called-tools-table'>{tool_id}</artefact>"

    @staticmethod
    def get_info() -> str:
        return "This agent uses MCP (Model Context Protocol) tools to perform various operations."

    def get_description(self) -> str:
        return f"""
Tool agent: {self.get_info()}
Each tool group contains a collection of tools that can be called with specific arguments.
This agent accepts a query in plain English and uses the appropriate tools to gather information or perform actions.
The tools provide the capabilities needed to answer the user's question or complete the requested task.
        """
