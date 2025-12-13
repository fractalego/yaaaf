Configuration
=============

YAAAF is configured through a JSON file that defines the LLM client, available agents, data sources, and external tools.

Configuration File
------------------

Set the ``YAAAF_CONFIG`` environment variable to point to your configuration:

.. code-block:: bash

   export YAAAF_CONFIG=/path/to/config.json
   python -m yaaaf backend

Basic Structure
---------------

.. code-block:: json

   {
     "client": {
       "model": "qwen2.5:32b",
       "temperature": 0.7,
       "max_tokens": 1024,
       "host": "http://localhost:11434"
     },
     "agents": [
       "sql",
       "visualization",
       "answerer",
       "websearch"
     ],
     "sources": [],
     "tools": []
   }

Client Configuration
--------------------

The ``client`` section configures the default LLM settings:

.. code-block:: json

   {
     "client": {
       "model": "qwen2.5:32b",
       "temperature": 0.7,
       "max_tokens": 1024,
       "host": "http://localhost:11434",
       "disable_thinking": false
     }
   }

.. list-table::
   :header-rows: 1
   :widths: 20 60 20

   * - Field
     - Description
     - Default
   * - ``model``
     - Ollama model name
     - qwen2.5:32b
   * - ``temperature``
     - Creativity (0.0-2.0)
     - 0.7
   * - ``max_tokens``
     - Maximum response length
     - 1024
   * - ``host``
     - Ollama server URL
     - http://localhost:11434
   * - ``disable_thinking``
     - Disable extended thinking
     - false

Agent Configuration
-------------------

The ``agents`` array lists which agents are available. Agents can be specified as strings (using defaults) or objects (with custom settings).

Simple Format
~~~~~~~~~~~~~

.. code-block:: json

   {
     "agents": ["sql", "visualization", "answerer", "websearch"]
   }

Per-Agent Settings
~~~~~~~~~~~~~~~~~~

Override model settings for specific agents:

.. code-block:: json

   {
     "agents": [
       "sql",
       {
         "name": "visualization",
         "model": "qwen2.5-coder:32b",
         "temperature": 0.1
       },
       {
         "name": "answerer",
         "model": "qwen2.5:32b",
         "temperature": 0.7,
         "max_tokens": 4096
       },
       {
         "name": "document_retriever",
         "host": "http://remote-ollama:11434"
       }
     ]
   }

Available agent names:

- ``sql`` - Database queries
- ``visualization`` - Charts and graphs
- ``answerer`` - Synthesize answers
- ``reviewer`` - Analyze artifacts
- ``websearch`` - DuckDuckGo search
- ``brave_search`` - Brave Search API
- ``document_retriever`` - Document search
- ``url`` - URL content extraction
- ``url_reviewer`` - URL content synthesis
- ``bash`` - Filesystem operations
- ``tool`` - MCP tool integration
- ``mle`` - Machine learning
- ``numerical_sequences`` - Data structuring
- ``user_input`` - Interactive input

Data Sources
------------

The ``sources`` array configures data sources for agents.

SQLite Sources
~~~~~~~~~~~~~~

For SqlAgent:

.. code-block:: json

   {
     "sources": [
       {
         "name": "sales_database",
         "type": "sqlite",
         "path": "./data/sales.db"
       }
     ]
   }

Text Sources
~~~~~~~~~~~~

For DocumentRetrieverAgent:

.. code-block:: json

   {
     "sources": [
       {
         "name": "documentation",
         "type": "text",
         "path": "./docs/",
         "description": "Product documentation"
       }
     ]
   }

Supported text formats: ``.txt``, ``.md``, ``.html``, ``.htm``, ``.pdf``

RAG Sources
~~~~~~~~~~~

For persistent RAG storage:

.. code-block:: json

   {
     "sources": [
       {
         "name": "knowledge_base",
         "type": "rag",
         "path": "./data/rag_index.pkl",
         "description": "Persistent knowledge base"
       }
     ]
   }

MCP Tools Configuration
-----------------------

The ``tools`` array configures external tools via Model Context Protocol (MCP).

SSE Tools
~~~~~~~~~

HTTP-based MCP servers:

.. code-block:: json

   {
     "tools": [
       {
         "name": "calculator",
         "type": "sse",
         "description": "Mathematical calculations",
         "url": "http://localhost:8080/sse"
       }
     ]
   }

Stdio Tools
~~~~~~~~~~~

Command-line MCP servers:

.. code-block:: json

   {
     "tools": [
       {
         "name": "file_tools",
         "type": "stdio",
         "description": "File manipulation",
         "command": "python",
         "args": ["-m", "my_mcp_server"]
       }
     ]
   }

API Keys
--------

Some agents require API keys:

.. code-block:: json

   {
     "api_keys": {
       "brave_search_api_key": "YOUR_API_KEY"
     }
   }

Get a Brave Search API key at https://api.search.brave.com/

Safety Filter
-------------

Configure content filtering:

.. code-block:: json

   {
     "safety_filter": {
       "enabled": true,
       "blocked_keywords": ["harmful", "dangerous"],
       "blocked_patterns": ["pattern.*regex"],
       "custom_message": "I cannot process that request."
     }
   }

Complete Example
----------------

.. code-block:: json

   {
     "client": {
       "model": "qwen2.5:32b",
       "temperature": 0.7,
       "max_tokens": 2048,
       "host": "http://localhost:11434"
     },
     "agents": [
       "sql",
       {
         "name": "visualization",
         "model": "qwen2.5-coder:32b",
         "temperature": 0.1
       },
       "answerer",
       "reviewer",
       "websearch",
       "document_retriever",
       "tool"
     ],
     "sources": [
       {
         "name": "main_database",
         "type": "sqlite",
         "path": "./data/main.db"
       },
       {
         "name": "documentation",
         "type": "text",
         "path": "./docs/",
         "description": "Product documentation"
       }
     ],
     "tools": [
       {
         "name": "calculator",
         "type": "sse",
         "url": "http://localhost:8080/sse",
         "description": "Math operations"
       }
     ],
     "api_keys": {
       "brave_search_api_key": "YOUR_KEY_HERE"
     }
   }

Configuration Generator
-----------------------

Use the interactive configuration generator:

.. code-block:: bash

   python -m yaaaf config

This guides you through:

- LLM model selection
- Agent configuration
- Source setup
- Tool configuration

Environment Variables
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Description
   * - ``YAAAF_CONFIG``
     - Path to configuration JSON file
   * - ``YAAAF_DEBUG``
     - Enable debug logging (true/false)
   * - ``BRAVE_SEARCH_API_KEY``
     - Brave Search API key (alternative to config)

Troubleshooting
---------------

**Agent not available**: Ensure the agent is listed in the ``agents`` array.

**Source not found**: Check that the path exists and is accessible.

**Tool connection failed**: Verify the MCP server is running and accessible.

**Model not available**: Pull the model with ``ollama pull model_name``.
