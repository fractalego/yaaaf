Agents Reference
================

This page provides detailed documentation for every agent in YAAAF. Each agent is described with its role in the artifact flow, input/output types, configuration, and usage examples.

EXTRACTORS
----------

Extractors are source agents that pull data from external systems into the artifact flow.

SqlAgent
~~~~~~~~

**Role**: EXTRACTOR

**Purpose**: Executes SQL queries against configured databases and returns tabular data.

**Accepts**: None (source agent)

**Produces**: table

**Description**:
SqlAgent converts natural language questions into SQL queries, executes them against configured SQLite databases, and returns the results as table artifacts. It understands database schemas and can handle complex queries involving joins, aggregations, and filters.

**Configuration**:

.. code-block:: python

   from yaaaf.components.sources.sqlite_source import SqliteSource
   from yaaaf.components.agents.sql_agent import SqlAgent

   source = SqliteSource(name="sales_db", db_path="data/sales.db")
   sql_agent = SqlAgent(client=client, sources=[source])

**Example workflow usage**:

.. code-block:: yaml

   assets:
     sales_data:
       agent: SqlAgent
       description: "Get monthly sales totals"
       type: table

**Capabilities**:

- Schema introspection (automatically discovers tables and columns)
- Natural language to SQL conversion
- Query validation and error handling
- Support for multiple database sources
- Parameterized queries for safety

DocumentRetrieverAgent
~~~~~~~~~~~~~~~~~~~~~~

**Role**: EXTRACTOR

**Purpose**: Retrieves relevant text chunks from document collections using BM25 search.

**Accepts**: None (source agent)

**Produces**: text

**Description**:
DocumentRetrieverAgent searches through configured document collections to find passages relevant to the query. It uses BM25 (Best Match 25) ranking to identify the most relevant chunks from text files, PDFs, and other document formats.

**Configuration**:

.. code-block:: python

   from yaaaf.components.sources.rag_source import RAGSource
   from yaaaf.components.agents.document_retriever_agent import DocumentRetrieverAgent

   source = RAGSource(description="Technical manuals", source_path="docs/")
   # Add text files
   source.add_text(open("manual.txt").read())
   # Add PDFs (with optional page chunking)
   with open("guide.pdf", "rb") as f:
       source.add_pdf(f.read(), "guide.pdf", pages_per_chunk=1)

   agent = DocumentRetrieverAgent(client=client, sources=[source])

**Example workflow usage**:

.. code-block:: yaml

   assets:
     relevant_docs:
       agent: DocumentRetrieverAgent
       description: "Find documentation about installation"
       type: text

**Supported formats**:

- Plain text (.txt)
- Markdown (.md)
- HTML (.html, .htm)
- PDF (.pdf) with configurable page chunking

BraveSearchAgent
~~~~~~~~~~~~~~~~

**Role**: EXTRACTOR

**Purpose**: Searches the web using Brave Search API.

**Accepts**: None (source agent)

**Produces**: table

**Description**:
BraveSearchAgent queries the Brave Search API to find relevant web pages. It returns structured results including titles, URLs, and snippets. Brave Search uses its own independent search index, providing results that may differ from Google or Bing.

**Configuration**:

Requires ``BRAVE_SEARCH_API_KEY`` environment variable or configuration.

.. code-block:: json

   {
     "api_keys": {
       "brave_search_api_key": "YOUR_API_KEY"
     }
   }

**Example workflow usage**:

.. code-block:: yaml

   assets:
     search_results:
       agent: BraveSearchAgent
       description: "Search for recent AI developments"
       type: table

DuckDuckGoSearchAgent
~~~~~~~~~~~~~~~~~~~~~

**Role**: EXTRACTOR

**Purpose**: Searches the web using DuckDuckGo.

**Accepts**: None (source agent)

**Produces**: table

**Description**:
DuckDuckGoSearchAgent performs web searches using DuckDuckGo's search API. It does not require API keys and provides privacy-focused search results. Results are returned as a table with titles, URLs, and snippets.

