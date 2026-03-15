"""
Generate a synthetic dataset of web-search planning scenarios using GPT-4.

This script creates diverse planning examples using ONLY:
  - BraveSearchAgent: searches the web, produces table (titles, urls, snippets)
  - UrlAgent: fetches content from a specific URL, produces text
  - AnswererAgent: synthesises multiple artifacts into a final answer, produces table

Patterns covered:
  - Multi-search aggregation: several independent BraveSearch calls combined by Answerer
  - Chained search: BraveSearch result feeds UrlAgent to fetch content, then another
    BraveSearch is triggered based on findings (cascading research)
  - Deep research: multiple searches + URL fetches + chained follow-ups + final synthesis
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
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
# Agent definitions (restricted to web-search trio)
# ---------------------------------------------------------------------------

WEB_AGENTS = {
    "BraveSearchAgent": {
        "description": "Searches the web using Brave Search API. Returns a table of results (title, url, snippet).",
        "accepts": [],
        "produces": ["table"],
    },
    "UrlAgent": {
        "description": (
            "Fetches and reads the full content of a specific URL. "
            "Can take a table of search results as input and pick the most relevant URL to visit. "
            "Produces the page content as text."
        ),
        "accepts": ["table"],
        "produces": ["text"],
    },
    "AnswererAgent": {
        "description": (
            "Synthesises multiple artifacts (tables and/or text) into a comprehensive final answer. "
            "Use this as the last step to aggregate all gathered information."
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
    for name, info in WEB_AGENTS.items()
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Bucket:
    name: str
    pattern: str          # 'multi_search' | 'chained_search' | 'deep_research'
    min_searches: int
    max_searches: int
    use_url_agent: bool
    chained: bool         # whether some searches depend on earlier search results
    target_count: int


@dataclass
class PlanningExample:
    scenario: str
    workflow_yaml: str
    agents_used: List[str]
    num_agents: int
    num_steps: int
    complexity: str
    is_valid: bool
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class WebSearchDatasetGenerator:

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
        pattern_hints = {
            "multi_search": (
                "The user needs information that requires MULTIPLE INDEPENDENT web searches "
                "(e.g., comparing several topics, gathering data from different angles) "
                "which are then synthesised into a single answer."
            ),
            "chained_search": (
                "The user asks a question where the answer to a first web search reveals "
                "something that TRIGGERS a follow-up web search or URL visit. "
                "For example: search for 'best ML papers 2024', visit the top result, "
                "then search for the authors' other work based on what was found."
            ),
            "deep_research": (
                "The user wants deep, multi-layered research: several independent searches, "
                "full page reads via URL, and follow-up searches based on findings — "
                "all aggregated into a comprehensive report."
            ),
        }

        prompt = f"""Generate a realistic user query that requires a web research workflow.

Pattern to follow: {pattern_hints[bucket.pattern]}

Constraints:
- The workflow should involve {bucket.min_searches}–{bucket.max_searches} distinct web searches.
- {'Include at least one step where a URL is visited to read the full content of a page.' if bucket.use_url_agent else 'No need to visit specific URLs.'}
- {'Some searches should depend on what was found in earlier searches (cascading/chained).' if bucket.chained else 'Searches can be independent.'}

Available agents: BraveSearchAgent, UrlAgent, AnswererAgent.

Generate ONLY the user query (1–3 sentences). Do not include the workflow plan.

