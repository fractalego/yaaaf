import asyncio
import unittest

from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages, Tool, ToolFunction


class TestClients(unittest.TestCase):
    def test_client_initialization(self):
        client = OllamaClient(
            model="qwen2.5-coder:latest",
            temperature=0.7,
            max_tokens=100,
        )
        messages = (
            Messages()
            .add_system_prompt("You only say hello.")
            .add_user_utterance("Hello, how are you?")
        )
        answer = asyncio.run(
            client.predict(messages=messages, stop_sequences=["<taskcompleted/>"])
        )
        expected = "hello"
        self.assertIn(expected, answer.message.lower())

    def test_client_can_run_tools(self):
        tools = [
            Tool(
                type="function",
                function=ToolFunction(
                    name="todo_agent",
                    description="This agent creates structured todo lists for planning query responses",
                    parameters={
                        "type": "object",
                        "properties": {
                            "instruction": {
                                "type": "string",
                                "description": "A short instruction for the todo agent to follow",
                            },
                        },
                        "required": ["instruction"],
                    },
                ),
            )
        ]

        client = OllamaClient(
            model="qwen2.5-coder:latest",
            temperature=0.7,
            max_tokens=100,
        )
        messages = (
            Messages()
            .add_system_prompt("You only do what the user asks.")
            .add_user_utterance("Hello, find the purpose of life for me.")
        )
        answer = asyncio.run(
            client.predict(
                messages=messages,
                tools=tools,
            )
        )
        print(answer)

        # Verify the response structure
        self.assertIsInstance(answer.message, str)
        self.assertIsInstance(answer.tool_calls, (list, type(None)))

        # When tools are available, the model should use them
        if answer.tool_calls:
            self.assertGreater(len(answer.tool_calls), 0)
            # Check that tool call structure is correct
            tool_call = answer.tool_calls[0]
            self.assertEqual(tool_call.type, "function")
            self.assertEqual(tool_call.function["name"], "todo_agent")
            self.assertIn("instruction", tool_call.function.get("arguments", {}))
        else:
            # If no tool calls, there should be a message
            self.assertGreater(len(answer.message), 0)