**Example workflow usage**:

.. code-block:: yaml

   assets:
     web_results:
       agent: DuckDuckGoSearchAgent
       description: "Find information about climate change"
       type: table

**Note**: No API key required. Rate limits may apply.

UrlAgent
~~~~~~~~

**Role**: EXTRACTOR

**Purpose**: Fetches and extracts content from specific URLs.

**Accepts**: None (source agent)

**Produces**: text

**Description**:
UrlAgent retrieves content from web pages given their URLs. It extracts the main text content, handling HTML parsing and content extraction. Useful when you need content from specific known URLs rather than search results.

**Example workflow usage**:

.. code-block:: yaml

   assets:
     page_content:
       agent: UrlAgent
       description: "Fetch content from the documentation page"
       type: text
       params:
         url: "https://example.com/docs"

UserInputAgent
~~~~~~~~~~~~~~

**Role**: EXTRACTOR

**Purpose**: Collects information from users interactively.

**Accepts**: None (source agent)

**Produces**: text

**Description**:
UserInputAgent pauses workflow execution to request input from the user. This enables interactive workflows where user decisions or additional information is needed mid-execution. The workflow resumes once the user provides input.

**Interaction Mode**: INTERACTIVE (pauses for user input)

**Example workflow usage**:

.. code-block:: yaml

   assets:
     user_preference:
       agent: UserInputAgent
       description: "Ask user which format they prefer"
       type: text

TRANSFORMERS
------------

Transformers convert artifacts from one form to another.

MleAgent
~~~~~~~~

**Role**: TRANSFORMER

**Purpose**: Trains machine learning models on tabular data.

**Accepts**: table

**Produces**: model

**Description**:
MleAgent analyzes tabular data and trains scikit-learn models. It can perform classification, regression, and clustering tasks. The agent automatically selects appropriate algorithms based on the data characteristics and creates model artifacts that can be used for predictions.

**Output Permanence**: PERSISTENT (models are saved)

**Example workflow usage**:

.. code-block:: yaml

   assets:
     training_data:
       agent: SqlAgent
       description: "Get customer data with churn labels"
       type: table

     churn_model:
       agent: MleAgent
       description: "Train model to predict customer churn"
       type: model
       inputs: [training_data]

**Capabilities**:

- Automatic feature selection
- Model selection based on task type
- Cross-validation for model evaluation
- Feature importance analysis

ReviewerAgent
~~~~~~~~~~~~~

**Role**: TRANSFORMER

**Purpose**: Analyzes and validates artifacts.

**Accepts**: table, text

**Produces**: table

**Description**:
ReviewerAgent examines artifacts and provides analysis, validation, or summary. It can identify patterns, check data quality, extract key information, and generate structured reports about the input artifacts.

**Example workflow usage**:

.. code-block:: yaml

   assets:
     raw_data:
       agent: SqlAgent
       description: "Get raw sales data"
       type: table

     data_analysis:
       agent: ReviewerAgent
       description: "Analyze data quality and identify issues"
       type: table
       inputs: [raw_data]

ToolAgent
~~~~~~~~~

**Role**: TRANSFORMER

**Purpose**: Executes external tools via Model Context Protocol (MCP).

**Accepts**: table, text

**Produces**: table

**Description**:
ToolAgent interfaces with external tools and services through the MCP protocol. It can call functions provided by MCP servers, enabling integration with calculators, APIs, file systems, and other external capabilities.

**Configuration**:

.. code-block:: json

   {
     "tools": [
       {
         "name": "calculator",
         "type": "sse",
         "url": "http://localhost:8080/sse"
       },
       {
         "name": "file_tools",
         "type": "stdio",
         "command": "python",
         "args": ["-m", "mcp_server"]
       }
     ]
   }

**Example workflow usage**:

.. code-block:: yaml

   assets:
     calculation_result:
       agent: ToolAgent
       description: "Calculate compound interest"
       type: table

