"""Test TF-IDF example retrieval for PlannerAgent."""

import unittest
from yaaaf.components.agents.planner_example_retriever import PlannerExampleRetriever


class TestPlannerExampleRetrieval(unittest.TestCase):
    """Test the TF-IDF-based example retrieval system."""

    def setUp(self):
        """Set up test fixtures."""
        # Use bundled dataset
        self.retriever = PlannerExampleRetriever(top_k=3)

    def test_retriever_initialization(self):
        """Test that retriever initializes and loads dataset."""
        self.assertIsNotNone(self.retriever.dataset)
        self.assertGreater(len(self.retriever.dataset), 0)
        self.assertIsNotNone(self.retriever.vectorizer)
        self.assertIsNotNone(self.retriever.tfidf_matrix)

    def test_retrieve_sales_examples(self):
        """Test retrieval for sales-related query."""
        query = "Analyze sales data from database and create visualization"

        examples = self.retriever.retrieve_examples(query)

        self.assertEqual(len(examples), 3)
        self.assertTrue(all(isinstance(ex, tuple) for ex in examples))
        self.assertTrue(all(len(ex) == 2 for ex in examples))

        # Print retrieved examples for inspection
        print("\n=== Sales Query Examples ===")
        for i, (scenario, workflow) in enumerate(examples, 1):
            print(f"\nExample {i}:")
            print(f"Scenario: {scenario[:100]}...")
            self.assertTrue(len(scenario) > 0)
            self.assertTrue(len(workflow) > 0)
            self.assertIn("assets:", workflow.lower())

    def test_retrieve_ml_examples(self):
        """Test retrieval for ML-related query."""
        query = "Train a machine learning model to predict customer churn"

        examples = self.retriever.retrieve_examples(query)

        self.assertEqual(len(examples), 3)

        print("\n=== ML Query Examples ===")
        for i, (scenario, workflow) in enumerate(examples, 1):
            print(f"\nExample {i}:")
            print(f"Scenario: {scenario[:100]}...")

    def test_retrieve_search_examples(self):
        """Test retrieval for web search query."""
        query = "Search for recent news about AI and summarize findings"

        examples = self.retriever.retrieve_examples(query)

        self.assertEqual(len(examples), 3)

        print("\n=== Search Query Examples ===")
        for i, (scenario, workflow) in enumerate(examples, 1):
            print(f"\nExample {i}:")
            print(f"Scenario: {scenario[:100]}...")

    def test_format_examples_for_prompt(self):
        """Test formatting of examples for prompt injection."""
        query = "Analyze customer data"
        examples = self.retriever.retrieve_examples(query)

        formatted = self.retriever.format_examples_for_prompt(examples)

        self.assertIsInstance(formatted, str)
        self.assertIn("Example 1", formatted)
        self.assertIn("```yaml", formatted)
        self.assertIn("assets:", formatted)

        print("\n=== Formatted Examples ===")
        print(formatted[:500])

    def test_retrieval_consistency(self):
        """Test that same query returns same examples."""
        query = "Create a data analysis workflow"

        examples1 = self.retriever.retrieve_examples(query)
        examples2 = self.retriever.retrieve_examples(query)

        self.assertEqual(len(examples1), len(examples2))
        # Should return same examples for same query
        for (s1, w1), (s2, w2) in zip(examples1, examples2):
            self.assertEqual(s1, s2)
            self.assertEqual(w1, w2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
