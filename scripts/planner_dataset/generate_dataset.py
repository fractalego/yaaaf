"""
Generate a synthetic dataset of planning scenarios and workflows using GPT-4.

This script creates 1000 diverse planning examples stratified by:
- Number of agents used (2, 3-5, 6+)
- Number of workflow steps
- Agent types and combinations
- Workflow complexity (simple chains vs complex trees)
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import pandas as pd
from openai import OpenAI
from tqdm import tqdm
import yaml
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Agent taxonomy and artifact specifications (copied from repo)
AGENT_TAXONOMIES = {
    "AnswererAgent": {
        "data_flow": "synthesizer",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Combines multiple artifacts into comprehensive answers"
    },
    "BashAgent": {
        "data_flow": "generator",
        "interaction_mode": "interactive",
        "output_permanence": "persistent",
        "description": "Creates effects through filesystem operations"
    },
    "BraveSearchAgent": {
        "data_flow": "extractor",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Pulls data from Brave web search API"
    },
    "DuckDuckGoSearchAgent": {
        "data_flow": "extractor",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Pulls data from DuckDuckGo search API"
    },
    "DocumentRetrieverAgent": {
        "data_flow": "extractor",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Pulls relevant chunks from document collections"
    },
    "MleAgent": {
        "data_flow": "transformer",
        "interaction_mode": "autonomous",
        "output_permanence": "persistent",
        "description": "Analyzes data to extract patterns and create ML models"
    },
    "NumericalSequencesAgent": {
        "data_flow": "transformer",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Reshapes unstructured data into structured tables"
    },
    "ReviewerAgent": {
        "data_flow": "transformer",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Analyzes and validates information"
    },
    "SqlAgent": {
        "data_flow": "extractor",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Pulls data from databases via SQL queries"
    },
    "ToolAgent": {
        "data_flow": "transformer",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Converts instructions into MCP tool calls"
    },
    "UrlAgent": {
        "data_flow": "extractor",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Fetches content from specific URLs"
    },
    "UrlRetrieverAgent": {
        "data_flow": "synthesizer",
        "interaction_mode": "autonomous",
        "output_permanence": "ephemeral",
        "description": "Combines URL content into structured summaries"
    },
    "UserInputAgent": {
        "data_flow": "extractor",
        "interaction_mode": "interactive",
        "output_permanence": "ephemeral",
        "description": "Gathers information from users"
    },
    "VisualizationAgent": {
        "data_flow": "generator",
        "interaction_mode": "autonomous",
        "output_permanence": "persistent",
        "description": "Creates visual artifacts from data"
    },
}

AGENT_ARTIFACT_SPECS = {
    # Source agents (extractors)
    "SqlAgent": {"accepts": [], "produces": ["table"]},
    "DocumentRetrieverAgent": {"accepts": [], "produces": ["text"]},
    "BraveSearchAgent": {"accepts": [], "produces": ["table"]},
    "DuckDuckGoSearchAgent": {"accepts": [], "produces": ["table"]},
    "UrlAgent": {"accepts": [], "produces": ["text"]},
    "UserInputAgent": {"accepts": [], "produces": ["text"]},

    # Transformer agents
    "ReviewerAgent": {"accepts": ["table"], "produces": ["table"]},
    "NumericalSequencesAgent": {"accepts": ["text", "table"], "produces": ["table"]},
    "MleAgent": {"accepts": ["table"], "produces": ["model"]},
    "ToolAgent": {"accepts": ["text"], "produces": ["json", "text"]},

    # Synthesizer agents
    "AnswererAgent": {"accepts": ["table", "text", "model"], "produces": ["table"]},
    "UrlRetrieverAgent": {"accepts": ["text"], "produces": ["table"]},

    # Sink agents (generators)
    "VisualizationAgent": {"accepts": ["table"], "produces": ["image"]},
    "BashAgent": {"accepts": ["text"], "produces": ["text"]},
}


@dataclass
class StratificationBucket:
    """Defines a stratification bucket for generating diverse examples."""
    name: str
    min_agents: int
    max_agents: int
    min_steps: int
    max_steps: int
    complexity: str  # 'simple_chain', 'multi_branch', 'complex_tree'
    target_count: int


@dataclass
class PlanningExample:
    """A single planning example with metadata."""
    scenario: str
    workflow_yaml: str
    agents_used: List[str]
    num_agents: int
    num_steps: int
    complexity: str
    is_valid: bool
    error_message: Optional[str] = None


class PlannerDatasetGenerator:
    """Generates synthetic planning datasets using GPT-4."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        """Initialize the generator.

        Args:
            api_key: OpenAI API key
            model: GPT-4 model to use
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.agent_descriptions = self._create_agent_descriptions()

    def _create_agent_descriptions(self) -> str:
        """Create formatted agent descriptions for the prompt."""
        descriptions = []

        for agent_name, taxonomy in AGENT_TAXONOMIES.items():
            spec = AGENT_ARTIFACT_SPECS.get(agent_name, {"accepts": [], "produces": []})

            desc_parts = [f"{agent_name}:"]
            desc_parts.append(f"  {taxonomy['description']}")

            # Format accepts
            if not spec['accepts']:
                accepts_str = "None (source)"
            else:
                accepts_str = "/".join(spec['accepts'])

            # Format produces
            produces_str = "/".join(spec['produces'])

            desc_parts.append(f"  - Accepts: {accepts_str}")
            desc_parts.append(f"  - Produces: {produces_str}")
            desc_parts.append(f"  - Data Flow: {taxonomy['data_flow']}")
            desc_parts.append(f"  - Interaction: {taxonomy['interaction_mode']}")
            desc_parts.append(f"  - Output: {taxonomy['output_permanence']}")

            descriptions.append("\n".join(desc_parts))

        return "\n\n".join(descriptions)

    def generate_scenario(self, bucket: StratificationBucket) -> str:
        """Generate a realistic scenario using GPT-4.

        Args:
            bucket: Stratification bucket defining constraints

        Returns:
            Generated scenario description
        """
        prompt = f"""Generate a realistic user scenario that would require a workflow with the following characteristics:
- Number of agents needed: {bucket.min_agents} to {bucket.max_agents}
- Number of workflow steps: {bucket.min_steps} to {bucket.max_steps}
- Complexity type: {bucket.complexity}

Available agents:
{self.agent_descriptions}

The scenario should be:
1. Realistic and practical (something a real user might ask)
2. Require multiple agents working together
3. Match the complexity type:
   - simple_chain: Linear sequence of operations (A → B → C)
   - multi_branch: Multiple parallel branches that may converge (A → B, A → C → D)
   - complex_tree: Complex dependency graph with multiple sources and sinks

Generate ONLY the user scenario/query (1-3 sentences). Do not include the workflow plan.
Ensure the scenario naturally requires using agents from different categories (extractors, transformers, generators).

Example scenarios:
- "Analyze our Q4 sales data from the database, validate the numbers, and create an interactive dashboard showing trends by region"
- "Search for recent ML papers on transformers, extract key findings from the top 5 papers, and create a summary report with visualizations"
- "Fetch data from our API endpoint, clean and normalize it, train a prediction model, and visualize the model's performance metrics"

Your scenario:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    def generate_workflow(self, scenario: str, bucket: StratificationBucket) -> str:
        """Generate a workflow plan for the scenario using GPT-4.

        Args:
            scenario: User scenario description
            bucket: Stratification bucket defining constraints

        Returns:
            YAML workflow plan
        """
        planner_prompt = f"""Your task is to create an execution plan as an asset-based workflow that shows how ARTIFACTS flow from sources through transformers to sinks.

