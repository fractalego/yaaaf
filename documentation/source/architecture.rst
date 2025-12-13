Architecture
============

YAAAF is an **artifact-first** framework. The architecture is designed around one principle: artifacts flow through planned railways from sources to destinations. Agents are stations, not destinations.

System Overview
---------------

::

   +------------------+     HTTP      +------------------+
   |     Frontend     | <-----------> |     Backend      |
   |    (Next.js)     |               |    (FastAPI)     |
   +------------------+               +------------------+
                                              |
                                              v
                                    +------------------+
                                    |   Orchestrator   |
                                    +------------------+
                                              |
                           +------------------+------------------+
                           |                                     |
                           v                                     v
                  +------------------+                  +------------------+
                  |     Planner      |                  |  Workflow Engine |
                  |     Agent        |                  +------------------+
                  +------------------+                           |
                           |                                     v
                           v                           +------------------+
                  +------------------+                 |      Agents      |
                  |  YAML Workflow   | --------------> | (execute in DAG  |
                  |  (DAG definition)|                 |      order)      |
                  +------------------+                 +------------------+
                                                                |
                                                                v
                                                      +------------------+
                                                      | Artifact Storage |
                                                      +------------------+

Core Components
---------------

Orchestrator
~~~~~~~~~~~~

The orchestrator is the entry point for all queries. It:

1. Receives the user query
2. Extracts the goal and determines target artifact type
3. Invokes the planner to generate a workflow
4. Passes the workflow to the workflow engine
5. Returns the final artifact to the user

Planner Agent
~~~~~~~~~~~~~

The planner generates YAML workflows from natural language goals:

- Analyzes the user's intent
- Determines required artifact types
- Selects appropriate agents
- Constructs a valid DAG with dependencies
- Uses RAG-based example retrieval for quality

Workflow Engine
~~~~~~~~~~~~~~~

The workflow engine executes the planned DAG:

- Parses YAML workflow definition
- Topologically sorts assets by dependencies
- Executes agents in correct order
- Passes artifacts between agents
- Handles errors and retries

Artifact Storage
~~~~~~~~~~~~~~~~

Centralized storage for all generated artifacts:

- Tables (pandas DataFrames)
- Images (PNG files)
- Models (sklearn pickled models)
- Text (documents, summaries)
- JSON (structured data)

Artifacts are stored by unique ID and referenced throughout the workflow.

Data Flow
---------

::

   User Query: "Show sales by region as a chart"
           |
           v
   +-------------------+
   | Goal Extraction   |
   | Goal: visualize   |
   | Target: image     |
   +-------------------+
           |
           v
   +-------------------+
   | RAG Retrieval     |
   | Find similar      |
   | examples          |
   +-------------------+
           |
           v
   +-------------------+
   | Plan Generation   |
   | SqlAgent -> table |
   | VisAgent -> image |
   +-------------------+
           |
           v
   +-------------------+
   | Workflow Exec     |
   | Step 1: SqlAgent  |
   | Step 2: VisAgent  |
   +-------------------+
           |
           v
   +-------------------+
   | Final Artifact    |
   | Image: chart.png  |
   +-------------------+

Request Processing
~~~~~~~~~~~~~~~~~~

1. **Frontend**: User submits query via chat interface
2. **API**: Backend receives POST to ``/create_stream``
3. **Orchestrator**: Analyzes query, invokes planner
4. **Planner**: Generates YAML workflow using RAG examples
5. **Engine**: Executes workflow DAG
6. **Agents**: Process their assigned steps, produce artifacts
7. **Storage**: Artifacts stored with unique IDs
8. **Streaming**: Results streamed back as Notes
9. **Frontend**: Displays formatted response with artifacts

Agent System
------------

Base Classes
~~~~~~~~~~~~

**ToolBasedAgent**: For agents using the executor pattern

.. code-block:: python

   class ToolBasedAgent(BaseAgent):
       def __init__(self, client, executor):
           self._client = client
           self._executor = executor

**CustomAgent**: For agents with complex custom logic

.. code-block:: python

   class CustomAgent(BaseAgent):
       async def _query_custom(self, messages, notes):
           # Custom implementation
           pass

Executor Pattern
~~~~~~~~~~~~~~~~

Agents delegate operations to executors:

