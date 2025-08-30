import asyncio
import unittest
from unittest.mock import Mock

from yaaaf.components.agents.user_input_agent import UserInputAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.data_types import Messages
from yaaaf.components.data_types.tools import ClientResponse


class TestUserInputAgent(unittest.TestCase):
    def setUp(self):
        self.client = Mock(spec=OllamaClient)
        self.agent = UserInputAgent(self.client)

    def test_initialization(self):
        """Test that UserInputAgent initializes correctly."""
        self.assertIsNotNone(self.agent._client)
        self.assertEqual(self.agent.get_name(), "userinputagent")
        self.assertIn("User Input agent", self.agent.get_description())

    def test_get_description(self):
        """Test that the agent description is informative."""
        description = self.agent.get_description()
        self.assertIn("User Input agent", description)
        self.assertIn("interact with the user", description)
        self.assertIn("<userinputagent>", description)
        self.assertIn("</userinputagent>", description)

    def test_opening_and_closing_tags(self):
        """Test that agent has correct HTML-like tags."""
        self.assertEqual(self.agent.get_opening_tag(), "<userinputagent>")
        self.assertEqual(self.agent.get_closing_tag(), "</userinputagent>")

    def test_is_paused_method(self):
        """Test the is_paused method correctly identifies paused responses."""
        self.assertTrue(self.agent.is_paused("Some question <taskpaused/>"))
        self.assertTrue(self.agent.is_paused("<taskpaused/> at the beginning"))
        self.assertFalse(self.agent.is_paused("No pause tag here"))
        self.assertFalse(self.agent.is_paused("This has <taskcompleted/> only"))

    def test_query_with_question_format(self):
        """Test agent query that asks a formatted question and pauses."""

        # Mock client response with question format
        async def mock_predict(*args, **kwargs):
            return ClientResponse(
                message="""I need more information to help you.
            ```question
            What specific features would you like in your application?
            ```
            <taskpaused/>"""
            )

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance(
            "Help me build an application but I'm not sure what I need"
        )

        result = asyncio.run(self.agent.query(messages))

        # Should return the question with paused tag
        self.assertIn("What specific features", result)
        self.assertIn("<taskpaused/>", result)

    def test_query_with_direct_pause(self):
        """Test agent query that pauses without question format."""

        # Mock client response with direct pause
        async def mock_predict(*args, **kwargs):
            return ClientResponse(
                message="Could you please clarify what type of data analysis you need? <taskpaused/>"
            )

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance("I need help with data analysis")

        result = asyncio.run(self.agent.query(messages))

        # Should return the question part with paused tag
        self.assertIn("Could you please clarify", result)
        self.assertIn("<taskpaused/>", result)

    def test_query_with_completion(self):
        """Test agent query that completes without pausing."""

        # Mock client response that completes
        async def mock_predict(*args, **kwargs):
            return ClientResponse(
                message="Based on your requirements, here's what I recommend: Use Python with Flask for your web application. <taskcompleted/>"
            )

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance(
            "I want to build a simple web application for my small business"
        )

        result = asyncio.run(self.agent.query(messages))

        # Should return clean output without completion tag
        self.assertIn("Use Python with Flask", result)
        self.assertNotIn("<taskcompleted/>", result)
        self.assertNotIn("<taskpaused/>", result)

    def test_query_with_multi_step_conversation(self):
        """Test agent query with multiple steps before pausing."""
        call_count = 0

        async def mock_predict(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ClientResponse(
                    message="I understand you want to create something. Let me think about what information I need."
                )
            elif call_count == 2:
                return ClientResponse(
                    message="""```question
                What is your budget for this project?
                ```
                <taskpaused/>"""
                )
            else:
                return ClientResponse(
                    message="Thank you for the information. <taskcompleted/>"
                )

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance("I want to create a project")

        result = asyncio.run(self.agent.query(messages))

        # Should return the question with paused tag
        self.assertIn("What is your budget", result)
        self.assertIn("<taskpaused/>", result)

    def test_query_with_malformed_question(self):
        """Test agent query with malformed question format."""
        call_count = 0

        async def mock_predict(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ClientResponse(
                    message="I need to ask you something but forgot the format"
                )
            elif call_count == 2:
                return ClientResponse(
                    message="""```question
                How many users will be using this system?
                ```
                <taskpaused/>"""
                )
            else:
                return ClientResponse(message="Got it. <taskcompleted/>")

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance("Help me design a system")

        result = asyncio.run(self.agent.query(messages))

        # Should eventually get to the properly formatted question
        self.assertIn("How many users", result)
        self.assertIn("<taskpaused/>", result)

    def test_query_with_empty_response(self):
        """Test agent query with empty response."""

        # Mock client response that's empty
        async def mock_predict(*args, **kwargs):
            return ClientResponse(message="")

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance("Test empty response")

        result = asyncio.run(self.agent.query(messages))

        # Should handle empty response gracefully
        self.assertIsInstance(result, str)

    def test_query_reaches_max_steps(self):
        """Test agent query that reaches maximum steps."""

        # Mock client response that never completes or pauses
        async def mock_predict(*args, **kwargs):
            return ClientResponse(message="I'm still thinking about your request...")

        self.client.predict = mock_predict

        messages = Messages().add_user_utterance("Complex request")

        result = asyncio.run(self.agent.query(messages))

        # Should return the last output even if max steps reached
        self.assertIn("thinking", result)

    def test_completing_tags_include_both_completion_and_pause(self):
        """Test that completing tags include both completion and pause tags."""
        from yaaaf.components.agents.settings import task_completed_tag, task_paused_tag

        self.assertIn(task_completed_tag, self.agent._completing_tags)
        self.assertIn(task_paused_tag, self.agent._completing_tags)

    def test_is_complete_method_with_pause_tag(self):
        """Test that is_complete method returns True for pause tag."""
        self.assertTrue(self.agent.is_complete("Some response <taskpaused/>"))
        self.assertTrue(self.agent.is_complete("Some response <taskcompleted/>"))
        self.assertFalse(self.agent.is_complete("Some response without tags"))


if __name__ == "__main__":
    unittest.main()
