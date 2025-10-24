import logging
from typing import List

from yaaaf.components.agents.base_agent import ToolBasedAgent
from yaaaf.components.executors import SQLExecutor
from yaaaf.components.agents.prompts import sql_agent_prompt_template
from yaaaf.components.client import BaseClient
from yaaaf.components.sources.sqlite_source import SqliteSource
from yaaaf.components.agents.artefact_utils import create_prompt_from_sources

_logger = logging.getLogger(__name__)


class SqlAgent(ToolBasedAgent):
    """SQL Agent that executes SQL queries against database sources."""

    def __init__(self, client: BaseClient, sources: List[SqliteSource]):
        """Initialize SQL agent with client and data sources."""
        super().__init__(client, SQLExecutor(sources))
        # Complete the prompt template with schema from sources
        self._system_prompt = create_prompt_from_sources(sources, sql_agent_prompt_template)
        self._output_tag = "```sql"

    @staticmethod
    def get_info() -> str:
        """Get a brief description of what this agent does."""
        return "Executes SQL queries against connected databases"

    def get_description(self) -> str:
        return f"""
SQL agent: {self.get_info()}.
This agent provides an interface to a dataset through SQL queries. It includes table information and column names.
To call this agent write {self.get_opening_tag()} INFORMATION TO RETRIEVE {self.get_closing_tag()}
Do not write an SQL formula. Just write in clear and brief English the information you need to retrieve.
        """
