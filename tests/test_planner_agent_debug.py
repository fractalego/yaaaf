#!/usr/bin/env python3
"""
Test to debug the PlannerAgent behavior
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock

from yaaaf.components.agents.planner_agent import PlannerAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages, Utterance


class TestPlannerAgentDebug(unittest.TestCase):
    def setUp(self):
        # Create a mock client that returns a proper YAML response
        self.mock_client = Mock(spec=OllamaClient)
        
        # Mock available agents
        self.available_agents = [
            {
                "name": "BraveSearchAgent",
                "description": "Search the web for current information",
                "taxonomy": Mock(data_flow="EXTRACTOR", output_permanence="EPHEMERAL")
            },
            {
                "name": "AnswererAgent", 
                "description": "Synthesize information into comprehensive answers",
                "taxonomy": Mock(data_flow="SYNTHESIZER", output_permanence="EPHEMERAL")
            }
        ]
        
        # Create planner agent
        self.planner = PlannerAgent(self.mock_client, self.available_agents)

    def test_planner_system_prompt(self):
        """Test that the planner has a proper system prompt."""
        print(f"Planner system prompt: {self.planner._system_prompt}")
        
        # Check that the prompt contains the expected elements
        self.assertIn("yaml", self.planner._system_prompt.lower())
        self.assertIn("assets:", self.planner._system_prompt)
        self.assertIn("BraveSearchAgent", self.planner._system_prompt)
        self.assertIn("AnswererAgent", self.planner._system_prompt)

    def test_planner_executor_setup(self):
        """Test that the planner executor is set up correctly."""
        self.assertIsNotNone(self.planner._executor)
        print(f"Planner executor type: {type(self.planner._executor)}")

    async def test_planner_with_mock_response(self):
        """Test planner with a mocked YAML response."""
        # Mock the client to return a proper YAML plan
        mock_yaml_plan = """I'll create a plan to find current information about Italy's prime minister.

```yaml
assets:
  current_pm_search:
    agent: BraveSearchAgent
    description: "Search for current prime minister of Italy"
    type: TEXT
    validation:
      - content_length > 0
      
  pm_answer:
    agent: AnswererAgent
    description: "Synthesize information about Italy's current PM"
    type: TEXT
    inputs: [current_pm_search]
```

This plan will search for current information and then synthesize an answer."""

        self.mock_client.predict = AsyncMock(return_value=mock_yaml_plan)
        
        # Test the planner
        messages = Messages(utterances=[
            Utterance(role="user", content="Who is the current prime minister of Italy?")
        ])
        
        response = await self.planner.query(messages)
        print(f"Planner response: {response}")
        
        # Check that we get a proper response
        self.assertIsNotNone(response)
        self.assertIn("yaml", response.lower())

    async def test_planner_executor_directly(self):
        """Test the planner executor directly."""
        from yaaaf.components.executors.planner_executor import PlannerExecutor
        
        executor = PlannerExecutor(self.available_agents)
        
        # Mock the client response
        mock_response = """Here's the execution plan:

```yaml
assets:
  web_search:
    agent: BraveSearchAgent
    description: "Search for Italy PM information"
    type: TEXT
  
  final_answer:
    agent: AnswererAgent
    description: "Provide final answer"
    type: TEXT
    inputs: [web_search]
```"""

        # Test the executor's operation
        try:
            result, error = await executor.execute_operation(
                instruction="Create plan for finding Italy's PM",
                context={"mock_response": mock_response}
            )
            print(f"Executor result: {result}")
            print(f"Executor error: {error}")
        except Exception as e:
            print(f"Executor exception: {e}")

def async_test(coro):
    """Helper to run async tests."""
    def wrapper(self):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(self))
    return wrapper

# Apply async decorator to async test methods
TestPlannerAgentDebug.test_planner_with_mock_response = async_test(TestPlannerAgentDebug.test_planner_with_mock_response)
TestPlannerAgentDebug.test_planner_executor_directly = async_test(TestPlannerAgentDebug.test_planner_executor_directly)


if __name__ == "__main__":
    unittest.main()