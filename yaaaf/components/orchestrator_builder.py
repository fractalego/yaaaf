import os
import logging
from typing import List
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.agents.planner_agent import PlannerAgent
from yaaaf.components.agents.reviewer_agent import ReviewerAgent
from yaaaf.components.agents.sql_agent import SqlAgent
from yaaaf.components.agents.document_retriever_agent import DocumentRetrieverAgent
from yaaaf.components.agents.url_agent import URLAgent
from yaaaf.components.agents.url_reviewer_agent import UrlReviewerAgent
from yaaaf.components.agents.user_input_agent import UserInputAgent
from yaaaf.components.agents.visualization_agent import VisualizationAgent
from yaaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaaf.components.agents.brave_search_agent import BraveSearchAgent
from yaaaf.components.agents.bash_agent import BashAgent
from yaaaf.components.agents.tool_agent import ToolAgent
from yaaaf.components.agents.numerical_sequences_agent import NumericalSequencesAgent
from yaaaf.components.agents.answerer_agent import AnswererAgent
from yaaaf.components.agents.mle_agent import MleAgent
from yaaaf.components.agents.validation_agent import ValidationAgent
from yaaaf.components.client import OllamaClient
from yaaaf.components.sources.sqlite_source import SqliteSource
from yaaaf.components.sources.rag_source import RAGSource
from yaaaf.components.sources.persistent_rag_source import PersistentRAGSource
from yaaaf.connectors.mcp_connector import MCPSseConnector, MCPStdioConnector, MCPTools
from yaaaf.server.config import Settings, AgentSettings, ToolTransportType

_logger = logging.getLogger(__name__)


