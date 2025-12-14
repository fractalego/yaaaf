"""Tests for pause/resume mechanism in workflow execution."""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from yaaaf.components.executors.paused_execution import (
    PausedExecutionException,
    PausedExecutionState,
)
from yaaaf.components.executors.workflow_executor import WorkflowExecutor
from yaaaf.components.agents.user_input_agent import UserInputAgent
from yaaaf.components.data_types import Messages, Utterance, Note
from yaaaf.components.data_types.tools import ClientResponse


class TestPausedExecutionState(unittest.TestCase):
    """Test PausedExecutionState data class."""

    def test_paused_execution_state_creation(self):
        """Test creating a PausedExecutionState instance."""
        messages = Messages(utterances=[Utterance(role="user", content="test")])

        state = PausedExecutionState(
            stream_id="test_stream_123",
            original_messages=messages,
            yaml_plan="assets:\n  test: {agent: test}",
            completed_assets={"asset1": "result1"},
            current_asset="user_input_step",
            next_asset_index=2,
            question_asked="What is your name?",
            user_input_messages=messages,
            notes=[],
        )

        self.assertEqual(state.stream_id, "test_stream_123")
        self.assertEqual(state.question_asked, "What is your name?")
        self.assertEqual(state.current_asset, "user_input_step")
        self.assertEqual(state.next_asset_index, 2)
        self.assertEqual(len(state.completed_assets), 1)

    def test_paused_execution_state_repr(self):
        """Test string representation of PausedExecutionState."""
        messages = Messages(utterances=[Utterance(role="user", content="test")])

        state = PausedExecutionState(
            stream_id="test_123",
            original_messages=messages,
            yaml_plan="test",
            completed_assets={},
            current_asset="step1",
            next_asset_index=0,
            question_asked="This is a very long question that should be truncated in repr",
            user_input_messages=messages,
            notes=[],
        )

        repr_str = repr(state)
        self.assertIn("test_123", repr_str)
        self.assertIn("step1", repr_str)
        self.assertIn("completed=0", repr_str)


class TestPausedExecutionException(unittest.TestCase):
    """Test PausedExecutionException."""

    def test_exception_creation(self):
        """Test creating PausedExecutionException with state."""
        messages = Messages(utterances=[Utterance(role="user", content="test")])

        state = PausedExecutionState(
            stream_id="test_stream",
            original_messages=messages,
            yaml_plan="test",
            completed_assets={},
            current_asset="step1",
            next_asset_index=0,
            question_asked="What is your budget?",
            user_input_messages=messages,
            notes=[],
        )

        exception = PausedExecutionException(state)

        self.assertEqual(exception.get_state(), state)
        self.assertIn("What is your budget?", str(exception))

    def test_exception_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught."""
        messages = Messages(utterances=[Utterance(role="user", content="test")])

        state = PausedExecutionState(
            stream_id="test",
            original_messages=messages,
            yaml_plan="test",
            completed_assets={},
            current_asset="step1",
            next_asset_index=0,
            question_asked="Test question",
            user_input_messages=messages,
            notes=[],
        )

        with self.assertRaises(PausedExecutionException) as context:
            raise PausedExecutionException(state)

        caught_state = context.exception.get_state()
        self.assertEqual(caught_state.question_asked, "Test question")


class TestWorkflowExecutorPauseDetection(unittest.TestCase):
    """Test WorkflowExecutor pause detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.yaml_plan = """
assets:
  user_info:
    agent: user_input
    description: "Ask user for their name"
    type: TEXT

  greeting:
    agent: answerer
    description: "Generate personalized greeting"
    type: TEXT
    inputs: [user_info]
"""

        # Mock agents
        self.mock_user_input_agent = MagicMock()
        self.mock_user_input_agent.query = AsyncMock()

        self.mock_answerer_agent = MagicMock()
        self.mock_answerer_agent.query = AsyncMock()

        self.agents = {
            "user_input": self.mock_user_input_agent,
            "answerer": self.mock_answerer_agent,
        }

        self.original_messages = Messages(
            utterances=[Utterance(role="user", content="Greet me")]
        )

    async def test_pause_detection_with_question_format(self):
        """Test that executor detects pause with question format."""
        # User input agent returns paused response
        self.mock_user_input_agent.query.return_value = """
Question for user: What is your name?

```question
What is your name?
```

<taskpaused/>
"""

        executor = WorkflowExecutor(
            yaml_plan=self.yaml_plan,
            agents=self.agents,
            notes=[],
            stream_id="test_stream",
            original_messages=self.original_messages,
        )

        # Execute should raise PausedExecutionException
        with self.assertRaises(PausedExecutionException) as context:
            await executor.execute(self.original_messages)

        # Verify exception state
        state = context.exception.get_state()
        self.assertEqual(state.stream_id, "test_stream")
        self.assertIn("What is your name?", state.question_asked)
        self.assertEqual(state.current_asset, "user_info")
        self.assertEqual(len(state.completed_assets), 0)

    async def test_pause_detection_without_question_format(self):
        """Test pause detection when question is in plain text."""
        # User input agent returns paused response without special format
        self.mock_user_input_agent.query.return_value = """
Could you please tell me your favorite color?
<taskpaused/>
"""

        executor = WorkflowExecutor(
            yaml_plan=self.yaml_plan,
            agents=self.agents,
            notes=[],
            stream_id="test_stream",
            original_messages=self.original_messages,
        )

        with self.assertRaises(PausedExecutionException) as context:
            await executor.execute(self.original_messages)

        state = context.exception.get_state()
        self.assertIn("favorite color", state.question_asked)

    async def test_extract_question_from_result(self):
        """Test question extraction from various result formats."""
        executor = WorkflowExecutor(
            yaml_plan=self.yaml_plan,
            agents=self.agents,
            notes=[],
            stream_id="test",
            original_messages=self.original_messages,
        )

        # Test question format
        result1 = """
```question
What is your budget?
```
<taskpaused/>
"""
        question1 = executor._extract_question_from_result(result1)
        self.assertEqual(question1, "What is your budget?")

        # Test plain text before pause tag
        result2 = "How many users do you have? <taskpaused/>"
        question2 = executor._extract_question_from_result(result2)
        self.assertIn("How many users", question2)

        # Test with "Question for user:" prefix
        result3 = "Question for user: What is your email? <taskpaused/>"
        question3 = executor._extract_question_from_result(result3)
        self.assertIn("What is your email?", question3)
        self.assertNotIn("Question for user:", question3)