NumericalSequencesAgent
~~~~~~~~~~~~~~~~~~~~~~~

**Role**: TRANSFORMER

**Purpose**: Structures unformatted numerical data into tables.

**Accepts**: text

**Produces**: table

**Description**:
NumericalSequencesAgent parses unstructured text containing numerical data and converts it into structured tabular format. It identifies patterns, extracts numbers, and organizes them into meaningful columns.

**Example workflow usage**:

.. code-block:: yaml

   assets:
     raw_text:
       agent: DocumentRetrieverAgent
       description: "Get financial report text"
       type: text

     structured_data:
       agent: NumericalSequencesAgent
       description: "Extract numerical data into table"
       type: table
       inputs: [raw_text]

SYNTHESIZERS
------------

Synthesizers combine multiple artifacts into unified outputs.

AnswererAgent
~~~~~~~~~~~~~

**Role**: SYNTHESIZER

**Purpose**: Combines multiple artifacts into comprehensive answers.

**Accepts**: table, text

**Produces**: table

**Description**:
AnswererAgent is the primary synthesis agent. It takes artifacts from multiple sources (documents, databases, web searches) and generates comprehensive, well-cited answers. Output is a structured table with paragraphs and their sources.

**Example workflow usage**:

.. code-block:: yaml

   assets:
     doc_results:
       agent: DocumentRetrieverAgent
       description: "Get relevant documentation"
       type: text

     db_results:
       agent: SqlAgent
       description: "Get supporting data"
       type: table

     comprehensive_answer:
       agent: AnswererAgent
       description: "Synthesize findings into complete answer"
       type: table
       inputs: [doc_results, db_results]

**Output format**:

.. code-block:: text

   | paragraph | source |
   |-----------|--------|
   | Finding from analysis... | Database: sales_2023 |
   | Additional context... | Document: manual.pdf |

UrlReviewerAgent
~~~~~~~~~~~~~~~~

**Role**: SYNTHESIZER

**Purpose**: Aggregates and summarizes content from multiple URLs.

**Accepts**: table (with URLs)

**Produces**: table

**Description**:
UrlReviewerAgent takes search results containing URLs, fetches the content from each URL, and synthesizes the information into a unified summary. It is typically used after a search agent to process the found pages.

**Example workflow usage**:

.. code-block:: yaml

   assets:
     search_results:
       agent: BraveSearchAgent
       description: "Search for product reviews"
       type: table

     review_summary:
       agent: UrlReviewerAgent
       description: "Summarize content from search results"
       type: table
       inputs: [search_results]

PlannerAgent
~~~~~~~~~~~~

**Role**: SYNTHESIZER

**Purpose**: Creates execution workflows from natural language goals.

**Accepts**: text (goals)

**Produces**: text (YAML workflow)

**Description**:
PlannerAgent analyzes user goals and generates YAML workflow definitions. It uses RAG-based example retrieval from 50,000+ planning scenarios to produce high-quality workflows. The planner understands agent capabilities and artifact type compatibility.

**Note**: PlannerAgent is used internally by the orchestrator. It is not typically called directly in workflows.

**Capabilities**:

- Goal extraction and analysis
- Agent capability matching
- Artifact type compatibility checking
- DAG construction with proper dependencies
- RAG-based example retrieval for better plans

GENERATORS
----------

Generators create final outputs or side effects.

VisualizationAgent
~~~~~~~~~~~~~~~~~~

**Role**: GENERATOR

**Purpose**: Creates charts and visualizations from data.

**Accepts**: table

**Produces**: image

**Description**:
VisualizationAgent generates matplotlib-based visualizations from tabular data. It can create bar charts, line graphs, scatter plots, pie charts, and other visualization types. Output is saved as PNG images.

**Output Permanence**: PERSISTENT (images are saved)

**Example workflow usage**:

.. code-block:: yaml

   assets:
     sales_data:
       agent: SqlAgent
       description: "Get quarterly sales"
       type: table

     sales_chart:
       agent: VisualizationAgent
       description: "Create bar chart of sales by quarter"
       type: image
       inputs: [sales_data]

