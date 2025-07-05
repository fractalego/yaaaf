import unittest
import pandas as pd
from unittest.mock import Mock, AsyncMock

from yaaaf.components.agents.numerical_sequences_agent import NumericalSequencesAgent
from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.client import BaseClient
from yaaaf.components.data_types import Messages, Utterance


class TestNumericalSequencesAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = Mock(spec=BaseClient)
        self.mock_client.predict = AsyncMock()
        self.agent = NumericalSequencesAgent(self.mock_client)

    async def test_extract_numerical_sequences(self):
        """Test that the agent can extract numerical data from search results."""

        # Create mock search result data
        search_data = pd.DataFrame(
            {
                "title": [
                    "Car Sales Report 2020",
                    "Car Sales Report 2021",
                    "Car Sales Report 2022",
                ],
                "content": [
                    "Red cars sold: 1500 units in 2020",
                    "Red cars sold: 1800 units in 2021",
                    "Red cars sold: 2100 units in 2022",
                ],
                "url": [
                    "https://example.com/2020",
                    "https://example.com/2021",
                    "https://example.com/2022",
                ],
            }
        )

        # Store the search result as an artefact
        storage = ArtefactStorage()
        search_artefact_id = "test_search_123"
        storage.store_artefact(
            search_artefact_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description="Search results about car sales",
                data=search_data,
                id=search_artefact_id,
            ),
        )

        # Create a message with the artefact reference
        messages = Messages(
            [
                Utterance(
                    role="user",
                    content=f"Extract yearly red car sales data from <artefact type='search-result'>{search_artefact_id}</artefact>",
                )
            ]
        )

        # Mock the LLM response with extracted numerical data
        mock_response = """I'll extract the numerical data about red car sales by year.

```table
| year | number_of_red_cars |
|------|-------------------|
| 2020 | 1500 |
| 2021 | 1800 |
| 2022 | 2100 |
```

<taskcompleted/>"""

        self.mock_client.predict.return_value = mock_response

        # Call the agent
        result = await self.agent.query(messages)

        # Verify the agent was called with correct prompt
        self.mock_client.predict.assert_called_once()
        call_args = self.mock_client.predict.call_args
        messages_arg = call_args.kwargs["messages"]

        # Check that the system prompt contains the search data
        system_prompts = [u for u in messages_arg.utterances if u.role == "system"]
        self.assertTrue(len(system_prompts) > 0)
        self.assertIn("Car Sales Report", system_prompts[0].content)

        # Verify the result contains artefact reference
        self.assertIn("artefact", result)
        self.assertIn("numerical-sequences-table", result)

    async def test_no_artefact_error(self):
        """Test that the agent returns error when no artefacts are provided."""
        messages = Messages(
            [
                Utterance(
                    role="user",
                    content="Extract numerical data without providing any artefacts",
                )
            ]
        )

        result = await self.agent.query(messages)

        # Should return no artefact error
        self.assertEqual(result, "No artefact found in the message.")
        self.mock_client.predict.assert_not_called()

    async def test_empty_table_response(self):
        """Test agent behavior when LLM returns empty/invalid table."""

        # Create dummy search data
        search_data = pd.DataFrame(
            {
                "title": ["Test"],
                "content": ["No numerical data here"],
                "url": ["https://example.com"],
            }
        )

        storage = ArtefactStorage()
        search_artefact_id = "test_empty_123"
        storage.store_artefact(
            search_artefact_id,
            Artefact(
                type=Artefact.Types.TABLE,
                description="Search results without numerical data",
                data=search_data,
                id=search_artefact_id,
            ),
        )

        messages = Messages(
            [
                Utterance(
                    role="user",
                    content=f"Extract numerical data from <artefact type='search-result'>{search_artefact_id}</artefact>",
                )
            ]
        )

        # Mock response with no valid table
        mock_response = """I couldn't find any numerical data in the provided content.

<taskcompleted/>"""

        self.mock_client.predict.return_value = mock_response

        result = await self.agent.query(messages)

        # Should return error about no numerical data
        self.assertIn("Could not extract numerical data", result)

    def test_agent_info(self):
        """Test agent info and description methods."""
        info = self.agent.get_info()
        self.assertIn("numerical data", info.lower())
        self.assertIn("structured tables", info.lower())

        description = self.agent.get_description()
        self.assertIn("Numerical Sequences agent", description)
        self.assertIn("numericalsequencesagent", description)
        self.assertIn("intermediary", description.lower())


if __name__ == "__main__":
    unittest.main()