class TestWorkflowExecutorResume(unittest.TestCase):
    """Test WorkflowExecutor resume functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.yaml_plan = """
assets:
  user_name:
    agent: user_input
    description: "Ask for user's name"
    type: TEXT

  greeting:
    agent: answerer
    description: "Create personalized greeting"
    type: TEXT
    inputs: [user_name]
"""

        # Mock agents
        self.mock_user_input_agent = MagicMock()
        self.mock_user_input_agent.query = AsyncMock()

        self.mock_answerer_agent = MagicMock()
        self.mock_answerer_agent.query = AsyncMock()

        self.agents = {
            "user_input": self.mock_user_input_agent,
            "answerer": self.mock_answerer_agent,
        }

        self.original_messages = Messages(
            utterances=[Utterance(role="user", content="Greet me")]
        )

    async def test_resume_from_paused_state(self):
        """Test resuming execution from paused state."""
        # Create paused state
        user_input_messages = Messages(
            utterances=[
                Utterance(role="user", content="Greet me"),
                Utterance(
                    role="assistant",
                    content="I need to ask you: What is your name?",
                ),
            ]
        )

        state = PausedExecutionState(
            stream_id="test_stream",
            original_messages=self.original_messages,
            yaml_plan=self.yaml_plan,
            completed_assets={},
            current_asset="user_name",
            next_asset_index=0,
            question_asked="What is your name?",
            user_input_messages=user_input_messages,
            notes=[],
        )

        # Mock user input agent completing with user's response
        self.mock_user_input_agent.query.return_value = (
            "User provided: Alice <taskcompleted/>"
        )

        # Mock answerer agent creating greeting
        self.mock_answerer_agent.query.return_value = (
            "Hello Alice, nice to meet you! <taskcompleted/>"
        )

        # Create executor and resume
        executor = WorkflowExecutor(
            yaml_plan=self.yaml_plan,
            agents=self.agents,
            notes=[],
            stream_id="test_stream",
            original_messages=self.original_messages,
        )

        result = await executor.resume_from_paused_state(state, "Alice")

        # Verify user input agent was called with updated messages
        self.mock_user_input_agent.query.assert_called_once()
        call_messages = self.mock_user_input_agent.query.call_args[0][0]
        # Should have original messages + user's response
        self.assertTrue(any("Alice" in u.content for u in call_messages.utterances))

        # Verify answerer agent was called
        self.mock_answerer_agent.query.assert_called_once()

        # Verify final result
        self.assertIsNotNone(result)

    async def test_resume_with_nested_pause(self):
        """Test that nested pause (another user input) is handled."""
        user_input_messages = Messages(
            utterances=[Utterance(role="user", content="Test")]
        )

        state = PausedExecutionState(
            stream_id="test_stream",
            original_messages=self.original_messages,
            yaml_plan=self.yaml_plan,
            completed_assets={},
            current_asset="user_name",
            next_asset_index=0,
            question_asked="What is your name?",
            user_input_messages=user_input_messages,
            notes=[],
        )

        # First completion
        self.mock_user_input_agent.query.return_value = "User said: Bob <taskcompleted/>"

        # Answerer agent pauses again!
        self.mock_answerer_agent.query.return_value = (
            "What title should I use? <taskpaused/>"
        )

        executor = WorkflowExecutor(
            yaml_plan=self.yaml_plan,
            agents=self.agents,
            notes=[],
            stream_id="test_stream",
            original_messages=self.original_messages,
        )

        # Should raise another PausedExecutionException
        with self.assertRaises(PausedExecutionException) as context:
            await executor.resume_from_paused_state(state, "Bob")

        nested_state = context.exception.get_state()
        self.assertEqual(nested_state.current_asset, "greeting")
        self.assertIn("title", nested_state.question_asked.lower())

    async def test_resume_preserves_completed_assets(self):
        """Test that completed assets are preserved during resume."""
        # Create state with some completed assets
        state = PausedExecutionState(
            stream_id="test_stream",
            original_messages=self.original_messages,
            yaml_plan=self.yaml_plan,
            completed_assets={"previous_step": "previous result"},
            current_asset="user_name",
            next_asset_index=1,
            question_asked="What is your name?",
            user_input_messages=Messages(
                utterances=[Utterance(role="user", content="test")]
            ),
            notes=[],
        )

        self.mock_user_input_agent.query.return_value = "Alice <taskcompleted/>"
        self.mock_answerer_agent.query.return_value = (
            "Hello Alice! <taskcompleted/>"
        )

        executor = WorkflowExecutor(
            yaml_plan=self.yaml_plan,
            agents=self.agents,
            notes=[],
            stream_id="test_stream",
            original_messages=self.original_messages,
        )

        await executor.resume_from_paused_state(state, "Alice")

        # Verify completed assets were restored
        self.assertIn("previous_step", executor.asset_results)
        self.assertEqual(executor.asset_results["previous_step"], "previous result")


class TestAccessoriesPauseResume(unittest.TestCase):
    """Test accessories.py pause/resume functions."""

    def test_save_and_get_paused_state(self):
        """Test saving and retrieving paused state."""
        from yaaaf.server.accessories import (
            save_paused_state,
            get_paused_state,
            clear_paused_state,
        )

        messages = Messages(utterances=[Utterance(role="user", content="test")])

        state = PausedExecutionState(
            stream_id="test_123",
            original_messages=messages,
            yaml_plan="test",
            completed_assets={},
            current_asset="step1",
            next_asset_index=0,
            question_asked="Test?",
            user_input_messages=messages,
            notes=[],
        )

        # Save state
        save_paused_state("test_123", state)

        # Retrieve state
        retrieved = get_paused_state("test_123")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.stream_id, "test_123")
        self.assertEqual(retrieved.question_asked, "Test?")

        # Clear state
        clear_paused_state("test_123")
        cleared = get_paused_state("test_123")
        self.assertIsNone(cleared)

    def test_get_nonexistent_paused_state(self):
        """Test getting state for stream that doesn't exist."""
        from yaaaf.server.accessories import get_paused_state

        result = get_paused_state("nonexistent_stream")
        self.assertIsNone(result)