You are a planning expert who understands:
1. Agent taxonomies:
   - EXTRACTORS (Sources): Pull data from external sources, produce artifacts
   - TRANSFORMERS (Processors): Transform artifacts into new artifacts
   - SYNTHESIZERS: Combine multiple artifacts into unified artifacts
   - GENERATORS (Sinks): Consume artifacts to create final outputs

2. Artifact types:
   - table: Tabular data (DataFrames)
   - text: Text content (documents, responses)
   - image: Visual outputs (charts, plots)
   - model: Trained ML models
   - json: Structured data

Available agents and their artifact handling:
{self.agent_descriptions}

CRITICAL RULES:
1. You MUST ONLY use the agent names listed above. DO NOT invent agent names.
2. You MUST use the EXACT artifact types from each agent's "Produces" field. DO NOT guess types.
3. If an agent "Produces: table" then you MUST use "type: table" in your plan.
4. If an agent "Produces: image" then you MUST use "type: image" in your plan.
5. NEVER use a type that is not in the agent's "Produces" list.
6. For this workflow, use {bucket.min_agents}-{bucket.max_agents} agents with {bucket.min_steps}-{bucket.max_steps} steps.
7. Create a {bucket.complexity} workflow structure.

Instructions for creating the workflow:
1. Analyze the user's goal to identify the required FINAL ARTIFACT type
2. Work backwards from the sink to determine what artifacts it needs
3. Plan transformation steps that produce the required artifacts
4. Identify source agents that can produce initial artifacts
5. Define dependencies through inputs field

