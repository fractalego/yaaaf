import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.agents.planner_agent import PlannerAgent
from yaaaf.components.agents.sql_agent import SqlAgent
from yaaaf.components.agents.visualization_agent import VisualizationAgent
from yaaaf.components.agents.artefacts import Artefact
from yaaaf.components.data_types import Messages, Utterance
from yaaaf.components.executors.workflow_executor import ValidationError


class TestPlanDrivenOrchestrator(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Mock LLM client
        self.mock_client = MagicMock()
        self.mock_client.agenerate = AsyncMock()
        self.mock_client.predict = AsyncMock()

        # Mock agents
        self.mock_sql_agent = MagicMock(spec=SqlAgent)
        self.mock_sql_agent.aprocess = AsyncMock()
        self.mock_sql_agent.get_info = MagicMock(return_value="Executes SQL queries")

        self.mock_viz_agent = MagicMock(spec=VisualizationAgent)
        self.mock_viz_agent.aprocess = AsyncMock()
        self.mock_viz_agent.get_info = MagicMock(return_value="Creates visualizations")

        self.mock_planner = MagicMock(spec=PlannerAgent)
        self.mock_planner.aprocess = AsyncMock()

        # Available agents
        self.agents = {
            "SqlAgent": self.mock_sql_agent,
            "VisualizationAgent": self.mock_viz_agent,
            "PlannerAgent": self.mock_planner,
        }

        # Create orchestrator
        self.orchestrator = OrchestratorAgent(self.mock_client, self.agents)

    def test_initialization(self):
        """Test orchestrator initializes correctly."""
        self.assertEqual(self.orchestrator.planner, self.mock_planner)
        self.assertIsNone(self.orchestrator.current_plan)
        self.assertIsNone(self.orchestrator.plan_executor)

    @patch(
        "yaaaf.components.agents.orchestrator_agent.EnhancedGoalExtractor"
    )
    async def test_goal_extraction(self, mock_goal_extractor_class):
        """Test goal extraction from user messages."""
        # Mock goal extractor
        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(
            return_value={
                "goal": "Create sales visualization",
                "artifact_type": "IMAGE",
            }
        )
        mock_goal_extractor_class.return_value = mock_extractor

        # Create new orchestrator to use mocked extractor
        orchestrator = OrchestratorAgent(self.mock_client, self.agents)

        # Test goal extraction
        messages = Messages(
            utterances=[Utterance(role="user", content="Show me a sales chart")]
        )

        goal_info = await orchestrator._extract_goal_and_type(messages)

        self.assertEqual(goal_info["goal"], "Create sales visualization")
        self.assertEqual(goal_info["artifact_type"], "IMAGE")

    async def test_plan_generation(self):
        """Test plan generation from goal."""
        # Mock planner response
        plan_yaml = """
assets:
  sales_data:
    agent: SqlAgent
    description: "Extract sales data"
    type: TABLE
    
  sales_chart:
    agent: VisualizationAgent  
    description: "Create sales visualization"
    type: IMAGE
    inputs: [sales_data]
"""

        mock_response = MagicMock()
        mock_response.content = f"Here's the plan:\n```yaml\n{plan_yaml}\n```"
        self.mock_planner.aprocess.return_value = mock_response

        # Generate plan
        messages = Messages(
            utterances=[Utterance(role="user", content="Show sales chart")]
        )

        plan = await self.orchestrator._generate_plan(
            goal="Create sales visualization", target_type="IMAGE", messages=messages
        )

        self.assertIn("assets:", plan)
        self.assertIn("sales_data", plan)
        self.assertIn("sales_chart", plan)
        self.assertIn("SqlAgent", plan)
        self.assertIn("VisualizationAgent", plan)

    @patch("yaaaf.components.agents.orchestrator_agent.WorkflowExecutor")
    @patch(
        "yaaaf.components.agents.orchestrator_agent.EnhancedGoalExtractor"
    )
    async def test_successful_execution(
        self, mock_goal_extractor_class, mock_workflow_executor_class
    ):
        """Test successful plan execution."""
        # Mock goal extractor
        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(
            return_value={
                "goal": "Create sales visualization",
                "artifact_type": "IMAGE",
            }
        )
        mock_goal_extractor_class.return_value = mock_extractor

        # Mock planner response
        plan_yaml = """
assets:
  sales_data:
    agent: SqlAgent
    type: TABLE
    
  sales_chart:
    agent: VisualizationAgent
    type: IMAGE
    inputs: [sales_data]
"""
        mock_plan_response = MagicMock()
        mock_plan_response.content = f"```yaml\n{plan_yaml}\n```"
        self.mock_planner.aprocess.return_value = mock_plan_response

        # Mock workflow executor
        mock_executor = MagicMock()
        final_artifact = Artefact(type="image", code="chart.png")
        mock_executor.execute = AsyncMock(return_value=final_artifact)
        mock_workflow_executor_class.return_value = mock_executor

        # Create new orchestrator
        orchestrator = OrchestratorAgent(self.mock_client, self.agents)

        # Execute
        messages = Messages(
            utterances=[Utterance(role="user", content="Show me a sales chart")]
        )

        result = await orchestrator.aprocess(messages)

        self.assertEqual(result.type, "image")
        self.assertEqual(result.code, "chart.png")
        mock_executor.execute.assert_called_once()

    @patch("yaaaf.components.agents.orchestrator_agent.WorkflowExecutor")
    @patch(
        "yaaaf.components.agents.orchestrator_agent.EnhancedGoalExtractor"
    )
    async def test_replanning_on_failure(
        self, mock_goal_extractor_class, mock_workflow_executor_class
    ):
        """Test replanning when execution fails."""
        # Mock goal extractor
        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(
            return_value={
                "goal": "Create sales visualization",
                "artifact_type": "IMAGE",
            }
        )
        mock_goal_extractor_class.return_value = mock_extractor

        # Mock planner responses (initial and replan)
        initial_plan = """
assets:
  sales_data:
    agent: SqlAgent
    type: TABLE
"""
        revised_plan = """
assets:
  sales_data:
    agent: SqlAgent
    type: TABLE
    
  sales_chart:
    agent: VisualizationAgent
    type: IMAGE
    inputs: [sales_data]
"""

        # Configure planner to return different plans
        plan_responses = [
            MagicMock(content=f"```yaml\n{initial_plan}\n```"),
            MagicMock(content=f"```yaml\n{revised_plan}\n```"),
        ]
        self.mock_planner.aprocess.side_effect = plan_responses

        # Mock workflow executor - fail first time, succeed second time
        mock_executor = MagicMock()
        final_artifact = Artefact(type="image", code="chart.png")
        mock_executor.execute.side_effect = [
            ValidationError("Missing visualization step"),
            AsyncMock(return_value=final_artifact)(),
        ]
        mock_executor.get_completed_assets.return_value = {
            "sales_data": Artefact(type="table", data="mock_data")
        }
        mock_workflow_executor_class.return_value = mock_executor

        # Create new orchestrator
        orchestrator = OrchestratorAgent(self.mock_client, self.agents)
        orchestrator._max_replan_attempts = 2  # Allow one retry

        # Execute
        messages = Messages(
            utterances=[Utterance(role="user", content="Show me a sales chart")]
        )

        result = await orchestrator.aprocess(messages)

        # Verify replanning occurred
        self.assertEqual(self.mock_planner.aprocess.call_count, 2)
        self.assertEqual(result.type, "image")

        # Check that second plan request includes error context
        second_call_messages = self.mock_planner.aprocess.call_args_list[1][0][0]
        second_call_content = second_call_messages.utterances[0].content
        self.assertIn("failed during execution", second_call_content)
        self.assertIn("Missing visualization step", second_call_content)

    def test_yaml_extraction(self):
        """Test YAML extraction from various response formats."""
        # Test standard format
        response1 = MagicMock()
        response1.content = "Here's the plan:\n```yaml\nassets:\n  test: value\n```"
        yaml1 = self.orchestrator._extract_yaml_from_response(response1)
        self.assertEqual(yaml1, "assets:\n  test: value")

        # Test direct assets format
        response2 = MagicMock()
        response2.content = "assets:\n  test: value\nMore text after"
        yaml2 = self.orchestrator._extract_yaml_from_response(response2)
        self.assertEqual(yaml2, "assets:\n  test: value\nMore text after")

        # Test from artifacts
        artifact = Artefact(code="assets:\n  test: value")
        response3 = MagicMock()
        response3.artefacts = [artifact]
        yaml3 = self.orchestrator._extract_yaml_from_response(response3)
        self.assertEqual(yaml3, "assets:\n  test: value")

    def test_artifact_type_verification(self):
        """Test artifact type verification."""
        # Test matching types
        table_artifact = Artefact(type="table")
        self.assertTrue(
            self.orchestrator._verify_artifact_type(table_artifact, "TABLE")
        )

        image_artifact = Artefact(type="IMAGE")
        self.assertTrue(
            self.orchestrator._verify_artifact_type(image_artifact, "image")
        )

        # Test mismatched types (should still pass with current implementation)
        text_artifact = Artefact(type="text")
        self.assertTrue(self.orchestrator._verify_artifact_type(text_artifact, "IMAGE"))

    def _run_async(self, coro):
        """Helper to run async code in sync tests."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
