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

**Purpose**: Performs web searches and retrieves relevant information using DuckDuckGo.

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

BraveSearchAgent
~~~~~~~~~~~~~~~~

**Purpose**: Performs web searches using Brave's independent search API with privacy focus.

**Capabilities**:
   * Searches using Brave's independent search index
   * Privacy-focused search results
   * API key-based authentication
   * Returns structured data with URLs and snippets
   * Independent from Google/Bing search indexes

**Usage Tags**: ``<bravesearchagent>...</bravesearchagent>``

**Configuration Requirements**:
   * Brave Search API key must be configured
   * See :doc:`brave_search_agent` for detailed setup instructions

**Example Queries**:
   * "Search for renewable energy innovations"
   * "Find privacy-focused alternatives to mainstream services"
   * "Look up independent journalism about tech industry"

**Example Configuration**:

.. code-block:: json

   {
     "agents": ["brave_search"],
     "api_keys": {
       "brave_search_api_key": "YOUR_API_KEY_HERE"
     }
   }

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

DocumentRetrieverAgent
~~~~~~~~~~~~~~~~~~~~~~

**Purpose**: Document search and retrieval from configured document collections with support for various file formats including PDFs with configurable chunking.

**Capabilities**:
   * Searches through document collections using BM25 indexing
   * Retrieves relevant text passages based on semantic similarity
   * Generates responses based on retrieved content
   * Supports multiple document sources and formats
   * **PDF Support**: Process PDF files with configurable page-level chunking
   * **File Upload**: Dynamic file upload through frontend interface
   * **Flexible Chunking**: Configure how PDF content is split (whole document, page-by-page, or custom chunk sizes)
   * **Status Reporting**: Reports available sources to the orchestrator for better decision-making

**Usage Tags**: ``<documentretrieveragent>...</documentretrieveragent>``

**Supported File Formats**:
   * Text files: ``.txt``, ``.md``, ``.html``, ``.htm``
   * PDF files: ``.pdf`` (with configurable chunking)

**Configuration**:

.. code-block:: python

   from yaaaf.components.sources.rag_source import RAGSource
   
   # Create RAG sources from different file types
   sources = []
   
   # Text file source
   text_source = RAGSource("Document collection", "documents/")
   sources.append(text_source)
   
   # PDF file with configurable chunking
   pdf_source = RAGSource("PDF manual", "manual.pdf")
   with open("manual.pdf", "rb") as f:
       pdf_content = f.read()
       # pages_per_chunk: -1 = whole document, 1 = page-by-page, N = N pages per chunk
       pdf_source.add_pdf(pdf_content, "manual.pdf", pages_per_chunk=-1)
   sources.append(pdf_source)
   
   document_retriever_agent = DocumentRetrieverAgent(client, sources)

**File Upload via Frontend**:

The Document Retriever agent supports dynamic file uploads through the frontend interface:

1. **Upload Interface**: Click the paperclip icon in the chat input area
2. **File Selection**: Drag and drop or click to select supported files
3. **PDF Options**: For PDF files, choose between:
   
   * **Whole document** (default): Process entire PDF as one searchable chunk
   * **Page by page**: Split PDF into individual page chunks for more granular retrieval

4. **Description**: Add a description after upload to help with retrieval
5. **Automatic Indexing**: Files are automatically indexed and available for queries

**PDF Chunking Strategies**:

* **Whole Document** (``pages_per_chunk=-1``): Best for shorter documents or when context across pages is important
* **Page-by-Page** (``pages_per_chunk=1``): Better for longer documents, technical manuals, or when specific page references are needed
* **Custom Chunks** (``pages_per_chunk=N``): Group multiple pages together for balanced context and granularity

**Example Queries**:
   * "What does the manual say about installation?"
   * "Find information about troubleshooting network issues"
   * "Search for pricing information in the uploaded documents"
   * "What are the safety guidelines mentioned in the PDF?"

**API Integration**:

The Document Retriever agent integrates with the file upload API:

.. code-block:: bash

   # Upload a file with default chunking (whole document for PDFs)
   curl -X POST "http://localhost:4000/upload_file_to_rag" \
        -F "file=@document.pdf" \
        -F "pages_per_chunk=-1"

**Status Reporting**:

The Document Retriever agent reports its available sources to the orchestrator, helping it make better routing decisions:

.. code-block:: text

   Available document sources (3 total):
     1. Uploaded file: manual.pdf
     2. File/Directory: Technical documentation
     3. Uploaded file: company_policies.txt

TodoAgent
~~~~~~~~~

**Purpose**: Creates structured todo lists for planning complex query responses.

**Capabilities**:
   * Analyzes complex queries and breaks them down into actionable todo items
   * Creates prioritized task lists with specific agent assignments
   * Generates structured markdown tables with ID, Task, Status, Priority, and Agent/Tool columns
   * Helps orchestrate multi-step workflows
   * Provides strategic planning for complex multi-agent tasks
   * Single-use agent (budget of 1 call per query)

**Usage Tags**: ``<todoagent>...</todoagent>``

**Key Features**:
   * **Strategic Planning**: Breaks complex queries into manageable steps
   * **Agent Assignment**: Identifies which specific agents should handle each task
   * **Priority Management**: Assigns priority levels (high, medium, low) to tasks
   * **Status Tracking**: Maintains task status (pending, in_progress, completed)
   * **Artifact Creation**: Generates structured todo-list artifacts for reference

**Table Structure**:

The TodoAgent creates markdown tables with the following columns:

.. code-block:: text

   | ID | Task | Status | Priority | Agent/Tool |
   | --- | ---- | ------ | -------- | ----------- |
   | 1 | Analyze sales data | pending | high | SqlAgent |
   | 2 | Create visualization | pending | medium | VisualizationAgent |
   | 3 | Research market trends | pending | low | WebSearchAgent |

**Example Queries**:
   * "Plan how to analyze customer churn and create recommendations"
   * "Break down the steps needed to create a comprehensive sales report"
   * "Create a todo list for implementing a new feature analysis workflow"

**Usage Notes**:
   * **Single Call**: TodoAgent has a budget of 1 call per query - use it strategically
   * **First Step**: Best used as the first agent in complex workflows
   * **Planning Focus**: Designed for planning, not execution
   * **Agent Awareness**: Knows about all available agents and their capabilities

**Example**:

.. code-block:: text

   <todoagent>
   I need to analyze our customer database, create visualizations, and provide insights. 
   Please create a structured plan for this analysis.
   </todoagent>

**Workflow Integration**:

The TodoAgent is typically used in this pattern:

1. **Initial Planning**: TodoAgent creates structured todo list
2. **Task Execution**: Other agents execute individual tasks from the list
3. **Progress Tracking**: Each task's status can be updated as work progresses
4. **Reference**: Todo list artifact serves as a roadmap for the entire workflow

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
   
   # Document Retriever Agent with document sources
   text_sources = [TextSource("documents/folder1/"), TextSource("documents/folder2/")]
   document_retriever_agent = DocumentRetrieverAgent(client, text_sources)

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