**Supported chart types**:

- Bar charts (vertical and horizontal)
- Line graphs
- Scatter plots
- Pie charts
- Histograms
- Box plots

BashAgent
~~~~~~~~~

**Role**: GENERATOR

**Purpose**: Performs filesystem operations.

**Accepts**: text

**Produces**: text

**Description**:
BashAgent executes filesystem operations like reading files, listing directories, and writing output. It operates in a sandboxed environment and may request user confirmation for sensitive operations.

**Interaction Mode**: INTERACTIVE (may request confirmation)

**Output Permanence**: PERSISTENT (files are created/modified)

**Example workflow usage**:

.. code-block:: yaml

   assets:
     report_data:
       agent: AnswererAgent
       description: "Generate report content"
       type: table

     saved_report:
       agent: BashAgent
       description: "Save report to file"
       type: text
       inputs: [report_data]

**Security**: BashAgent operates with restricted permissions and may prompt for user confirmation before executing operations.

Agent Configuration
-------------------

Per-Agent Model Settings
~~~~~~~~~~~~~~~~~~~~~~~~

Each agent can use different model settings:

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
       }
     ]
   }

Agent Budgets
~~~~~~~~~~~~~

Agents have execution budgets limiting their LLM calls:

- **Default budget**: 2 calls per query
- **PlannerAgent**: 1 call (planning should be decisive)
- **Complex agents**: May have higher budgets for multi-step reasoning

Creating Custom Agents
----------------------

To create a new agent:

1. **Choose a base class**:

   - ``ToolBasedAgent``: For agents using the executor pattern
   - ``CustomAgent``: For agents with custom logic

2. **Define taxonomy**:

   .. code-block:: python

      # In agent_taxonomies.py
      "MyAgent": AgentTaxonomy(
          data_flow=DataFlow.TRANSFORMER,
          interaction_mode=InteractionMode.AUTONOMOUS,
          output_permanence=OutputPermanence.EPHEMERAL,
          description="Transforms X into Y"
      )

3. **Implement the agent**:

   .. code-block:: python

      class MyAgent(ToolBasedAgent):
          def __init__(self, client):
              super().__init__(client, MyExecutor())
              self._system_prompt = my_prompt_template

          @staticmethod
          def get_info() -> str:
              return "Transforms X into Y"

4. **Register in orchestrator builder**:

   .. code-block:: python

      # In orchestrator_builder.py
      self._agents_map["my_agent"] = MyAgent

5. **Add examples to planner dataset**:

   The planner uses RAG-based example retrieval to generate workflows. For the planner to know how to use your custom agent, you must add examples to the planner dataset.

   Edit ``yaaaf/data/planner_dataset.csv`` and add rows with:

   - ``scenario``: A natural language description of when to use your agent
   - ``workflow_yaml``: A YAML workflow showing your agent in action
   - ``agents_used``: List including your agent name
   - ``num_agents``: Number of agents in the workflow
   - ``num_steps``: Number of steps
   - ``complexity``: Workflow complexity (simple_chain, parallel, etc.)
   - ``is_valid``: Set to ``True``
   - ``error_message``: Leave empty

   **Example entry**:

   .. code-block:: text

      scenario,workflow_yaml,agents_used,num_agents,num_steps,complexity,is_valid,error_message
      "Transform the raw sensor data into a normalized format for analysis","assets:
        raw_data:
          agent: SqlAgent
          description: ""Get raw sensor readings""
          type: table
        normalized_data:
          agent: MyAgent
          description: ""Normalize sensor data""
          type: table
          inputs: [raw_data]","['SqlAgent', 'MyAgent']",2,2,simple_chain,True,

   Add 5-10 diverse examples showing your agent in different workflow contexts. This ensures the planner can correctly incorporate your agent into generated workflows.

   **Important**: Without examples in the dataset, the planner will not know when or how to use your custom agent in workflows.