.. code-block:: python

   class ToolExecutor:
       async def prepare_context(self, messages, notes) -> dict
       def extract_instruction(self, response) -> str
       async def execute_operation(self, instruction, context) -> tuple
       def validate_result(self, result) -> bool
       def transform_to_artifact(self, result, instruction, id) -> Artefact

This pattern separates:

- **Agent**: LLM interaction and reasoning
- **Executor**: Tool-specific operations

Taxonomy System
~~~~~~~~~~~~~~~

Agents are classified by their role:

.. list-table::
   :header-rows: 1

   * - Role
     - Description
     - Examples
   * - EXTRACTOR
     - Pull data from sources
     - SqlAgent, DocumentRetrieverAgent
   * - TRANSFORMER
     - Convert artifacts
     - MleAgent, ReviewerAgent
   * - SYNTHESIZER
     - Combine artifacts
     - AnswererAgent, PlannerAgent
   * - GENERATOR
     - Create final outputs
     - VisualizationAgent, BashAgent

Message Structure
-----------------

Messages
~~~~~~~~

.. code-block:: python

   class Messages:
       utterances: List[Utterance]

   class Utterance:
       role: str     # "user", "assistant", "system"
       content: str

Notes
~~~~~

.. code-block:: python

   class Note:
       message: str
       artefact_id: Optional[str]
       agent_name: Optional[str]
       model_name: Optional[str]
       internal: bool

Artifacts
~~~~~~~~~

.. code-block:: python

   class Artefact:
       type: Types  # TABLE, IMAGE, MODEL, TEXT, JSON
       description: str
       code: str    # Source code or content
       data: Any    # Actual data
       id: str      # Unique identifier

Storage Architecture
--------------------

ArtefactStorage
~~~~~~~~~~~~~~~

Singleton storage for all artifacts:

.. code-block:: python

   class ArtefactStorage:
       def store_artefact(self, id: str, artefact: Artefact)
       def get_artefact(self, id: str) -> Optional[Artefact]
       def list_artefacts() -> List[str]

Artifacts are referenced by ID in agent responses:

.. code-block:: text

   <artefact type='table'>abc123</artefact>

API Endpoints
-------------

Backend API
~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Endpoint
     - Method
     - Description
   * - ``/create_stream``
     - POST
     - Create new conversation stream
   * - ``/get_stream_status``
     - POST
     - Get stream status and notes
   * - ``/artefacts/{id}``
     - GET
     - Retrieve artifact by ID
   * - ``/upload_file_to_rag``
     - POST
     - Upload document for RAG
   * - ``/health``
     - GET
     - Health check

Frontend Architecture
---------------------

Next.js Application
~~~~~~~~~~~~~~~~~~~

- Server-side rendering
- Real-time streaming via polling
- TypeScript for type safety
- Tailwind CSS for styling

Chat Interface
~~~~~~~~~~~~~~

- Message display with agent attribution
- Artifact rendering (tables, images)
- File upload support
- Markdown rendering

Project Structure
-----------------

::

   yaaaf/
     __init__.py
     __main__.py
     components/
       agents/              # All agent implementations
         base_agent.py      # Base classes
         orchestrator_agent.py
         planner_agent.py
         sql_agent.py
         ...
       data_types/          # Core data structures
         messages.py
         artefacts.py
       executors/           # Tool executors
         sql_executor.py
         python_executor.py
       retrievers/          # RAG components
         local_vector_db.py
         planner_example_retriever.py
       sources/             # Data source connectors
         sqlite_source.py
         rag_source.py
     server/                # FastAPI backend
       routes.py
       run.py
     data/                  # Packaged data files
       planner_dataset.csv
     connectors/            # External integrations
       mcp_connector.py

   frontend/
     apps/www/              # Next.js application
       components/
       app/
     packages/              # Shared packages

Extensibility
-------------

Adding New Agents
~~~~~~~~~~~~~~~~~

1. Define taxonomy in ``agent_taxonomies.py``
2. Create executor in ``executors/``
3. Implement agent class extending ``ToolBasedAgent``
4. Register in ``orchestrator_builder.py``

Adding New Sources
~~~~~~~~~~~~~~~~~~

1. Implement source class with required interface
2. Add type handling in configuration loader
3. Wire to appropriate agents

Adding New Artifact Types
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Add type to ``Artefact.Types`` enum
2. Implement serialization in storage
3. Add rendering support in frontend
