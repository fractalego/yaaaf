Agents
======

YAAAF includes several specialized agents, each designed to handle specific types of tasks. All agents follow a common interface while providing unique capabilities.

Agent Overview
--------------

Base Agent Interface
~~~~~~~~~~~~~~~~~~~

All agents inherit from the ``BaseAgent`` class and implement the core interface:

.. code-block:: python

   class BaseAgent:
       async def query(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
           """Process a query and return a response"""
           pass
       
       def get_name(self) -> str:
           """Return the agent's name (lowercase class name)"""
           return self.__class__.__name__.lower()
       
       def get_description(self) -> str:
           """Return a description of the agent's capabilities"""
           pass

Available Agents
----------------

OrchestratorAgent
~~~~~~~~~~~~~~~~

**Purpose**: Central coordinator that routes queries to appropriate specialized agents.

**Capabilities**:
   * Analyzes user queries to determine intent
   * Routes requests to appropriate specialized agents
   * Manages conversation flow and context
   * Combines responses from multiple agents

**Usage Tags**: ``<orchestratoragent>...</orchestratoragent>``

**Example**:

.. code-block:: python

   orchestrator = OrchestratorAgent(client)
   orchestrator.subscribe_agent(SqlAgent(client, source))
   response = await orchestrator.query(messages)

SqlAgent
~~~~~~~~

**Purpose**: Executes SQL queries against configured data sources and returns structured results.

**Capabilities**:
   * Converts natural language to SQL queries
   * Executes queries against SQLite databases
   * Returns data as structured tables
   * Handles query errors and provides feedback

**Usage Tags**: ``<sqlagent>...</sqlagent>``

**Configuration**:

.. code-block:: python

   from yaaaf.components.sources.sqlite_source import SqliteSource
   
   source = SqliteSource("path/to/database.db")
   sql_agent = SqlAgent(client, source)

**Example Queries**:
   * "How many users are in the database?"
   * "Show me sales data from last month"
   * "Get the top 10 products by revenue"

VisualizationAgent
~~~~~~~~~~~~~~~~~

**Purpose**: Creates charts and visualizations from data artifacts.

**Capabilities**:
   * Generates matplotlib-based visualizations
   * Processes tabular data from other agents
   * Creates PNG images stored as artifacts
   * Supports various chart types (bar, line, scatter, etc.)

**Usage Tags**: ``<visualizationagent>...</visualizationagent>``

**Requirements**: Requires data artifacts from previous agent responses

**Example**:

.. code-block:: text

   <visualizationagent>
   Create a bar chart showing sales by region using the data from the SQL query above.
   <artefact>table_id_12345</artefact>
   </visualizationagent>

WebSearchAgent (DuckDuckGoSearchAgent)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose**: Performs web searches and retrieves relevant information.

**Capabilities**:
   * Searches the web using DuckDuckGo
   * Extracts relevant information from search results
   * Returns structured data with URLs and snippets
   * Handles search result ranking and filtering

**Usage Tags**: ``<websearchagent>...</websearchagent>``

**Example Queries**:
   * "Search for recent developments in AI"
   * "Find information about Python best practices"
   * "Look up current weather in San Francisco"

ReflectionAgent
~~~~~~~~~~~~~~

**Purpose**: Provides step-by-step reasoning and planning for complex tasks.

**Capabilities**:
   * Breaks down complex problems into steps
   * Provides strategic thinking and planning
   * Suggests approaches for multi-step tasks
   * Helps with task decomposition

**Usage Tags**: ``<reflectionagent>...</reflectionagent>``

**Example**:

.. code-block:: text

   <reflectionagent>
   How should I approach analyzing customer churn in our database?
   </reflectionagent>

RAGAgent
~~~~~~~~

**Purpose**: Retrieval-augmented generation from document collections.

**Capabilities**:
   * Searches through document collections
   * Retrieves relevant text passages
   * Generates responses based on retrieved content
   * Supports multiple document sources

**Usage Tags**: ``<ragagent>...</ragagent>``

**Configuration**:

.. code-block:: python

   from yaaaf.components.sources.text_source import TextSource
   
   sources = [TextSource("documents/")]
   rag_agent = RAGAgent(client, sources)

ReviewerAgent
~~~~~~~~~~~~

**Purpose**: Analyzes and extracts information from data artifacts.

**Capabilities**:
   * Reviews data from previous agents
   * Extracts specific information patterns
   * Performs data quality checks
   * Generates summary reports

**Usage Tags**: ``<revieweragent>...</revieweragent>``

**Requirements**: Requires data artifacts to analyze

UrlReviewerAgent
~~~~~~~~~~~~~~~

**Purpose**: Retrieves and analyzes content from web URLs.

**Capabilities**:
   * Fetches content from web pages
   * Extracts relevant information from HTML
   * Processes and summarizes web content
   * Handles various content types

**Usage Tags**: ``<urlrevieweragent>...</urlrevieweragent>``

**Example**:

.. code-block:: text

   <urlrevieweragent>
   Analyze the content of this article about machine learning trends.
   <artefact>websearch_results_456</artefact>
   </urlrevieweragent>

MleAgent
~~~~~~~~

**Purpose**: Machine learning model training and analysis.

**Capabilities**:
   * Trains sklearn models on provided data
   * Performs feature analysis and selection
   * Generates model predictions and insights
   * Saves trained models as artifacts

**Usage Tags**: ``<mleagent>...</mleagent>``

**Requirements**: Requires tabular data for training

ToolAgent
~~~~~~~~~

**Purpose**: Integration with MCP (Model Context Protocol) tools.

**Capabilities**:
   * Interfaces with external tools and APIs
   * Executes tool calls based on user requests
   * Handles tool authentication and parameters
   * Returns structured tool responses

**Usage Tags**: ``<toolagent>...</toolagent>``

**Configuration**: Requires MCP tool setup and authentication

Agent Communication
-------------------

Message Flow
~~~~~~~~~~~

Agents communicate through a structured message system:

1. **Input**: Agents receive ``Messages`` objects containing conversation history
2. **Processing**: Agents process the request according to their specialization
3. **Output**: Agents return string responses with optional artifacts
4. **Notes**: Agents can append ``Note`` objects to track their contributions

Artifact Handling
~~~~~~~~~~~~~~~~~

Agents can generate and consume artifacts:

**Creating Artifacts**:

.. code-block:: python

   # Store an artifact
   artifact = Artefact(
       type=Artefact.Types.TABLE,
       data=dataframe,
       description="Query results",
       id=unique_id
   )
   storage.store_artefact(unique_id, artifact)

**Referencing Artifacts**:

.. code-block:: text

   The results are in this artifact: <artefact type='table'>table_id_123</artefact>

**Consuming Artifacts**:

.. code-block:: python

   # Retrieve artifacts from previous responses
   artifacts = get_artefacts_from_utterance_content(content)

Error Handling
~~~~~~~~~~~~~

All agents implement comprehensive error handling:

* **Logging**: Errors are logged with context information
* **Graceful Degradation**: Agents continue operation when possible
* **User Feedback**: Error messages are returned to users when appropriate
* **Recovery**: Agents attempt to recover from transient failures

Agent Development
-----------------

Creating Custom Agents
~~~~~~~~~~~~~~~~~~~~~~

To create a new agent:

1. **Inherit from BaseAgent**:

   .. code-block:: python

      class CustomAgent(BaseAgent):
          async def query(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
              # Implement your agent logic here
              return "Agent response"
          
          def get_description(self) -> str:
              return "Description of what this agent does"

2. **Register with Orchestrator**:

   .. code-block:: python

      orchestrator.subscribe_agent(CustomAgent(client))

3. **Handle Artifacts** (if needed):

   .. code-block:: python

      # Generate artifacts
      artifact_id = create_hash(content)
      self._storage.store_artefact(artifact_id, artifact)
      
      # Reference in response
      return f"Result: <artefact type='custom'>{artifact_id}</artefact>"

Best Practices
~~~~~~~~~~~~~

* **Single Responsibility**: Each agent should have a clear, focused purpose
* **Error Handling**: Implement comprehensive error handling and logging
* **Artifact Management**: Use centralized storage for generated content
* **Configuration**: Make agents configurable through dependency injection
* **Testing**: Write unit tests for agent functionality
* **Documentation**: Provide clear descriptions of agent capabilities

Agent Configuration
------------------

Model Configuration
~~~~~~~~~~~~~~~~~~

Agents can be configured with different models:

.. code-block:: python

   client = OllamaClient(
       model="qwen2.5:32b",
       temperature=0.4,
       max_tokens=1000
   )

Data Source Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

Agents requiring data sources need proper configuration:

.. code-block:: python

   # SQL Agent with database
   sqlite_source = SqliteSource("data/database.db")
   sql_agent = SqlAgent(client, sqlite_source)
   
   # RAG Agent with document sources
   text_sources = [TextSource("documents/folder1/"), TextSource("documents/folder2/")]
   rag_agent = RAGAgent(client, text_sources)

Agent Registry
~~~~~~~~~~~~~

The orchestrator maintains a registry of available agents:

.. code-block:: python

   def build_orchestrator():
       orchestrator = OrchestratorAgent(client)
       
       # Register all available agents
       orchestrator.subscribe_agent(SqlAgent(client, source))
       orchestrator.subscribe_agent(VisualizationAgent(client))
       orchestrator.subscribe_agent(WebSearchAgent(client))
       orchestrator.subscribe_agent(ReflectionAgent(client))
       
       return orchestrator