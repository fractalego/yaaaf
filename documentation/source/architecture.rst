Architecture
============

YAAAF follows a modular, agent-based architecture designed for scalability and extensibility.

System Overview
---------------

.. code-block:: text

   ┌─────────────────┐    HTTP/WebSocket    ┌──────────────────┐
   │                 │ ◄─────────────────► │                  │
   │  Frontend       │                     │  Backend         │
   │  (Next.js)      │                     │  (FastAPI)       │
   │                 │                     │                  │
   └─────────────────┘                     └──────────────────┘
                                                     │
                                                     ▼
                                           ┌──────────────────┐
                                           │  Orchestrator    │
                                           │  Agent           │
                                           └──────────────────┘
                                                     │
                                ┌────────────────────┼────────────────────┐
                                ▼                    ▼                    ▼
                      ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
                      │  SQL Agent      │  │ Visualization   │  │ Web Search      │
                      │                 │  │ Agent           │  │ Agent           │
                      └─────────────────┘  └─────────────────┘  └─────────────────┘
                                ▼                    ▼                    ▼
                      ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
                      │ Artifact        │  │ Artifact        │  │ Artifact        │
                      │ Storage         │  │ Storage         │  │ Storage         │
                      └─────────────────┘  └─────────────────┘  └─────────────────┘

Core Components
---------------

Backend Architecture
~~~~~~~~~~~~~~~~~~~~

**FastAPI Server**
   The main HTTP server that handles API requests and provides streaming endpoints.

**Orchestrator Agent**
   Central coordinator that:
   
   * Receives user queries
   * Determines which agents to call
   * Manages the conversation flow
   * Returns structured responses

**Specialized Agents**
   Independent agents that handle specific tasks:
   
   * Process specific types of requests
   * Generate artifacts (tables, images, etc.)
   * Return structured responses

**Artifact Storage**
   Centralized storage system for generated content:
   
   * Tables from SQL queries
   * Images from visualizations
   * Search results from web queries

Frontend Architecture
~~~~~~~~~~~~~~~~~~~~

**Next.js Application**
   Modern React-based frontend with:
   
   * Server-side rendering
   * Real-time streaming support
   * Component-based UI architecture

**Chat Interface**
   Real-time chat components that:
   
   * Display agent responses with formatting
   * Handle streaming updates
   * Show artifacts inline

**API Layer**
   TypeScript interfaces for:
   
   * Backend communication
   * Data type safety
   * Error handling

Data Flow
---------

Request Processing
~~~~~~~~~~~~~~~~~

1. **User Input**: User types a query in the frontend chat interface
2. **API Call**: Frontend sends request to backend ``/create_stream`` endpoint
3. **Orchestration**: OrchestratorAgent analyzes the query and determines appropriate agents
4. **Agent Execution**: Specialized agents process their part of the request
5. **Artifact Generation**: Agents create artifacts (tables, images, etc.) stored centrally
6. **Response Streaming**: Results are streamed back to frontend in real-time
7. **UI Update**: Frontend displays formatted responses with agent attribution

Message Structure
~~~~~~~~~~~~~~~~

**Note Object**:

.. code-block:: python

   class Note:
       message: str              # The actual content
       artefact_id: str | None   # Reference to stored artifact
       agent_name: str | None    # Which agent generated this

**Messages**:

.. code-block:: python

   class Messages:
       utterances: List[Utterance]  # Conversation history

**Utterance**:

.. code-block:: python

   class Utterance:
       role: str     # "user", "assistant", "system"
       content: str  # Message content

Agent System
------------

Base Agent Pattern
~~~~~~~~~~~~~~~~~

All agents inherit from ``BaseAgent`` and implement:

.. code-block:: python

   class BaseAgent:
       async def query(self, messages: Messages, notes: Optional[List[Note]] = None) -> str:
           """Process a query and return response"""
           pass
       
       def get_name(self) -> str:
           """Return lowercase class name"""
           return self.__class__.__name__.lower()
       
       def get_opening_tag(self) -> str:
           """Return opening tag for agent identification"""
           return f"<{self.get_name()}>"
       
       def get_closing_tag(self) -> str:
           """Return closing tag for agent identification"""
           return f"</{self.get_name()}>"

Agent Registration
~~~~~~~~~~~~~~~~~

Agents are registered with the orchestrator:

.. code-block:: python

   orchestrator = OrchestratorAgent(client)
   orchestrator.subscribe_agent(SqlAgent(client, source))
   orchestrator.subscribe_agent(VisualizationAgent(client))
   orchestrator.subscribe_agent(WebSearchAgent(client))

Tag-Based Routing
~~~~~~~~~~~~~~~~

The orchestrator uses HTML-like tags to route requests:

* ``<sqlagent>Get user count</sqlagent>`` → Routes to SQL Agent
* ``<visualizationagent>Create chart</visualizationagent>`` → Routes to Visualization Agent
* ``<websearchagent>Search for AI news</websearchagent>`` → Routes to Web Search Agent

Storage Architecture
-------------------

Artifact Management
~~~~~~~~~~~~~~~~~~

**Centralized Storage**:
   All artifacts are stored in a central ``ArtefactStorage`` system with unique IDs.

**Reference-Based**:
   Notes contain ``artefact_id`` references rather than embedding full artifacts.

**Type Safety**:
   Artifacts have specific types (TABLE, IMAGE, etc.) for proper handling.

**Retrieval**:
   Frontend can fetch artifacts by ID through dedicated endpoints.

Configuration System
--------------------

**Environment-Based**:
   Configuration through environment variables and JSON files.

**Model Configuration**:
   Currently supports Ollama models only. The system uses ``OllamaClient`` for all LLM interactions.

**Agent Selection**:
   Configurable agent registration and capabilities.

**Data Sources**:
   Configurable database connections and data sources.

Extensibility
-------------

Adding New Agents
~~~~~~~~~~~~~~~~

1. **Create Agent Class**: Inherit from ``BaseAgent``
2. **Implement Query Method**: Process requests and return responses
3. **Register with Orchestrator**: Add to agent registry
4. **Update Configuration**: Include in system configuration

Adding New Data Sources
~~~~~~~~~~~~~~~~~~~~~~

1. **Implement Source Interface**: Create new data source class
2. **Update Agent Configuration**: Configure agents to use new source
3. **Add Connection Logic**: Handle authentication and connection management

Frontend Extensions
~~~~~~~~~~~~~~~~~~

1. **New Components**: Add React components for new features
2. **API Integration**: Extend TypeScript interfaces for new data types
3. **UI Updates**: Modify chat interface to handle new agent types