class TestUserInputAgentIntegration(unittest.TestCase):
    """Integration tests for UserInputAgent with pause/resume."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_client.predict = AsyncMock()
        self.agent = UserInputAgent(self.mock_client)

    async def test_user_input_agent_pauses_correctly(self):
        """Test that UserInputAgent returns paused response."""
        # Mock client to return question with pause tag
        self.mock_client.predict.return_value = ClientResponse(
            message="""
```question
What is your project budget?
```
<taskpaused/>
"""
        )

        messages = Messages().add_user_utterance(
            "I need help planning my project budget"
        )

        result = await self.agent.query(messages)

        # Should contain the question and pause tag
        self.assertIn("budget", result.lower())
        self.assertIn("<taskpaused/>", result)
        self.assertTrue(self.agent.is_paused(result))

    async def test_user_input_agent_completion_after_response(self):
        """Test UserInputAgent completes after receiving user response."""
        call_count = 0

        async def mock_predict_sequence(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: ask question
                return ClientResponse(
                    message="```question\nWhat is your name?\n```\n<taskpaused/>"
                )
            else:
                # Second call: user provided answer, complete
                return ClientResponse(message="Thank you! <taskcompleted/>")

        self.mock_client.predict = mock_predict_sequence

        # First query - agent asks question
        messages = Messages().add_user_utterance("I need help")
        result1 = await self.agent.query(messages)
        self.assertIn("<taskpaused/>", result1)

        # Second query - agent receives answer and completes
        messages2 = messages.add_user_utterance("Alice")
        result2 = await self.agent.query(messages2)
        self.assertIn("<taskcompleted/>", result2)
        self.assertNotIn("<taskpaused/>", result2)


# Run async tests
def run_async_test(coro):
    """Helper to run async tests."""
    return asyncio.run(coro)


if __name__ == "__main__":
    # Monkey-patch test methods to run async tests
    for test_class in [
        TestWorkflowExecutorPauseDetection,
        TestWorkflowExecutorResume,
        TestUserInputAgentIntegration,
    ]:
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                method = getattr(test_class, method_name)
                if asyncio.iscoroutinefunction(method):
                    # Wrap async method
                    def make_sync_test(async_method):
                        def sync_test(self):
                            return run_async_test(async_method(self))

                        return sync_test

                    setattr(test_class, method_name, make_sync_test(method))

    unittest.main()
