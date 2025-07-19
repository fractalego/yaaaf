Welcome to YAAAF Documentation
=============================

**YAAAF** (Yet Another Autonomous Agents Framework) is a modular framework for building agentic applications with both Python backend and Next.js frontend components. The system features an orchestrator pattern with specialized agents for different tasks like SQL queries, web search, visualization, and reflection.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   configuration
   architecture
   agents
   brave_search_agent
   mcp_integration
   api_reference
   frontend
   gdpr_popup
   development
   examples

Key Features
------------

* **Modular Agent System**: Specialized agents for SQL, visualization, web search, reflection, and more
* **Orchestrator Pattern**: Central coordinator that routes queries to appropriate agents
* **MCP Integration**: Full support for Model Context Protocol (MCP) with SSE and stdio transports
* **Real-time Streaming**: Live updates through WebSocket-like streaming
* **Artifact Management**: Structured handling of generated content (tables, images, etc.)
* **Frontend Integration**: React-based UI with real-time chat interface
* **Extensible**: Easy to add new agents and capabilities

Quick Start
-----------

Install and run YAAAF in just a few commands:

.. code-block:: bash

   # Create a custom configuration (optional)
   python -m yaaaf config

   # Start the backend server (default port 4000)
   python -m yaaaf backend

   # Start the frontend server (default port 3000)
   python -m yaaaf frontend

   # Or specify custom ports
   python -m yaaaf backend 8080
   python -m yaaaf frontend 3001

Architecture Overview
---------------------

YAAAF follows a clean separation between backend and frontend:

* **Backend**: Python-based server with FastAPI and specialized agents
* **Frontend**: Next.js application with real-time chat interface
* **Communication**: RESTful API with streaming support
* **Storage**: Centralized artifact storage with ID-based references

Agents
------

YAAAF includes several built-in agents:

* **OrchestratorAgent**: Routes queries to appropriate specialized agents
* **SqlAgent**: Executes SQL queries and returns structured data
* **VisualizationAgent**: Creates charts and visualizations from data
* **WebSearchAgent**: Performs web searches using DuckDuckGo
* **BraveSearchAgent**: Privacy-focused web search using Brave's independent search API
* **ReflectionAgent**: Provides step-by-step reasoning and planning
* **DocumentRetrieverAgent**: Document search and retrieval from configured sources
* **TodoAgent**: Creates structured todo lists for planning complex multi-agent tasks
* **ToolAgent**: Advanced integration with MCP (Model Context Protocol) tools and external services

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`