Example queries:
- "Research the current state of fusion energy: find the latest breakthroughs, read the most cited recent article, then search for the companies currently leading in this space."
- "Compare the economic impact of remote work in the US, Europe, and Asia by searching each region separately and synthesising the findings."
- "Find the top 3 Python web frameworks in 2024, visit each framework's homepage to read their feature lists, then search for recent benchmark comparisons between them."

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
        chained_instruction = ""
        if bucket.chained:
            chained_instruction = """
CHAINED SEARCH PATTERN (required for this example):
  At least one BraveSearchAgent step should feed into a UrlAgent (to visit the most
  relevant URL found), and the result of that URL visit should feed into another
  BraveSearchAgent or AnswererAgent.  This represents the "I found X, now let me
  look deeper into X" behaviour.

  Example chained sub-graph:
    initial_search_results:       # BraveSearchAgent, no inputs
    top_article_content:          # UrlAgent, inputs: [initial_search_results]
    followup_search_results:      # BraveSearchAgent — query informed by top_article_content
      inputs: [top_article_content]
"""

        prompt = f"""You are a workflow planning expert for a web-research assistant.

AVAILABLE AGENTS (you MUST use ONLY these three):
{AGENT_DESCRIPTIONS}

ARTIFACT RULES:
- BraveSearchAgent produces: table  (columns: title, url, snippet)
- UrlAgent produces: text           (full page content)
- AnswererAgent produces: table     (final synthesised answer)
- UrlAgent may take a BraveSearchAgent table as input to decide which URL to visit.
- AnswererAgent must be the FINAL step, taking all gathered artifacts as inputs.

WORKFLOW FORMAT (YAML, no markdown):
assets:
  <asset_name>:
    agent: brave_search | url | answerer
    description: "..."
    type: table | text
    inputs: [<asset_name>, ...]   # omit if no inputs
    checks:
      - "<condition>"

NAMING RULES:
- Use descriptive snake_case names (e.g., "fusion_energy_news", "openai_homepage_content").
- BAD: "result1", "data", "output".

ACCEPTANCE CONDITIONS (checks):
- table: row_count >= N, columns: [title, url, snippet], no_empty_values: [title, url]
- text: length > 100, contains_expected_content: true
- final answerer table: row_count >= 1, columns: [summary], no_null_values: [summary]

TARGET FOR THIS EXAMPLE:
- Pattern: {bucket.pattern}
- Number of distinct searches: {bucket.min_searches}–{bucket.max_searches}
- Use UrlAgent: {'yes' if bucket.use_url_agent else 'no'}
{chained_instruction}

USER SCENARIO:
{scenario}

EXAMPLE WORKFLOWS:

Example 1 — multi_search (3 independent searches aggregated):
assets:
  us_remote_work_data:
    agent: brave_search
    description: "Search for economic impact of remote work in the US"
    type: table
    checks:
      - "row_count >= 5"
      - "columns: [title, url, snippet]"

  europe_remote_work_data:
    agent: brave_search
    description: "Search for economic impact of remote work in Europe"
    type: table
    checks:
      - "row_count >= 5"
      - "columns: [title, url, snippet]"

  asia_remote_work_data:
    agent: brave_search
    description: "Search for economic impact of remote work in Asia"
    type: table
    checks:
      - "row_count >= 5"
      - "columns: [title, url, snippet]"

  comparative_report:
    agent: answerer
    description: "Synthesise findings from all three regions into a comparative report"
    type: table
    inputs: [us_remote_work_data, europe_remote_work_data, asia_remote_work_data]
    checks:
      - "row_count >= 1"
      - "columns: [region, key_findings, economic_impact]"

Example 2 — chained_search (search → read URL → follow-up search → synthesise):
assets:
  fusion_breakthrough_search:
    agent: brave_search
    description: "Search for latest fusion energy breakthroughs"
    type: table
    checks:
      - "row_count >= 5"
      - "columns: [title, url, snippet]"

  top_fusion_article:
    agent: url
    description: "Read the most cited recent fusion energy article found in search"
    type: text
    inputs: [fusion_breakthrough_search]
    checks:
      - "length > 200"

  fusion_companies_search:
    agent: brave_search
    description: "Search for leading fusion energy companies based on article findings"
    type: table
    inputs: [top_fusion_article]
    checks:
      - "row_count >= 3"
      - "columns: [title, url, snippet]"

  fusion_research_report:
    agent: answerer
    description: "Combine breakthrough findings and company landscape into a report"
    type: table
    inputs: [fusion_breakthrough_search, top_fusion_article, fusion_companies_search]
    checks:
      - "row_count >= 1"
      - "columns: [summary, key_companies, recent_breakthroughs]"

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
            for name, cfg in assets.items():
                if not isinstance(cfg, dict):
                    return False, f"Asset '{name}' must be a dict", [], 0

                if "external_artifact_id" in cfg:
                    continue  # external reference, skip

                for field in ("agent", "description", "type"):
                    if field not in cfg:
                        return False, f"Asset '{name}' missing field '{field}'", [], 0

                agent = cfg["agent"]
                if agent not in WEB_AGENTS:
                    return False, f"Agent '{agent}' not in allowed set {list(WEB_AGENTS)}", [], 0

                agents_used.append(agent)

            return True, None, list(set(agents_used)), len(assets)

        except yaml.YAMLError as e:
            return False, f"YAML error: {e}", [], 0
        except Exception as e:
            return False, f"Validation error: {e}", [], 0

    # ------------------------------------------------------------------
    # Single example
    # ------------------------------------------------------------------

    def generate_example(self, bucket: Bucket, max_workflow_retries: int = 2) -> PlanningExample:
        scenario = self.generate_scenario(bucket)

        workflow_yaml = ""
        is_valid = False
        error_message = None
        agents_used = []
        num_steps = 0

        for attempt in range(max_workflow_retries + 1):
            workflow_yaml = self.generate_workflow(scenario, bucket)
            is_valid, error_message, agents_used, num_steps = self.validate_workflow(workflow_yaml)
            if is_valid:
                break
            if attempt < max_workflow_retries:
                logger.debug(f"Invalid workflow (attempt {attempt+1}): {error_message}. Retrying…")

        return PlanningExample(
            scenario=scenario,
            workflow_yaml=workflow_yaml,
            agents_used=agents_used,
            num_agents=len(agents_used),
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
        total_examples: int = 1000,
        output_path: str = "websearch_dataset.csv",
        save_debug_info: bool = False,
        max_workflow_retries: int = 2,
    ) -> pd.DataFrame:

        # Stratification: proportions sum to 1.0
        bucket_configs = [
            # Simple: 2 independent searches + Answerer
            Bucket("simple_2search", "multi_search", 2, 2, False, False,
                   int(total_examples * 0.10)),
            # 3–4 independent searches + Answerer
            Bucket("multi_3to4search", "multi_search", 3, 4, False, False,
                   int(total_examples * 0.15)),
            # 4–6 independent searches + Answerer (broad aggregation)
            Bucket("multi_4to6search", "multi_search", 4, 6, False, False,
                   int(total_examples * 0.15)),
            # 2 searches + 1 URL visit + Answerer
            Bucket("search_url_2", "multi_search", 2, 3, True, False,
                   int(total_examples * 0.10)),
            # Simple chained: search → URL → follow-up search → Answerer
            Bucket("chained_simple", "chained_search", 2, 3, True, True,
                   int(total_examples * 0.15)),
            # Chained with extra searches alongside
            Bucket("chained_medium", "chained_search", 3, 4, True, True,
                   int(total_examples * 0.15)),
            # Deep research: 4–6 searches + multiple URL reads + chained follow-ups
            Bucket("deep_research_medium", "deep_research", 4, 5, True, True,
                   int(total_examples * 0.10)),
            Bucket("deep_research_large", "deep_research", 5, 7, True, True,
                   int(total_examples * 0.10)),
        ]

        # Adjust last bucket so total == requested
        generated_total = sum(b.target_count for b in bucket_configs)
        if generated_total < total_examples:
            bucket_configs[-1].target_count += total_examples - generated_total

        examples = []
        failed_workflows = [] if save_debug_info else None

        for bucket in bucket_configs:
            logger.info(f"\nGenerating {bucket.target_count} examples for bucket '{bucket.name}'")
            for _ in tqdm(range(bucket.target_count), desc=bucket.name):
                for attempt in range(3):
                    try:
                        ex = self.generate_example(bucket, max_workflow_retries)
                        examples.append(ex)
                        if not ex.is_valid and save_debug_info:
                            failed_workflows.append({
                                "scenario": ex.scenario,
                                "workflow_yaml": ex.workflow_yaml,
                                "error": ex.error_message,
                                "bucket": bucket.name,
                            })
                        break
                    except Exception as e:
                        logger.error(f"Error on attempt {attempt+1}: {e}")
                        if attempt == 2:
                            examples.append(PlanningExample(
                                scenario="", workflow_yaml="", agents_used=[],
                                num_agents=0, num_steps=0, complexity=bucket.pattern,
                                is_valid=False, error_message=str(e),
                            ))

        df = pd.DataFrame([asdict(ex) for ex in examples])

        logger.info("\n=== Dataset Statistics ===")
        logger.info(f"Total: {len(df)}")
        if len(df) > 0:
            logger.info(f"Valid: {df['is_valid'].sum()}")
            logger.info(f"Invalid: {(~df['is_valid']).sum()}")
            logger.info(f"\nBy complexity:\n{df['complexity'].value_counts()}")

        df.to_csv(output_path, index=False)
        logger.info(f"\nSaved to: {output_path}")

        if save_debug_info and failed_workflows:
            debug_path = output_path.replace(".csv", "_debug.json")
            with open(debug_path, "w") as f:
                json.dump(failed_workflows, f, indent=2)
            logger.info(f"Debug info saved to: {debug_path}")

        return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a web-search focused planning dataset (BraveSearch + URL + Answerer)."
    )
    parser.add_argument("--api-key", type=str, default=None,
                        help="OpenAI API key (or set OPENAI_API_KEY)")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--total", type=int, default=1000,
                        help="Total number of examples to generate")
    parser.add_argument("--output", type=str, default="websearch_dataset.csv")
    parser.add_argument("--debug", action="store_true",
                        help="Save failed workflows to a debug JSON file")
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

    gen = WebSearchDatasetGenerator(
        api_key=api_key,
        model=args.model,
        scenario_temperature=args.scenario_temperature,
        workflow_temperature=args.workflow_temperature,
    )

    gen.generate_dataset(
        total_examples=args.total,
        output_path=args.output,
        save_debug_info=args.debug,
        max_workflow_retries=args.max_retries,
    )

    logger.info("Done.")


if __name__ == "__main__":
    main()
