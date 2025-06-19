Configuration
=============

YAAAF provides an interactive configuration generator to help you create custom configurations for your specific needs. The configuration system supports multiple agents, data sources, and LLM models.

Configuration Generator
-----------------------

The configuration generator is an interactive command-line tool that helps you create a local ``config.json`` file.

Usage
~~~~~

.. code-block:: bash

   python -m yaaaf config

This command will start an interactive session that guides you through:

* **LLM model configuration** with any Ollama model name
* **Agent configuration** with descriptions for each agent
* **Database sources** (SQLite files) setup
* **Text sources** (files/folders) for RAG functionality
* **Configuration preview** and saving

Interactive Flow Example
~~~~~~~~~~~~~~~~~~~~~~~~

The configuration generator provides a user-friendly interface:

.. code-block:: text

   ======================================================================
   🤖 YAAAF Configuration Generator
   ======================================================================

   This tool will help you create a local config.json file for YAAAF.
   You'll be asked about:
     • LLM model name (any Ollama model)
     • Which agents to enable
     • Database sources (SQLite files)
     • Text sources (files/folders for RAG)

   Press Ctrl+C at any time to exit.
   ----------------------------------------------------------------------

   🔧 LLM Client Configuration
   ------------------------------

   Enter Ollama model name (e.g., qwen2.5:32b, llama3.1:8b) [qwen2.5:32b]: qwen2.5:14b
   Temperature (0.0-2.0, higher = more creative) [0.7]: 0.5
   Max tokens per response [1024]: 2048

Available Agents
~~~~~~~~~~~~~~~~

The configuration generator supports all built-in YAAAF agents:

.. list-table:: Available Agents
   :header-rows: 1
   :widths: 15 50 20

   * - Agent
     - Description
     - Requirements
   * - **reflection**
     - Step-by-step reasoning and thinking about tasks
     - None
   * - **visualization**
     - Creates charts and visualizations from data
     - None
   * - **sql**
     - Executes SQL queries against databases
     - SQLite sources
   * - **rag**
     - Retrieval-Augmented Generation using text sources
     - Text sources
   * - **reviewer**
     - Analyzes artifacts and validates results
     - None
   * - **websearch**
     - Performs web searches using DuckDuckGo
     - None
   * - **url_reviewer**
     - Extracts information from web search results
     - None

Source Types
~~~~~~~~~~~~

YAAAF supports two types of data sources:

SQLite Sources (for SQL Agent)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Type**: ``"sqlite"``
* **Path**: Path to ``.db`` file
* **Used by**: SQL agent for database queries
* **Features**: Automatic file validation and path resolution

Text Sources (for RAG Agent)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Type**: ``"text"``
* **Path**: Single file or directory
* **Formats**: ``.txt``, ``.md``, ``.html``, ``.htm``
* **Used by**: RAG agent for document retrieval
* **Features**: Directory scanning and file counting

Generated Configuration
-----------------------

The configuration generator creates a JSON file with this structure:

.. code-block:: json

   {
     "client": {
       "model": "qwen2.5:14b",
       "temperature": 0.5,
       "max_tokens": 2048
     },
     "agents": [
       "reflection",
       "visualization", 
       "sql",
       "rag",
       "reviewer"
     ],
     "sources": [
       {
         "name": "Archaeological Data",
         "type": "sqlite",
         "path": "./data/london_archaeological_data.db"
       },
       {
         "name": "Wikipedia Archaeology",
         "type": "text",
         "path": "./data/Archaeology - Wikipedia.html",
         "description": "Wikipedia page about archaeology"
       },
       {
         "name": "Documentation",
         "type": "text", 
         "path": "./docs/",
         "description": "Project documentation and guides"
       }
     ]
   }

Configuration Sections
~~~~~~~~~~~~~~~~~~~~~~

Client Configuration
^^^^^^^^^^^^^^^^^^^^

The ``client`` section configures the LLM connection:

* **model**: Model identifier (e.g., ``"qwen2.5:32b"``)
* **temperature**: Creativity level (0.0-2.0, default: 0.7)
* **max_tokens**: Maximum response length (default: 1024)

Agents Configuration
^^^^^^^^^^^^^^^^^^^^

The ``agents`` array lists enabled agents. Each agent can be specified as a simple string name or as an object with custom model settings:

**Simple Agent Names:**

.. code-block:: json

   "agents": ["reflection", "sql", "rag"]

**Per-Agent Model Configuration:**

.. code-block:: json

   "agents": [
     "reflection",
     {
       "name": "visualization",
       "model": "qwen2.5-coder:32b",
       "temperature": 0.1
     },
     "sql",
     {
       "name": "rag",
       "model": "qwen2.5:14b",
       "temperature": 0.8,
       "max_tokens": 4096
     }
   ]

**Per-Agent Settings:**

