import unittest
from unittest.mock import AsyncMock, MagicMock
import yaml

from yaaaf.components.agents.planner_agent import PlannerAgent
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Utterance, AgentTaxonomy, DataFlow, InteractionMode, OutputPermanence


class TestPlannerAgent(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock(spec=BaseClient)
        self.mock_client.agenerate = AsyncMock()
        
        # Mock available agents with taxonomies
        self.available_agents = [
            {
                "name": "SqlAgent",
                "description": "Executes SQL queries on databases",
                "taxonomy": AgentTaxonomy(
                    data_flow=DataFlow.EXTRACTOR,
                    interaction_mode=InteractionMode.AUTONOMOUS,
                    output_permanence=OutputPermanence.PERSISTENT
                )
            },
            {
                "name": "ReviewerAgent", 
                "description": "Validates data quality and extracts information",
                "taxonomy": AgentTaxonomy(
                    data_flow=DataFlow.TRANSFORMER,
                    interaction_mode=InteractionMode.AUTONOMOUS,
                    output_permanence=OutputPermanence.PERSISTENT
                )
            },
            {
                "name": "VisualizationAgent",
                "description": "Creates charts and visualizations",
                "taxonomy": AgentTaxonomy(
                    data_flow=DataFlow.GENERATOR,
                    interaction_mode=InteractionMode.AUTONOMOUS,
                    output_permanence=OutputPermanence.PERSISTENT
                )
            }
        ]
        
        self.planner_agent = PlannerAgent(self.mock_client, self.available_agents)
    
    def test_planner_agent_initialization(self):
        """Test that planner agent initializes correctly."""
        self.assertEqual(self.planner_agent._output_tag, "```yaml")
        self.assertIn("SqlAgent", self.planner_agent._system_prompt)
        self.assertIn("YAML", self.planner_agent._system_prompt)
        self.assertIn("asset-based workflow", self.planner_agent._system_prompt)
    
    def test_get_info(self):
        """Test agent info description."""
        info = PlannerAgent.get_info()
        self.assertIn("workflow", info.lower())
        self.assertIn("data flow", info.lower())
    
    def test_get_description(self):
        """Test agent description contains YAML information."""
        description = self.planner_agent.get_description()
        self.assertIn("YAML", description)
        self.assertIn("workflow", description)
        self.assertIn("asset-based", description)
    
    async def test_yaml_workflow_generation(self):
        """Test that planner generates valid YAML workflows."""
        # Mock LLM response with valid YAML workflow
        mock_response = """
I'll create a workflow for your data analysis request.

```yaml
assets:
  sales_data:
    agent: SqlAgent
    description: "Extract sales data from database"
    type: TABLE
    validation:
      - row_count > 0
      - columns: [date, sales, region]
    
  validated_data:
    agent: ReviewerAgent
    description: "Validate data quality and clean"
    type: TABLE
    inputs: [sales_data]
    
  sales_visualization:
    agent: VisualizationAgent
    description: "Create sales charts and graphs"
    type: IMAGE
    inputs: [validated_data]
    conditions:
      - if: validated_data.row_count > 1000
        params: {chart_type: "heatmap"}
      - else:
        params: {chart_type: "bar"}
```

This workflow shows the complete data pipeline from extraction to visualization.
        """
        
        self.mock_client.agenerate.return_value = mock_response
        
        # Create test messages
        messages = Messages(
            utterances=[Utterance(role="user", content="Create a sales visualization workflow")]
        )
        
        # Process the request
        result = await self.planner_agent.aprocess(messages)
        
        # Verify the response contains the workflow
        self.assertIsNotNone(result)
        self.assertIn("assets:", result.content)
        
        # Verify YAML is valid and contains expected structure
        yaml_start = result.content.find("```yaml") + 7
        yaml_end = result.content.find("```", yaml_start)
        yaml_content = result.content[yaml_start:yaml_end].strip()
        
        # Parse YAML to verify it's valid
        workflow_data = yaml.safe_load(yaml_content)
        self.assertIn("assets", workflow_data)
        
        assets = workflow_data["assets"]
        self.assertIn("sales_data", assets)
        self.assertIn("validated_data", assets)
        self.assertIn("sales_visualization", assets)
        
        # Verify asset structure
        sales_data = assets["sales_data"]
        self.assertEqual(sales_data["agent"], "SqlAgent")
        self.assertEqual(sales_data["type"], "TABLE")
        self.assertIn("validation", sales_data)
        
        validated_data = assets["validated_data"]
        self.assertEqual(validated_data["agent"], "ReviewerAgent")
        self.assertIn("inputs", validated_data)
        self.assertEqual(validated_data["inputs"], ["sales_data"])
        
        sales_viz = assets["sales_visualization"]
        self.assertEqual(sales_viz["agent"], "VisualizationAgent")
        self.assertEqual(sales_viz["type"], "IMAGE")
        self.assertIn("conditions", sales_viz)
    
    def test_executor_yaml_validation(self):
        """Test that the executor properly validates YAML workflows."""
        from yaaaf.components.executors.planner_executor import PlannerExecutor
        
        executor = PlannerExecutor(self.available_agents)
        
        # Test valid YAML
        valid_yaml = """
assets:
  test_asset:
    agent: SqlAgent
    description: "Test asset"
    type: TABLE
"""
        result, error = self._run_async(executor.execute_operation(valid_yaml, {}))
        self.assertIsNone(error)
        self.assertEqual(result, valid_yaml)
        
        # Test invalid YAML - missing assets
        invalid_yaml = """
invalid_structure:
  test: value
"""
        result, error = self._run_async(executor.execute_operation(invalid_yaml, {}))
        self.assertIsNotNone(error)
        self.assertIn("missing 'assets' section", error)
        
        # Test invalid YAML - missing required fields
        incomplete_yaml = """
assets:
  test_asset:
    agent: SqlAgent
    # missing description and type
"""
        result, error = self._run_async(executor.execute_operation(incomplete_yaml, {}))
        self.assertIsNotNone(error)
        self.assertIn("missing required field", error)
    
    def test_agent_descriptions_include_taxonomy(self):
        """Test that agent descriptions include taxonomy information."""
        descriptions = self.planner_agent._create_agent_descriptions(self.available_agents)
        
        self.assertIn("SqlAgent", descriptions)
        self.assertIn("extractor", descriptions)
        self.assertIn("ReviewerAgent", descriptions) 
        self.assertIn("transformer", descriptions)
        self.assertIn("VisualizationAgent", descriptions)
        self.assertIn("generator", descriptions)
    
    def _run_async(self, coro):
        """Helper to run async code in sync tests."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


if __name__ == '__main__':
    unittest.main()