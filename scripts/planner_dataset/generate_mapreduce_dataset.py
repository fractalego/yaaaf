"""
Generate a synthetic dataset of map-reduce (for_each) planning scenarios using GPT-4.

Each example contains:
  - A realistic user query that benefits from per-row processing
  - A YAML workflow that uses the for_each construct

Patterns covered:
  - search_then_fetch: BraveSearch → for_each(url) → answerer
  - sql_then_process: sql → for_each(sub-agent) → answerer
  - multi_source_then_fetch: multiple BraveSearch → for_each(url) → answerer
  - deep_per_row: for_each with 2-step row_chain → answerer
"""

import os
import json
import logging
from typing import List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
from openai import OpenAI
from tqdm import tqdm
import yaml
import random

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent definitions (the ones usable inside for_each row_chains)
# ---------------------------------------------------------------------------

AGENTS = {
    "brave_search": {
        "description": "Searches the web using Brave Search API. Returns a table (title, url, snippet).",
        "accepts": [],
        "produces": ["table"],
    },
    "url": {
        "description": (
            "Fetches and reads the full content of a specific URL. "
            "Can take a table (e.g. search results) as input to pick the most relevant URL. "
            "Produces page content as text."
        ),
        "accepts": ["table"],
        "produces": ["text"],
    },
    "sql": {
        "description": "Executes SQL queries against a database. Produces a table.",
        "accepts": [],
        "produces": ["table"],
    },
    "answerer": {
        "description": (
            "Synthesises multiple artifacts (tables and/or text) into a comprehensive final answer. "
            "Always the last step. Produces a table."
        ),
        "accepts": ["table", "text"],
        "produces": ["table"],
    },
}

AGENT_DESCRIPTIONS = "\n\n".join(
    f"{name}:\n"
    f"  {info['description']}\n"
    f"  - Accepts: {'/'.join(info['accepts']) if info['accepts'] else 'None (source)'}\n"
    f"  - Produces: {'/'.join(info['produces'])}"
    for name, info in AGENTS.items()
)

FOR_EACH_SYNTAX = """
FOR-EACH NODE SYNTAX (type: for_each):
  <node_name>:
    type: for_each          # identifies this as a map-reduce node (NO 'agent' field)
    description: "..."
    inputs: [<table_asset>]  # the table to iterate over, one row at a time
    row_output: <asset_name_inside_row_chain>
    row_chain:
      assets:
        <asset_name>:
          agent: <agent>
          description: "..."
          type: <type>
          inputs: [__row__]   # __row__ is the current single-row table

Rules:
- type: for_each nodes do NOT have an 'agent' field
- inputs must reference a table asset
- row_chain must have an 'assets' key
- row_output must name one of the assets inside row_chain
- __row__ inside row_chain refers to the current row (a single-row table)
- All row results are concatenated into one table artifact
- answerer must be the LAST step in the outer workflow, taking the for_each node as input
"""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Bucket:
    name: str
    pattern: str
    description: str
    target_count: int