Workflow Format Rules:
- Use YAML asset-based syntax
- Each asset has: name, agent, description, type, inputs (optional), conditions (optional)
- Assets without inputs are source nodes
- Dependencies are explicit through inputs field
- CRITICAL: The "type" field MUST be copied EXACTLY from the agent's "Produces" field (lowercase)
- Include validation and error handling where appropriate

User Scenario:
{scenario}

Generate the workflow plan in YAML format. Output ONLY the YAML workflow wrapped in ```yaml blocks.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": planner_prompt}],
            temperature=0.7,
            max_tokens=1500
        )

        content = response.choices[0].message.content.strip()

        # Extract YAML from code block
        if "```yaml" in content:
            yaml_start = content.find("```yaml") + 7
            yaml_end = content.find("```", yaml_start)
            return content[yaml_start:yaml_end].strip()
        elif "```" in content:
            yaml_start = content.find("```") + 3
            yaml_end = content.find("```", yaml_start)
            return content[yaml_start:yaml_end].strip()
        else:
            return content

    def validate_workflow(self, workflow_yaml: str) -> tuple[bool, Optional[str], List[str], int]:
        """Validate the generated workflow.

        Args:
            workflow_yaml: YAML workflow string

        Returns:
            Tuple of (is_valid, error_message, agents_used, num_steps)
        """
        try:
            workflow_data = yaml.safe_load(workflow_yaml)

            if not isinstance(workflow_data, dict):
                return False, "Invalid workflow format: root must be a dictionary", [], 0

            if "assets" not in workflow_data:
                return False, "Invalid workflow format: missing 'assets' section", [], 0

            assets = workflow_data["assets"]
            if not isinstance(assets, dict):
                return False, "Invalid workflow format: 'assets' must be a dictionary", [], 0

            agents_used = []

            # Validate each asset
            for asset_name, asset_config in assets.items():
                if not isinstance(asset_config, dict):
                    return False, f"Invalid asset '{asset_name}': must be a dictionary", [], 0

                required_fields = ["agent", "description", "type"]
                for field in required_fields:
                    if field not in asset_config:
                        return False, f"Invalid asset '{asset_name}': missing required field '{field}'", [], 0

                agent_name = asset_config["agent"]
                agents_used.append(agent_name)

                # Validate agent exists
                if agent_name not in AGENT_TAXONOMIES:
                    return False, f"Unknown agent '{agent_name}' in asset '{asset_name}'", [], 0

            return True, None, list(set(agents_used)), len(assets)

        except yaml.YAMLError as e:
            return False, f"Invalid YAML format: {str(e)}", [], 0
        except Exception as e:
            return False, f"Error validating workflow: {str(e)}", [], 0

    def generate_example(self, bucket: StratificationBucket) -> PlanningExample:
        """Generate a complete planning example.

        Args:
            bucket: Stratification bucket defining constraints

        Returns:
            PlanningExample instance
        """
        # Generate scenario
        scenario = self.generate_scenario(bucket)

        # Generate workflow
        workflow_yaml = self.generate_workflow(scenario, bucket)

        # Validate workflow
        is_valid, error_message, agents_used, num_steps = self.validate_workflow(workflow_yaml)

        return PlanningExample(
            scenario=scenario,
            workflow_yaml=workflow_yaml,
            agents_used=agents_used,
            num_agents=len(agents_used),
            num_steps=num_steps,
            complexity=bucket.complexity,
            is_valid=is_valid,
            error_message=error_message
        )

    def generate_dataset(
        self,
        total_examples: int = 1000,
        output_path: str = "planner_dataset.parquet"
    ) -> pd.DataFrame:
        """Generate complete stratified dataset.

        Args:
            total_examples: Total number of examples to generate
            output_path: Path to save the Parquet file

        Returns:
            DataFrame with all examples
        """
        # Define stratification buckets
        buckets = [
            # Simple 2-agent workflows
            StratificationBucket(
                name="simple_2agent_chain",
                min_agents=2, max_agents=2,
                min_steps=2, max_steps=2,
                complexity="simple_chain",
                target_count=150
            ),

            # Medium 3-5 agent linear workflows
            StratificationBucket(
                name="medium_chain",
                min_agents=3, max_agents=5,
                min_steps=3, max_steps=5,
                complexity="simple_chain",
                target_count=200
            ),

            # Medium 3-5 agent branching workflows
            StratificationBucket(
                name="medium_branch",
                min_agents=3, max_agents=5,
                min_steps=3, max_steps=6,
                complexity="multi_branch",
                target_count=250
            ),

            # Complex 6+ agent tree workflows
            StratificationBucket(
                name="complex_tree_small",
                min_agents=6, max_agents=8,
                min_steps=6, max_steps=10,
                complexity="complex_tree",
                target_count=200
            ),

            # Very complex 9+ agent tree workflows
            StratificationBucket(
                name="complex_tree_large",
                min_agents=9, max_agents=12,
                min_steps=9, max_steps=15,
                complexity="complex_tree",
                target_count=200
            ),
        ]

        examples = []

        logger.info(f"Generating {total_examples} planning examples...")

        for bucket in buckets:
            logger.info(f"\nGenerating {bucket.target_count} examples for bucket: {bucket.name}")

            for i in tqdm(range(bucket.target_count), desc=bucket.name):
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        example = self.generate_example(bucket)
                        examples.append(example)

                        # Log invalid examples
                        if not example.is_valid:
                            logger.warning(
                                f"Invalid workflow generated: {example.error_message}"
                            )

                        break  # Success, exit retry loop

                    except Exception as e:
                        logger.error(f"Error generating example (attempt {retry+1}/{max_retries}): {e}")
                        if retry == max_retries - 1:
                            # Add a failed example
                            examples.append(PlanningExample(
                                scenario="",
                                workflow_yaml="",
                                agents_used=[],
                                num_agents=0,
                                num_steps=0,
                                complexity=bucket.complexity,
                                is_valid=False,
                                error_message=str(e)
                            ))

        # Convert to DataFrame
        df = pd.DataFrame([asdict(ex) for ex in examples])

        # Add summary statistics
        logger.info("\n=== Dataset Statistics ===")
        logger.info(f"Total examples: {len(df)}")
        logger.info(f"Valid examples: {df['is_valid'].sum()}")
        logger.info(f"Invalid examples: {(~df['is_valid']).sum()}")
        logger.info(f"\nExamples by complexity:")
        logger.info(df['complexity'].value_counts())
        logger.info(f"\nExamples by number of agents:")
        logger.info(df['num_agents'].value_counts().sort_index())

        # Save to Parquet
        df.to_parquet(output_path, index=False)
        logger.info(f"\nDataset saved to: {output_path}")

        return df


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate synthetic planning dataset using GPT-4"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4-turbo-preview",
        help="GPT-4 model to use"
    )
    parser.add_argument(
        "--total",
        type=int,
        default=1000,
        help="Total number of examples to generate"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="planner_dataset.parquet",
        help="Output Parquet file path"
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAI API key required. Set --api-key or OPENAI_API_KEY env var"
        )

    # Generate dataset
    generator = PlannerDatasetGenerator(api_key=api_key, model=args.model)
    df = generator.generate_dataset(
        total_examples=args.total,
        output_path=args.output
    )

    logger.info("\nDataset generation complete!")


if __name__ == "__main__":
    main()