* **name**: Agent identifier (required when using object format)
* **model**: Override model for this specific agent (optional)
* **temperature**: Override temperature for this agent (optional)  
* **max_tokens**: Override max tokens for this agent (optional)

Agents without explicit configuration will use the default client settings as fallback.

Sources Configuration  
^^^^^^^^^^^^^^^^^^^^

The ``sources`` array defines data sources:

**SQLite Source:**

.. code-block:: json

   {
     "name": "My Database",
     "type": "sqlite",
     "path": "/path/to/database.db"
   }

**Text Source:**

.. code-block:: json

   {
     "name": "Documentation",
     "type": "text",
     "path": "/path/to/docs/",
     "description": "Project documentation"
   }

Using the Configuration
-----------------------

Method 1: Environment Variable (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set the ``YAAAF_CONFIG`` environment variable to point to your configuration file:

.. code-block:: bash

   export YAAAF_CONFIG=/path/to/your/config.json
   python -m yaaaf backend

Method 2: Replace Default Config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copy your configuration to replace the default:

.. code-block:: bash

   cp config.json yaaaf/server/default_config.json
   python -m yaaaf backend

Method 3: Manual Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also create or edit configuration files manually using any text editor. Follow the JSON structure shown above.

Configuration Features
----------------------

The configuration generator includes several helpful features:

Input Validation
~~~~~~~~~~~~~~~~

* **File/directory existence checking**
* **Numeric validation** for temperature and tokens
* **Path resolution** (relative → absolute)
* **Format validation** for text files

User Experience
~~~~~~~~~~~~~~~

* **Rich emoji-based interface** for better readability
* **Configuration preview** before saving
* **Detailed usage instructions** after completion
* **Multiple usage methods** (environment variable vs default replacement)
* **Clear warnings** and confirmations
* **Graceful error handling** and Ctrl+C support

Example Configuration Files
---------------------------

You can download a complete example configuration file: :download:`example_config.json <_static/example_config.json>`

Minimal Configuration
~~~~~~~~~~~~~~~~~~~~~

A basic configuration with only essential components:

.. code-block:: json

   {
     "client": {
       "model": "qwen2.5:7b",
       "temperature": 0.7,
       "max_tokens": 1024
     },
     "agents": ["reflection"],
     "sources": []
   }

Full-Featured Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A comprehensive setup with multiple agents and sources:

.. code-block:: json

   {
     "client": {
       "model": "qwen2.5:32b",
       "temperature": 0.6,
       "max_tokens": 2048
     },
     "agents": [
       "reflection",
       {
         "name": "visualization",
         "model": "qwen2.5-coder:32b",
         "temperature": 0.1
       },
       "sql",
       {
         "name": "rag", 
         "model": "qwen2.5:14b",
         "temperature": 0.8,
         "max_tokens": 4096
       },
       "reviewer",
       "websearch",
       "brave_search",
       "url_reviewer"
     ],
     "sources": [
       {
         "name": "Main Database",
         "type": "sqlite",
         "path": "./data/main.db"
       },
       {
         "name": "Research Papers",
         "type": "text",
         "path": "./papers/",
         "description": "Academic research papers"
       },
       {
         "name": "Knowledge Base",
         "type": "text",
         "path": "./kb/articles/",
         "description": "Internal knowledge base"
       }
     ],
     "api_keys": {
       "brave_search_api_key": "YOUR_BRAVE_SEARCH_API_KEY_HERE"
     },
     "safety_filter": {
       "enabled": false,
       "blocked_keywords": [],
       "blocked_patterns": [],
       "custom_message": "I cannot answer that"
     }
   }

API Keys Configuration
~~~~~~~~~~~~~~~~~~~~~~

Some agents require API keys for external services. Configure them in the ``api_keys`` section:

.. code-block:: json

   {
     "api_keys": {
       "brave_search_api_key": "your-brave-search-api-key-here"
     }
   }

**Available API Keys:**

* **``brave_search_api_key``**: Required for BraveSearchAgent
  
  * Obtain from: https://api.search.brave.com/
  * Used for: Web search using Brave's independent search index
  * Required when: Using the ``brave_search`` agent

**Security Notes:**

* Never commit API keys to version control
* Use environment variables in production
* Rotate keys regularly for security
* Store keys securely and restrict access

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**File Not Found Errors**
   Ensure all paths in your configuration exist and are accessible.

**Model Loading Issues**
   Verify that the specified model is available in your Ollama installation.

**Agent Dependencies**
   Some agents require specific sources (SQL agent needs SQLite sources, RAG agent needs text sources).

**Permission Errors**
   Ensure YAAAF has read access to all configured source files and directories.

Configuration Validation
~~~~~~~~~~~~~~~~~~~~~~~~

YAAAF validates configurations on startup and will report any issues:

.. code-block:: bash

   # Test your configuration
   python -m yaaaf backend --dry-run  # (if available)

   # Or check logs when starting normally
   python -m yaaaf backend