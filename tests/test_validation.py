"""Tests for the validation system."""

import unittest
import pandas as pd

from yaaaf.components.validators.validation_result import ValidationResult
from yaaaf.components.validators.artifact_inspector import (
    inspect_artifact,
    inspect_table,
    inspect_text,
    inspect_image,
    inspect_model,
)
from yaaaf.components.agents.artefacts import Artefact


class TestValidationResult(unittest.TestCase):
    """Tests for ValidationResult dataclass."""

    def test_valid_result_creation(self):
        """Test creating a valid result."""
        result = ValidationResult.valid(reason="Test reason", asset_name="test_asset")
        self.assertTrue(result.is_valid)
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.reason, "Test reason")
        self.assertFalse(result.should_ask_user)
        self.assertEqual(result.asset_name, "test_asset")

    def test_invalid_replan_result(self):
        """Test creating an invalid result that triggers replan."""
        result = ValidationResult.invalid_replan(
            reason="Wrong data",
            suggested_fix="Try different source",
            confidence=0.4,
            asset_name="test_asset",
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.confidence, 0.4)
        self.assertEqual(result.suggested_fix, "Try different source")
        self.assertTrue(result.should_replan)

    def test_invalid_ask_user_result(self):
        """Test creating an invalid result that requires user input."""
        result = ValidationResult.invalid_ask_user(
            reason="Cannot determine intent", asset_name="test_asset"
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.confidence, 0.1)
        self.assertTrue(result.should_ask_user)
        self.assertFalse(result.should_replan)

    def test_should_replan_property(self):
        """Test the should_replan property."""
        # Valid result should not trigger replan
        valid = ValidationResult.valid()
        self.assertFalse(valid.should_replan)

        # Invalid with high confidence should not trigger replan
        high_conf = ValidationResult(
            is_valid=False,
            confidence=0.8,
            reason="Minor issue",
            should_ask_user=False,
        )
        self.assertFalse(high_conf.should_replan)

        # Invalid with low confidence should trigger replan
        low_conf = ValidationResult(
            is_valid=False,
            confidence=0.4,
            reason="Major issue",
            should_ask_user=False,
        )
        self.assertTrue(low_conf.should_replan)

        # Should ask user takes precedence over replan
        ask_user = ValidationResult(
            is_valid=False,
            confidence=0.2,
            reason="Need user input",
            should_ask_user=True,
        )
        self.assertFalse(ask_user.should_replan)

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = ValidationResult(
            is_valid=False,
            confidence=0.6,
            reason="Test reason",
            should_ask_user=False,
            suggested_fix="Try again",
            asset_name="test_asset",
        )

        data = original.to_dict()
        restored = ValidationResult.from_dict(data)

        self.assertEqual(restored.is_valid, original.is_valid)
        self.assertEqual(restored.confidence, original.confidence)
        self.assertEqual(restored.reason, original.reason)
        self.assertEqual(restored.should_ask_user, original.should_ask_user)
        self.assertEqual(restored.suggested_fix, original.suggested_fix)
        self.assertEqual(restored.asset_name, original.asset_name)

    def test_automatic_should_ask_user(self):
        """Test that should_ask_user is set automatically for very low confidence."""
        result = ValidationResult(
            is_valid=False,
            confidence=0.2,  # Below ASK_USER_THRESHOLD
            reason="Very wrong",
            should_ask_user=False,  # Will be overridden
        )
        self.assertTrue(result.should_ask_user)