class OrchestratorBuilder:
    def __init__(self, config: Settings):
        self.config = config
        self._agents_map = {
            "visualization": VisualizationAgent,
            "sql": SqlAgent,
            "document_retriever": DocumentRetrieverAgent,
            "reviewer": ReviewerAgent,
            "websearch": DuckDuckGoSearchAgent,
            "brave_search": BraveSearchAgent,
            "url": URLAgent,
            "url_reviewer": UrlReviewerAgent,
            "user_input": UserInputAgent,
            "bash": BashAgent,
            "tool": ToolAgent,
            "numerical_sequences": NumericalSequencesAgent,
            "answerer": AnswererAgent,
            "mle": MleAgent,
            "planner": PlannerAgent,
        }

    def _load_text_from_file(self, file_path: str) -> str:
        """Load text content from a file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()

    def _create_rag_sources(self) -> List[RAGSource]:
        """Create document sources from text-type sources in config."""
        rag_sources = []

        # First check if we have a persistent RAG source configured
        has_persistent_rag = any(source.type == "rag" for source in self.config.sources)

        # Add uploaded sources if available (but skip if we have persistent RAG to avoid duplicates)
        if not has_persistent_rag:
            try:
                from yaaaf.server.routes import get_uploaded_rag_sources

                uploaded_sources = get_uploaded_rag_sources()
                rag_sources.extend(uploaded_sources)
                _logger.info(f"Added {len(uploaded_sources)} uploaded document sources")
            except ImportError:
                # Routes module might not be available in some contexts
                pass
            except Exception as e:
                _logger.warning(f"Could not load uploaded document sources: {e}")

        for source_config in self.config.sources:
            if source_config.type == "rag":
                # Use the same persistent RAG source instance from routes
                try:
                    from yaaaf.server.routes import _get_persistent_rag_source

                    rag_source = _get_persistent_rag_source()
                    if rag_source:
                        rag_sources.append(rag_source)
                        _logger.info(
                            f"Using shared persistent RAG source: {source_config.name} at {source_config.path}"
                        )
                    else:
                        _logger.warning(
                            "Could not get persistent RAG source from routes"
                        )
                except ImportError:
                    # Fallback: create new instance if routes not available
                    description = getattr(
                        source_config, "description", source_config.name
                    )
                    rag_source = PersistentRAGSource(
                        description=description,
                        source_path=source_config.name or "persistent_rag",
                        pickle_path=source_config.path,
                    )
                    rag_sources.append(rag_source)
                    _logger.info(
                        f"Created new persistent RAG source: {source_config.name} at {source_config.path}"
                    )

            elif source_config.type == "text":
                description = getattr(source_config, "description", source_config.name)
                rag_source = RAGSource(
                    description=description, source_path=source_config.path
                )

                # Load text content from file or directory
                if os.path.isfile(source_config.path):
                    # Single file
                    if source_config.path.lower().endswith(".pdf"):
                        # Handle single PDF file with configurable chunking (default: 1 page per chunk)
                        with open(source_config.path, "rb") as pdf_file:
                            pdf_content = pdf_file.read()
                            filename = os.path.basename(source_config.path)
                            # Use default chunking of no chunking (-1), can be made configurable later
                            rag_source.add_pdf(
                                pdf_content, filename, pages_per_chunk=-1
                            )
                    else:
                        # Handle text files
                        text_content = self._load_text_from_file(source_config.path)
                        rag_source.add_text(text_content)
                elif os.path.isdir(source_config.path):
                    # Directory of files
                    for filename in os.listdir(source_config.path):
                        file_path = os.path.join(source_config.path, filename)
                        if os.path.isfile(file_path):
                            if filename.lower().endswith(
                                (".txt", ".md", ".html", ".htm")
                            ):
                                text_content = self._load_text_from_file(file_path)
                                rag_source.add_text(text_content)
                            elif filename.lower().endswith(".pdf"):
                                # Handle PDF files with configurable chunking (default: no chunking)
                                with open(file_path, "rb") as pdf_file:
                                    pdf_content = pdf_file.read()
                                    # Use default chunking of no chunking (-1), can be made configurable later
                                    rag_source.add_pdf(
                                        pdf_content, filename, pages_per_chunk=-1
                                    )

                rag_sources.append(rag_source)
        return rag_sources

    async def _create_mcp_tools(self) -> List[MCPTools]:
        """Create MCP tools from configuration."""
        mcp_tools = []
        for tool_config in self.config.tools:
            try:
                if tool_config.type == ToolTransportType.SSE:
                    if not tool_config.url:
                        _logger.warning(
                            f"SSE tool '{tool_config.name}' missing URL, skipping"
                        )
                        continue
                    connector = MCPSseConnector(
                        url=tool_config.url, description=tool_config.description
                    )
                elif tool_config.type == ToolTransportType.STDIO:
                    if not tool_config.command:
                        _logger.warning(
                            f"Stdio tool '{tool_config.name}' missing command, skipping"
                        )
                        continue
                    connector = MCPStdioConnector(
                        command=tool_config.command,
                        description=tool_config.description,
                        args=tool_config.args or [],
                    )
                else:
                    _logger.warning(f"Unknown tool transport type: {tool_config.type}")
                    continue

                tools = await connector.get_tools()
                mcp_tools.append(tools)
                _logger.info(f"Successfully loaded MCP tools from '{tool_config.name}'")

            except Exception as e:
                _logger.error(
                    f"Failed to load MCP tools from '{tool_config.name}': {e}"
                )
                continue

        return mcp_tools

    def _create_sql_sources(self) -> List[SqliteSource]:
        """Create SQL sources from sqlite-type sources in config."""
        sql_sources = []

        for source_config in self.config.sources:
            if source_config.type == "sqlite":
                # Ensure database file exists - create empty one if it doesn't
                import os

                if not os.path.exists(source_config.path):
                    try:
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(source_config.path), exist_ok=True)
                        # Create empty database file
                        import sqlite3

                        with sqlite3.connect(source_config.path) as conn:
                            conn.execute(
                                "SELECT 1"
                            )  # Simple query to initialize the database
                        _logger.info(
                            f"Created new database file at '{source_config.path}'"
                        )
                    except Exception as e:
                        _logger.error(
                            f"Could not create database file at {source_config.path}: {e}"
                        )
                        continue

                sql_source = SqliteSource(
                    name=source_config.name,
                    db_path=source_config.path,
                )
                sql_sources.append(sql_source)

        return sql_sources

    def _get_sqlite_source(self):
        """Get the first SQLite source from config (deprecated - use _create_sql_sources instead)."""
        sql_sources = self._create_sql_sources()
        return sql_sources[0] if sql_sources else None

    def _create_client_for_agent(self, agent_config) -> OllamaClient:
        """Create a client for an agent, using agent-specific settings if available."""
        if isinstance(agent_config, AgentSettings):
            # Use agent-specific settings, falling back to default client settings
            model = agent_config.model or self.config.client.model
            temperature = (
                agent_config.temperature
                if agent_config.temperature is not None
                else self.config.client.temperature
            )
            max_tokens = (
                agent_config.max_tokens
                if agent_config.max_tokens is not None
                else self.config.client.max_tokens
            )
            host = agent_config.host or self.config.client.host
            agent_name = agent_config.name

            # Log agent-specific configuration
            if agent_config.host:
                _logger.info(
                    f"Agent '{agent_name}' configured with custom host: {host}"
                )
            else:
                _logger.info(f"Agent '{agent_name}' using default host: {host}")
        else:
            # Use default client settings for string-based agent names
            model = self.config.client.model
            temperature = self.config.client.temperature
            max_tokens = self.config.client.max_tokens
            host = self.config.client.host
            agent_name = agent_config

            _logger.info(f"Agent '{agent_name}' using default host: {host}")

        return OllamaClient(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            host=host,
            disable_thinking=self.config.client.disable_thinking,
        )

    def _get_agent_name(self, agent_config) -> str:
        """Extract agent name from config (either string or AgentSettings object)."""
        if isinstance(agent_config, AgentSettings):
            return agent_config.name
        return agent_config


    async def build(self):
        # Log orchestrator configuration
        _logger.info(
            f"Building orchestrator with default client host: {self.config.client.host}"
        )

        # Create default client for orchestrator
        orchestrator_client = OllamaClient(
            model=self.config.client.model,
            temperature=self.config.client.temperature,
            max_tokens=self.config.client.max_tokens,
            host=self.config.client.host,
            disable_thinking=self.config.client.disable_thinking,
        )

        # Prepare sources
        sql_sources = self._create_sql_sources()
        rag_sources = self._create_rag_sources()

        # Prepare MCP tools
        mcp_tools = await self._create_mcp_tools()


        # First build all agents
        all_agents = {}
        for agent_config in self.config.agents:
            agent_name = self._get_agent_name(agent_config)
            if agent_name in self._agents_map:
                agent_client = self._create_client_for_agent(agent_config)
                agent = self._create_agent(
                    agent_name,
                    agent_client,
                    sql_sources,
                    rag_sources,
                    mcp_tools,
                )
                if agent:
                    all_agents[agent_name] = agent

        # Check if planner agent is available
        if "planner" not in all_agents:
            # Create planner agent if not in config
            agent_client = orchestrator_client
            from yaaaf.components.agents.agent_taxonomies import (
                get_all_agents_with_taxonomy,
            )

            available_agents = []
            # Only include agents that are actually configured
            configured_agent_names = [self._get_agent_name(agent_config) for agent_config in self.config.agents]
            for agent_name, agent_class in self._agents_map.items():
                if agent_name in configured_agent_names:  # Only configured agents
                    taxonomy = get_all_agents_with_taxonomy().get(agent_class.__name__)
                    if taxonomy:
                        available_agents.append(
                            {
                                "name": agent_name,  # Use config name instead of class name
                                "description": agent_class.get_info(),
                                "taxonomy": taxonomy,
                            }
                        )
            all_agents["planner"] = PlannerAgent(agent_client, available_agents)

        # Create validation agent for artifact validation
        validation_agent = ValidationAgent(orchestrator_client)
        _logger.info("Created validation agent")

        # Create plan-driven orchestrator with validation
        orchestrator = OrchestratorAgent(
            orchestrator_client, all_agents, validation_agent=validation_agent
        )
        _logger.info("Created plan-driven orchestrator with validation")

        return orchestrator

    def _create_agent(
        self,
        agent_name: str,
        agent_client,
        sql_sources,
        rag_sources,
        mcp_tools,
    ):
        """Helper method to create an agent with appropriate dependencies."""
        if agent_name == "sql" and sql_sources:
            return self._agents_map[agent_name](
                client=agent_client, sources=sql_sources
            )
        elif agent_name == "document_retriever" and rag_sources:
            return self._agents_map[agent_name](
                client=agent_client, sources=rag_sources
            )
        elif agent_name == "tool" and mcp_tools:
            return self._agents_map[agent_name](client=agent_client, tools=mcp_tools)
        elif agent_name == "planner":
            from yaaaf.components.agents.agent_taxonomies import (
                get_all_agents_with_taxonomy,
            )

            available_agents = []
            # Only include agents that are actually configured 
            configured_agent_names = [self._get_agent_name(agent_config) for agent_config in self.config.agents]
            for agent_key, agent_class in self._agents_map.items():
                if agent_key in configured_agent_names:  # Only configured agents
                    taxonomy = get_all_agents_with_taxonomy().get(agent_class.__name__)
                    if taxonomy:
                        available_agents.append(
                            {
                                "name": agent_key,  # Use config name instead of class name
                                "description": agent_class.get_info(),
                                "taxonomy": taxonomy,
                            }
                        )
            
            # Debug: Log available agents for planner
            _logger.info(f"Available agents for planner: {[agent['name'] for agent in available_agents]}")
            return self._agents_map[agent_name](
                client=agent_client, available_agents=available_agents
            )
        elif agent_name in self._agents_map:
            # Skip agents that require dependencies but don't have them
            if agent_name == "sql" and not sql_sources:
                return None  # SqlAgent requires sources
            elif agent_name == "document_retriever" and not rag_sources:
                return None  # DocumentRetrieverAgent requires sources
            elif agent_name == "tool" and not mcp_tools:
                return None  # ToolAgent requires tools
            else:
                return self._agents_map[agent_name](client=agent_client)
        return None
