"""
YAAAF - Yet Another Autonomous Agents Framework

A modular framework for building intelligent agentic applications with Python backend
and Next.js frontend components. The system features an orchestrator pattern with
specialized agents for different tasks like SQL queries, web search, visualization,
machine learning, and reflection.
"""

__version__ = "0.0.3"
__author__ = "YAAAF Contributors"
__email__ = "alberto@fractalego.io"
__license__ = "MIT"

# Core components
from yaaaf.components.data_types import Messages, Note, Utterance, PromptTemplate
from yaaaf.components.agents.base_agent import BaseAgent
from yaaaf.components.agents.orchestrator_agent import OrchestratorAgent
from yaaaf.components.orchestrator_builder import OrchestratorBuilder

# Common agents
from yaaaf.components.agents.sql_agent import SqlAgent
from yaaaf.components.agents.visualization_agent import VisualizationAgent
from yaaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
from yaaaf.components.agents.reflection_agent import ReflectionAgent
from yaaaf.components.agents.rag_agent import RAGAgent

# Client and configuration
from yaaaf.components.client import BaseClient, OllamaClient
from yaaaf.server.config import get_config

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    # Core data types
    "Messages",
    "Note",
    "Utterance",
    "PromptTemplate",
    # Base classes
    "BaseAgent",
    "BaseClient",
    # Main orchestrator
    "OrchestratorAgent",
    "OrchestratorBuilder",
    # Specialized agents
    "SqlAgent",
    "VisualizationAgent",
    "DuckDuckGoSearchAgent",
    "ReflectionAgent",
    "RAGAgent",
    # Client implementations
    "OllamaClient",
    # Configuration
    "get_config",
]