class TestArtifactInspector(unittest.TestCase):
    """Tests for artifact inspection utilities."""

    def test_inspect_table_artifact(self):
        """Test inspecting a table artifact."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob", "Charlie"],
            "age": [25, 30, 35],
            "city": ["NYC", "LA", "Chicago"],
        })
        artifact = Artefact(
            type=Artefact.Types.TABLE,
            data=df,
            description="Test table",
        )

        result = inspect_table(artifact)

        self.assertIn("**Schema:**", result)
        self.assertIn("Rows: 3", result)
        self.assertIn("Columns: 3", result)
        self.assertIn("name", result)
        self.assertIn("age", result)
        self.assertIn("Alice", result)

    def test_inspect_table_limits_rows(self):
        """Test that table inspection limits rows to 20."""
        df = pd.DataFrame({
            "id": range(100),
            "value": range(100),
        })
        artifact = Artefact(
            type=Artefact.Types.TABLE,
            data=df,
            description="Large table",
        )

        result = inspect_table(artifact)

        # Should show first 20 rows info
        self.assertIn("First 20 rows", result)
        # Should not contain row 50 data
        self.assertNotIn("50 |", result)

    def test_inspect_text_artifact(self):
        """Test inspecting a text artifact."""
        artifact = Artefact(
            type=Artefact.Types.TEXT,
            code="SELECT * FROM users",
            description="SQL query",
        )

        result = inspect_text(artifact)
        self.assertIn("SELECT * FROM users", result)

    def test_inspect_text_truncation(self):
        """Test that long text is truncated."""
        long_text = "x" * 5000  # More than MAX_TEXT_CHARS
        artifact = Artefact(
            type=Artefact.Types.TEXT,
            code=long_text,
            description="Long text",
        )

        result = inspect_text(artifact)
        self.assertIn("truncated", result)
        self.assertIn("5000 total characters", result)

    def test_inspect_image_artifact(self):
        """Test inspecting an image artifact."""
        artifact = Artefact(
            type=Artefact.Types.IMAGE,
            image="/path/to/chart.png",
            description="Sales chart",
            code="plt.bar(x, y)",
        )

        result = inspect_image(artifact)
        self.assertIn("**Image Artifact:**", result)
        self.assertIn("Sales chart", result)
        self.assertIn("/path/to/chart.png", result)
        self.assertIn("plt.bar", result)

    def test_inspect_model_artifact(self):
        """Test inspecting a model artifact."""
        # Create a real sklearn model for testing
        try:
            from sklearn.ensemble import RandomForestClassifier
            import numpy as np

            model = RandomForestClassifier(n_estimators=10)
            # Fit the model so it has estimators_
            X = np.array([[1, 2], [3, 4], [5, 6]])
            y = np.array([0, 1, 0])
            model.fit(X, y)

            artifact = Artefact(
                type=Artefact.Types.MODEL,
                model=model,
                description="Trained classifier",
            )

            result = inspect_model(artifact)
            self.assertIn("**Model Artifact:**", result)
            self.assertIn("Trained classifier", result)
            self.assertIn("RandomForestClassifier", result)
        except ImportError:
            self.skipTest("sklearn not installed")

    def test_inspect_none_artifact(self):
        """Test inspecting None artifact."""
        result = inspect_artifact(None)
        self.assertEqual(result, "No artifact provided")

    def test_inspect_artifact_routing(self):
        """Test that inspect_artifact routes to correct inspector."""
        # Table
        table_artifact = Artefact(type=Artefact.Types.TABLE, data=pd.DataFrame())
        result = inspect_artifact(table_artifact)
        self.assertIn("Schema", result)

        # Text
        text_artifact = Artefact(type=Artefact.Types.TEXT, code="test")
        result = inspect_artifact(text_artifact)
        self.assertEqual("test", result)


class TestValidationAgentParsing(unittest.TestCase):
    """Tests for ValidationAgent response parsing (unit tests only)."""

    def test_parse_valid_response(self):
        """Test parsing a valid JSON response."""
        from yaaaf.components.agents.validation_agent import ValidationAgent
        from yaaaf.components.client import OllamaClient

        # Use real client (parsing doesn't need network)
        client = OllamaClient(model="test", host="http://localhost:11434")
        agent = ValidationAgent(client)

        response = '''```json
{
  "is_valid": true,
  "confidence": 0.95,
  "reason": "Artifact matches expectations perfectly",
  "should_ask_user": false,
  "suggested_fix": null
}
```'''

        result = agent._parse_response(response, asset_name="test")

        self.assertTrue(result.is_valid)
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.asset_name, "test")

    def test_parse_invalid_response(self):
        """Test parsing an invalid JSON response."""
        from yaaaf.components.agents.validation_agent import ValidationAgent
        from yaaaf.components.client import OllamaClient

        client = OllamaClient(model="test", host="http://localhost:11434")
        agent = ValidationAgent(client)

        response = '''```json
{
  "is_valid": false,
  "confidence": 0.3,
  "reason": "Data does not match expected format",
  "should_ask_user": false,
  "suggested_fix": "Try using a different data source"
}
```'''

        result = agent._parse_response(response, asset_name="test")

        self.assertFalse(result.is_valid)
        self.assertEqual(result.confidence, 0.3)
        self.assertEqual(result.suggested_fix, "Try using a different data source")

    def test_parse_malformed_response(self):
        """Test handling malformed response."""
        from yaaaf.components.agents.validation_agent import ValidationAgent
        from yaaaf.components.client import OllamaClient

        client = OllamaClient(model="test", host="http://localhost:11434")
        agent = ValidationAgent(client)

        response = "This is not valid JSON"

        result = agent._parse_response(response, asset_name="test")

        # Should default to valid on parse error
        self.assertTrue(result.is_valid)
        self.assertIn("Could not parse", result.reason)


class TestWorkflowExecutorValidation(unittest.TestCase):
    """Tests for validation integration in WorkflowExecutor."""

    def test_validation_exceptions_defined(self):
        """Test that validation exceptions are properly defined."""
        from yaaaf.components.executors.workflow_executor import (
            ReplanRequiredException,
            UserDecisionRequiredException,
        )

        # Test ReplanRequiredException
        validation_result = ValidationResult.invalid_replan(
            reason="Test", suggested_fix="Fix it", asset_name="test_asset"
        )
        exc = ReplanRequiredException(validation_result, {"asset1": "result1"})
        self.assertEqual(exc.validation_result.asset_name, "test_asset")
        self.assertEqual(exc.completed_assets, {"asset1": "result1"})

        # Test UserDecisionRequiredException
        exc2 = UserDecisionRequiredException(validation_result, {"asset1": "result1"})
        self.assertIn("test_asset", str(exc2))


if __name__ == "__main__":
    unittest.main()
