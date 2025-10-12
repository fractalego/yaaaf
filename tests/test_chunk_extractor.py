import asyncio
import unittest

from yaaaf.components.extractors.chunk_extractor import ChunkExtractor
from yaaaf.components.client import OllamaClient


class TestChunkExtractor(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient(
            model="qwen2.5:32b",
            temperature=0.1,
            max_tokens=500,
        )
        self.extractor = ChunkExtractor(self.client)

        # Sample text for testing
        self.sample_text = """
        Chapter 1: Introduction to Machine Learning
        
        Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed. It focuses on developing algorithms that can analyze data and make predictions or decisions.
        
        Chapter 2: Types of Machine Learning
        
        There are three main types of machine learning: supervised learning, unsupervised learning, and reinforcement learning. Supervised learning uses labeled data to train models, while unsupervised learning finds patterns in unlabeled data.
        
        Chapter 3: Neural Networks
        
        Neural networks are computing systems inspired by biological neural networks. They consist of interconnected nodes that process information using connectionist approaches to computation.
        """

    def test_extract_successful(self):
        """Test successful chunk extraction."""
        result = asyncio.run(
            self.extractor.extract(self.sample_text, "What is machine learning?")
        )

        # Should return a list
        self.assertIsInstance(result, list)

        # Should have at least one result for this query
        self.assertGreater(len(result), 0)

        # Each result should have the required keys
        for chunk in result:
            self.assertIn("relevant_chunk_text", chunk)
            self.assertIn("position_in_document", chunk)
            self.assertIsInstance(chunk["relevant_chunk_text"], str)
            self.assertIsInstance(chunk["position_in_document"], str)
            # Text should not be empty
            self.assertGreater(len(chunk["relevant_chunk_text"].strip()), 0)

    def test_extract_empty_query(self):
        """Test extraction with empty query."""
        result = asyncio.run(self.extractor.extract(self.sample_text, ""))

        # Should return a list (might be empty)
        self.assertIsInstance(result, list)

    def test_extract_irrelevant_query(self):
        """Test extraction with irrelevant query."""
        result = asyncio.run(
            self.extractor.extract(self.sample_text, "What is quantum physics?")
        )

        # Should return a list (likely empty for this irrelevant query)
        self.assertIsInstance(result, list)

    def test_extract_empty_text(self):
        """Test extraction with empty text."""
        result = asyncio.run(self.extractor.extract("", "What is machine learning?"))

        # Should return an empty list
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_get_info(self):
        """Test the get_info static method."""
        info = ChunkExtractor.get_info()
        self.assertIsInstance(info, str)
        self.assertIn("chunk", info.lower())
        self.assertIn("extract", info.lower())


if __name__ == "__main__":
    unittest.main()
