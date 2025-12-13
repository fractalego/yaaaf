import csv
import logging
from importlib.resources import files
from typing import List, Tuple

from yaaaf.components.retrievers.local_vector_db import BM25LocalDB

_logger = logging.getLogger(__name__)


class PlannerExampleRetriever:
    """Retrieves relevant planner examples from the dataset using BM25."""

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern to avoid reloading the dataset multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if PlannerExampleRetriever._initialized:
            return

        self._vector_db = BM25LocalDB()
        self._id_to_example: dict[str, Tuple[str, str]] = {}  # id -> (scenario, workflow_yaml)
        self._load_dataset()
        PlannerExampleRetriever._initialized = True

    def _load_dataset(self):
        """Load the planner dataset CSV and index all scenarios."""
        try:
            csv_path = files("yaaaf.data").joinpath("planner_dataset.csv")

            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = 0

                for row in reader:
                    scenario = row.get("scenario", "").strip()
                    workflow_yaml = row.get("workflow_yaml", "").strip()

                    if not scenario or not workflow_yaml:
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
                _logger.info(f"Loaded {count} planner examples into BM25 index")

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
