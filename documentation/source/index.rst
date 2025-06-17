Welcome to YAAF Documentation
=============================

**YAAF** (Yet Another Agentic Framework) is a modular framework for building agentic applications with both Python backend and Next.js frontend components. The system features an orchestrator pattern with specialized agents for different tasks like SQL queries, web search, visualization, and reflection.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   architecture
   agents
   api_reference
   frontend
   development
   examples

Key Features
------------

* **Modular Agent System**: Specialized agents for SQL, visualization, web search, reflection, and more
* **Orchestrator Pattern**: Central coordinator that routes queries to appropriate agents
* **Real-time Streaming**: Live updates through WebSocket-like streaming
* **Artifact Management**: Structured handling of generated content (tables, images, etc.)
* **Frontend Integration**: React-based UI with real-time chat interface
* **Extensible**: Easy to add new agents and capabilities

Quick Start
-----------

Install and run YAAF in just a few commands:

.. code-block:: bash

   # Start the backend server (default port 4000)
   python -m yaaf backend

   # Start the frontend server (default port 3000)
   python -m yaaf frontend

   # Or specify custom ports
   python -m yaaf backend 8080
   python -m yaaf frontend 3001

Architecture Overview
---------------------

YAAF follows a clean separation between backend and frontend:

* **Backend**: Python-based server with FastAPI and specialized agents
* **Frontend**: Next.js application with real-time chat interface
* **Communication**: RESTful API with streaming support
* **Storage**: Centralized artifact storage with ID-based references

Agents
------

YAAF includes several built-in agents:

* **OrchestratorAgent**: Routes queries to appropriate specialized agents
* **SqlAgent**: Executes SQL queries and returns structured data
* **VisualizationAgent**: Creates charts and visualizations from data
* **WebSearchAgent**: Performs web searches using DuckDuckGo
* **ReflectionAgent**: Provides step-by-step reasoning and planning
* **RAGAgent**: Retrieval-augmented generation from document sources
* **ToolAgent**: Integration with MCP (Model Context Protocol) tools

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`