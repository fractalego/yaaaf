import ast
import csv
import hashlib
import logging
from importlib.resources import files
from typing import List, Optional, Set, Tuple

from yaaaf.components.retrievers.local_vector_db import BM25LocalDB

_logger = logging.getLogger(__name__)


class PlannerExampleRetriever:
    """Retrieves relevant planner examples from the dataset using BM25.

    Supports filtering examples by available agents - only examples that use
    a subset of the available agents will be indexed and returned.
    """

    # Cache instances by available_agents hash to avoid reloading
    _instances: dict[str, "PlannerExampleRetriever"] = {}

    def __new__(cls, available_agents: Optional[List[str]] = None):
        """Cache instances by available_agents to avoid reloading the dataset."""
        cache_key = cls._compute_cache_key(available_agents)
        if cache_key not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[cache_key] = instance
        return cls._instances[cache_key]

    @staticmethod
    def _compute_cache_key(available_agents: Optional[List[str]]) -> str:
        """Compute a cache key based on available agents."""
        if available_agents is None:
            return "all"
        sorted_agents = sorted(available_agents)
        return hashlib.md5(",".join(sorted_agents).encode()).hexdigest()

    def __init__(self, available_agents: Optional[List[str]] = None):
        """Initialize the retriever with optional agent filtering.

        Args:
            available_agents: List of available agent class names (e.g., ["BashAgent", "CodeEditAgent"]).
                            If None, all examples are included.
        """
        if getattr(self, "_initialized", False):
            return

        self._available_agents: Optional[Set[str]] = (
            set(available_agents) if available_agents else None
        )
        self._vector_db = BM25LocalDB()
        self._id_to_example: dict[str, Tuple[str, str]] = {}  # id -> (scenario, workflow_yaml)
        self._load_dataset()
        self._initialized = True

    def _parse_agents_used(self, agents_str: str) -> Set[str]:
        """Parse the agents_used column from CSV.

        The column can be in format: "['Agent1', 'Agent2']" or "Agent1,Agent2"
        """
        if not agents_str:
            return set()

        agents_str = agents_str.strip()

        # Try to parse as Python list literal
        if agents_str.startswith("["):
            try:
                agents_list = ast.literal_eval(agents_str)
                return set(agents_list)
            except (ValueError, SyntaxError):
                pass

        # Fallback: split by comma
        return set(a.strip().strip("'\"") for a in agents_str.split(","))

    def _is_example_allowed(self, agents_used: Set[str]) -> bool:
        """Check if an example should be included based on available agents."""
        if self._available_agents is None:
            return True

        # Example is allowed if all its agents are in the available set
        return agents_used.issubset(self._available_agents)

    def _load_dataset(self):
        """Load the planner dataset CSV and index scenarios filtered by available agents."""
        try:
            csv_path = files("yaaaf.data").joinpath("planner_dataset.csv")

            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = 0
                skipped = 0

                for row in reader:
                    scenario = row.get("scenario", "").strip()
                    workflow_yaml = row.get("workflow_yaml", "").strip()
                    agents_used_str = row.get("agents_used", "")

                    if not scenario or not workflow_yaml:
                        continue

                    # Parse and filter by available agents
                    agents_used = self._parse_agents_used(agents_used_str)
                    if not self._is_example_allowed(agents_used):
                        skipped += 1
                        continue

                    # Use row index as ID
                    example_id = str(count)

                    # Index the scenario for retrieval
                    self._vector_db.add_text_and_index(scenario, example_id)

                    # Store the full example
                    self._id_to_example[example_id] = (scenario, workflow_yaml)
                    count += 1

                # Build the BM25 index
                self._vector_db.build()

                if self._available_agents:
                    _logger.info(
                        f"Loaded {count} planner examples into BM25 index "
                        f"(skipped {skipped} due to agent filtering, "
                        f"available: {sorted(self._available_agents)})"
                    )
                else:
                    _logger.info(f"Loaded {count} planner examples into BM25 index (no filtering)")

        except Exception as e:
            _logger.error(f"Failed to load planner dataset: {e}")
            raise

    def get_examples(self, query: str, topn: int = 3) -> List[Tuple[str, str]]:
        """Retrieve the most relevant examples for a query.

        Args:
            query: The user's query/scenario to match against
            topn: Number of examples to retrieve (default: 3)

        Returns:
            List of tuples (scenario, workflow_yaml) for the most relevant examples
        """
        example_ids, _ = self._vector_db.get_indices_from_text(query, topn=topn)

        examples = []
        for example_id in example_ids:
            if example_id in self._id_to_example:
                examples.append(self._id_to_example[example_id])

        return examples

    def format_examples_for_prompt(self, query: str, topn: int = 3) -> str:
        """Retrieve and format examples for inclusion in a prompt.

        Args:
            query: The user's query/scenario to match against
            topn: Number of examples to retrieve (default: 3)

        Returns:
            Formatted string with examples ready for prompt injection
        """
        examples = self.get_examples(query, topn=topn)

        if not examples:
            return "No examples available."

        formatted_parts = []
        for i, (scenario, workflow_yaml) in enumerate(examples, 1):
            formatted_parts.append(
                f"Example {i}:\n"
                f"Scenario: {scenario}\n"
                f"```yaml\n{workflow_yaml}\n```"
            )

        return "\n\n".join(formatted_parts)