@dataclass
class PlanningExample:
    scenario: str
    workflow_yaml: str
    agents_used: List[str]
    num_steps: int
    complexity: str
    is_valid: bool
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class MapReduceDatasetGenerator:

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        scenario_temperature: float = 0.9,
        workflow_temperature: float = 0.7,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.scenario_temperature = scenario_temperature
        self.workflow_temperature = workflow_temperature

    # ------------------------------------------------------------------
    # Scenario generation
    # ------------------------------------------------------------------

    def generate_scenario(self, bucket: Bucket) -> str:
        prompt = f"""Generate a realistic user query that requires a workflow using this pattern:

Pattern: {bucket.pattern}
Description: {bucket.description}

The query must clearly require processing MULTIPLE ITEMS one by one — for example:
- For each URL in a list, fetch and analyse its content
- For each company in a result set, run an additional search
- For each row in a SQL result, fetch detailed data from the web

Generate ONLY the user query (1–3 sentences). Do not include a plan.

Example queries:
- "Find the top 5 AI research labs, then visit each lab's homepage and extract their latest published papers."
- "Get all companies in our database that are in the tech sector, then for each company search the web for their latest news."
- "Search for the most popular open-source LLMs, then visit each project's GitHub page to read their README."

Your query:"""

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.scenario_temperature,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()

    # ------------------------------------------------------------------
    # Workflow generation
    # ------------------------------------------------------------------

    def generate_workflow(self, scenario: str, bucket: Bucket) -> str:
        pattern_instructions = {
            "search_then_fetch": (
                "1. Use brave_search to get a list of items (table).\n"
                "2. Use for_each to visit each URL found (url agent in row_chain).\n"
                "3. Use answerer to synthesise all fetched content."
            ),
            "sql_then_process": (
                "1. Use sql to retrieve a table of items from the database.\n"
                "2. Use for_each to search the web for additional info on each row (brave_search in row_chain).\n"
                "3. Use answerer to synthesise."
            ),
            "multi_search_then_fetch": (
                "1. Use 2-3 independent brave_search steps to collect multiple tables.\n"
                "2. Use for_each on one of the search results to fetch each URL.\n"
                "3. Use answerer to combine all artifacts."
            ),
            "deep_per_row": (
                "1. Use brave_search to get an initial table.\n"
                "2. Use for_each with a 2-step row_chain: first fetch the URL (url agent), "
                "then search for more details (brave_search agent) based on what was found.\n"
                "3. Use answerer to synthesise."
            ),
        }

        prompt = f"""You are a workflow planning expert for a research assistant.

AVAILABLE AGENTS:
{AGENT_DESCRIPTIONS}

{FOR_EACH_SYNTAX}

WORKFLOW FORMAT (YAML, no markdown fences):
assets:
  <asset_name>:
    agent: brave_search | url | sql | answerer
    description: "..."
    type: table | text
    inputs: [<asset_name>, ...]   # omit if no inputs

NAMING RULES:
- Use descriptive snake_case names.
- BAD: "result1", "data", "output".

TARGET PATTERN: {bucket.pattern}
Steps to follow:
{pattern_instructions.get(bucket.pattern, '')}

USER SCENARIO:
{scenario}

EXAMPLE WORKFLOW (search_then_fetch pattern):
assets:
  framework_search:
    agent: brave_search
    description: "Search for the top Python web frameworks"
    type: table

  framework_homepages:
    type: for_each
    description: "Fetch each framework's homepage to read its features"
    inputs: [framework_search]
    row_output: homepage_content
    row_chain:
      assets:
        homepage_content:
          agent: url
          description: "Visit the URL from this search result row"
          type: text
          inputs: [__row__]

  final_comparison:
    agent: answerer
    description: "Compare all frameworks based on their homepage content"
    type: table
    inputs: [framework_homepages]

Now generate the workflow for the scenario above.
Output ONLY valid YAML starting with "assets:". No markdown, no explanations."""

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a workflow planning expert. Output ONLY valid YAML.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.workflow_temperature,
            max_tokens=1500,
        )

        content = resp.choices[0].message.content.strip()

        # Strip markdown fences if present
        for fence in ("```yaml", "```"):
            if fence in content:
                start = content.find(fence) + len(fence)
                end = content.find("```", start)
                content = content[start:end].strip()
                break

        if not content.startswith("assets:") and "assets:" in content:
            content = content[content.find("assets:"):]

        return content

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_workflow(self, workflow_yaml: str):
        """Return (is_valid, error_message, agents_used, num_steps)."""
        try:
            data = yaml.safe_load(workflow_yaml)
            if not isinstance(data, dict) or "assets" not in data:
                return False, "Missing 'assets' section", [], 0

            assets = data["assets"]
            if not isinstance(assets, dict):
                return False, "'assets' must be a dict", [], 0

            agents_used = []
            has_for_each = False
            has_answerer = False
            last_asset_name = list(assets.keys())[-1]

            for name, cfg in assets.items():
                if not isinstance(cfg, dict):
                    return False, f"Asset '{name}' must be a dict", [], 0

                if "external_artifact_id" in cfg:
                    continue

                asset_type = cfg.get("type")

                if asset_type == "for_each":
                    has_for_each = True
                    for field in ("type", "description", "row_chain", "row_output"):
                        if field not in cfg:
                            return False, f"for_each '{name}' missing field '{field}'", [], 0
                    row_chain = cfg.get("row_chain", {})
                    if not isinstance(row_chain, dict) or "assets" not in row_chain:
                        return False, f"for_each '{name}' row_chain must have 'assets'", [], 0
                    row_output = cfg.get("row_output")
                    if row_output not in row_chain.get("assets", {}):
                        return False, f"for_each '{name}' row_output '{row_output}' not in row_chain", [], 0
                else:
                    for field in ("agent", "description", "type"):
                        if field not in cfg:
                            return False, f"Asset '{name}' missing field '{field}'", [], 0
                    agent = cfg["agent"]
                    if agent not in AGENTS:
                        return False, f"Agent '{agent}' not in allowed set {list(AGENTS)}", [], 0
                    agents_used.append(agent)
                    if agent == "answerer":
                        has_answerer = True

            if not has_for_each:
                return False, "Workflow must contain at least one for_each node", [], 0

            if not has_answerer:
                return False, "Workflow must end with an answerer node", [], 0

            last_cfg = assets[last_asset_name]
            if last_cfg.get("agent") != "answerer":
                return False, f"Last node '{last_asset_name}' must be the answerer", [], 0

            return True, None, list(set(agents_used)), len(assets)

        except yaml.YAMLError as e:
            return False, f"YAML error: {e}", [], 0
        except Exception as e:
            return False, f"Validation error: {e}", [], 0

    # ------------------------------------------------------------------
    # Single example
    # ------------------------------------------------------------------

    def generate_example(self, bucket: Bucket, max_retries: int = 2) -> PlanningExample:
        scenario = self.generate_scenario(bucket)

        workflow_yaml = ""
        is_valid = False
        error_message = None
        agents_used = []
        num_steps = 0

        for attempt in range(max_retries + 1):
            workflow_yaml = self.generate_workflow(scenario, bucket)
            is_valid, error_message, agents_used, num_steps = self.validate_workflow(workflow_yaml)
            if is_valid:
                break
            if attempt < max_retries:
                logger.debug(f"Invalid (attempt {attempt + 1}): {error_message}. Retrying…")

        return PlanningExample(
            scenario=scenario,
            workflow_yaml=workflow_yaml,
            agents_used=agents_used,
            num_steps=num_steps,
            complexity=bucket.pattern,
            is_valid=is_valid,
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # Full dataset
    # ------------------------------------------------------------------

    def generate_dataset(
        self,
        total_examples: int = 200,
        output_path: str = "mapreduce_dataset.csv",
        max_retries: int = 2,
    ) -> pd.DataFrame:

        bucket_configs = [
            Bucket(
                "search_then_fetch",
                "search_then_fetch",
                "BraveSearch returns a table; for_each fetches each URL; answerer synthesises.",
                int(total_examples * 0.35),
            ),
            Bucket(
                "sql_then_process",
                "sql_then_process",
                "SQL returns a table of entities; for_each searches the web for each; answerer synthesises.",
                int(total_examples * 0.20),
            ),
            Bucket(
                "multi_search_then_fetch",
                "multi_search_then_fetch",
                "Multiple independent searches; for_each fetches URLs from one of them; answerer combines all.",
                int(total_examples * 0.25),
            ),
            Bucket(
                "deep_per_row",
                "deep_per_row",
                "Search → for_each with a 2-step row_chain (fetch URL then follow-up search) → answerer.",
                int(total_examples * 0.20),
            ),
        ]

        # Adjust last bucket so counts sum to total
        allocated = sum(b.target_count for b in bucket_configs)
        if allocated < total_examples:
            bucket_configs[-1].target_count += total_examples - allocated

        examples = []

        for bucket in bucket_configs:
            logger.info(f"\nGenerating {bucket.target_count} examples for '{bucket.name}'")
            for _ in tqdm(range(bucket.target_count), desc=bucket.name):
                for attempt in range(3):
                    try:
                        ex = self.generate_example(bucket, max_retries)
                        examples.append(ex)
                        break
                    except Exception as e:
                        logger.error(f"Error on attempt {attempt + 1}: {e}")
                        if attempt == 2:
                            examples.append(PlanningExample(
                                scenario="",
                                workflow_yaml="",
                                agents_used=[],
                                num_steps=0,
                                complexity=bucket.pattern,
                                is_valid=False,
                                error_message=str(e),
                            ))

        df = pd.DataFrame([asdict(ex) for ex in examples])

        logger.info("\n=== Dataset Statistics ===")
        logger.info(f"Total: {len(df)}")
        if len(df) > 0:
            logger.info(f"Valid: {df['is_valid'].sum()}")
            logger.info(f"Invalid: {(~df['is_valid']).sum()}")
            logger.info(f"\nBy pattern:\n{df['complexity'].value_counts()}")

        df.to_csv(output_path, index=False)
        logger.info(f"\nSaved to: {output_path}")

        return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a map-reduce (for_each) planning dataset."
    )
    parser.add_argument("--api-key", type=str, default=None,
                        help="OpenAI API key (or set OPENAI_API_KEY)")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--total", type=int, default=200,
                        help="Total number of examples to generate")
    parser.add_argument("--output", type=str, default="mapreduce_dataset.csv")
    parser.add_argument("--scenario-temperature", type=float, default=0.9)
    parser.add_argument("--workflow-temperature", type=float, default=0.7)
    parser.add_argument("--max-retries", type=int, default=2)

    args = parser.parse_args()

    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key required. Set --api-key or OPENAI_API_KEY env var.")

    logger.info(f"Model: {args.model}")
    logger.info(f"Total examples: {args.total}")
    logger.info(f"Output: {args.output}")

    gen = MapReduceDatasetGenerator(
        api_key=api_key,
        model=args.model,
        scenario_temperature=args.scenario_temperature,
        workflow_temperature=args.workflow_temperature,
    )

    gen.generate_dataset(
        total_examples=args.total,
        output_path=args.output,
        max_retries=args.max_retries,
    )

    logger.info("Done.")


if __name__ == "__main__":
    main()
