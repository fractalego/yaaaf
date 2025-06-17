API Reference
=============

This section provides detailed API documentation for YAAAF's core components.

Core Data Types
---------------

.. automodule:: yaaf.components.data_types
   :members:
   :undoc-members:
   :show-inheritance:

Messages Module
~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.data_types.messages
   :members:
   :undoc-members:
   :show-inheritance:

Notes Module
~~~~~~~~~~~~

.. automodule:: yaaf.components.data_types.notes
   :members:
   :undoc-members:
   :show-inheritance:

Base Agent
----------

.. automodule:: yaaf.components.agents.base_agent
   :members:
   :undoc-members:
   :show-inheritance:

Agents
------

Orchestrator Agent
~~~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.agents.orchestrator_agent
   :members:
   :undoc-members:
   :show-inheritance:

SQL Agent
~~~~~~~~

.. automodule:: yaaf.components.agents.sql_agent
   :members:
   :undoc-members:
   :show-inheritance:

Visualization Agent
~~~~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.agents.visualization_agent
   :members:
   :undoc-members:
   :show-inheritance:

Web Search Agent
~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.agents.websearch_agent
   :members:
   :undoc-members:
   :show-inheritance:

Reflection Agent
~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.agents.reflection_agent
   :members:
   :undoc-members:
   :show-inheritance:

RAG Agent
~~~~~~~~

.. automodule:: yaaf.components.agents.rag_agent
   :members:
   :undoc-members:
   :show-inheritance:

Reviewer Agent
~~~~~~~~~~~~~

.. automodule:: yaaf.components.agents.reviewer_agent
   :members:
   :undoc-members:
   :show-inheritance:

URL Reviewer Agent
~~~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.agents.url_reviewer_agent
   :members:
   :undoc-members:
   :show-inheritance:

MLE Agent
~~~~~~~~

.. automodule:: yaaf.components.agents.mle_agent
   :members:
   :undoc-members:
   :show-inheritance:

Tool Agent
~~~~~~~~~~

.. automodule:: yaaf.components.agents.tool_agent
   :members:
   :undoc-members:
   :show-inheritance:

Artifacts
---------

.. automodule:: yaaf.components.agents.artefacts
   :members:
   :undoc-members:
   :show-inheritance:

Client
------

.. automodule:: yaaf.components.client
   :members:
   :undoc-members:
   :show-inheritance:

Server
------

Routes
~~~~~~

.. automodule:: yaaf.server.routes
   :members:
   :undoc-members:
   :show-inheritance:

Accessories
~~~~~~~~~~

.. automodule:: yaaf.server.accessories
   :members:
   :undoc-members:
   :show-inheritance:

Configuration
~~~~~~~~~~~~

.. automodule:: yaaf.server.config
   :members:
   :undoc-members:
   :show-inheritance:

Sources
-------

SQLite Source
~~~~~~~~~~~~

.. automodule:: yaaf.components.sources.sqlite_source
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
---------

Orchestrator Builder
~~~~~~~~~~~~~~~~~~~

.. automodule:: yaaf.components.orchestrator_builder
   :members:
   :undoc-members:
   :show-inheritance:

Goal Extractor
~~~~~~~~~~~~~~

.. automodule:: yaaf.components.extractors.goal_extractor
   :members:
   :undoc-members:
   :show-inheritance:

HTTP API
--------

The YAAAF backend provides a RESTful HTTP API for frontend communication.

Create Stream
~~~~~~~~~~~~

**Endpoint**: ``POST /create_stream``

**Description**: Initiates a new conversation stream with the orchestrator.

**Request Body**:

.. code-block:: json

   {
     "stream_id": "unique_stream_identifier",
     "messages": [
       {
         "role": "user",
         "content": "Your query here"
       }
     ]
   }

**Response**: Status 200 on success

Get Utterances
~~~~~~~~~~~~~

**Endpoint**: ``POST /get_utterances``

**Description**: Retrieves all notes/utterances for a given stream.

**Request Body**:

.. code-block:: json

   {
     "stream_id": "unique_stream_identifier"
   }

**Response**:

.. code-block:: json

   [
     {
       "message": "Agent response content",
       "artefact_id": "artifact_id_or_null",
       "agent_name": "AgentName"
     }
   ]

Get Artifact
~~~~~~~~~~~

**Endpoint**: ``POST /get_artifact``

**Description**: Retrieves a specific artifact by ID.

**Request Body**:

.. code-block:: json

   {
     "artefact_id": "artifact_identifier"
   }

**Response**:

.. code-block:: json

   {
     "data": "HTML_table_data",
     "code": "SQL_or_Python_code",
     "image": "base64_encoded_image"
   }

Get Image
~~~~~~~~

**Endpoint**: ``POST /get_image``

**Description**: Retrieves a specific image artifact.

**Request Body**:

.. code-block:: json

   {
     "image_id": "image_identifier"
   }

**Response**: Base64 encoded image string

Get Query Suggestions
~~~~~~~~~~~~~~~~~~~~

**Endpoint**: ``GET /get_query_suggestions``

**Description**: Retrieves suggested queries for the user interface.

**Response**:

.. code-block:: json

   [
     "How many records are in the database?",
     "Show me a visualization of the data",
     "Search for recent news about AI"
   ]

Error Handling
--------------

API Error Responses
~~~~~~~~~~~~~~~~~~

All API endpoints return appropriate HTTP status codes:

* ``200``: Success
* ``400``: Bad Request (invalid parameters)
* ``404``: Not Found (resource doesn't exist)
* ``500``: Internal Server Error

Error responses include descriptive messages:

.. code-block:: json

   {
     "error": "Description of what went wrong",
     "details": "Additional error context"
   }

Agent Error Handling
~~~~~~~~~~~~~~~~~~~

Agents handle errors gracefully:

* **Logging**: All errors are logged with context
* **Recovery**: Agents attempt to continue operation when possible
* **User Feedback**: Meaningful error messages are returned to users
* **Fallbacks**: Default responses when primary functionality fails

Configuration API
-----------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~

* ``YAAAF_CONFIG``: Path to configuration JSON file

Configuration File Format
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

    {
      "client": {
        "model": "qwen2.5:32b",
        "temperature": 0.7,
        "max_tokens": 1024
      },
      "agents": [
        "reflection",
        "visualization",
        "sql",
        "reviewer",
        "websearch",
        "url_reviewer"
      ],
      "sources": [
        {
          "name": "london_archaeological_data",
          "type": "sqlite",
          "path": "../../data/london_archaeological_data.db"
        }
      ]
    }

Data Models
-----------

Core Types
~~~~~~~~~

**Note**: Represents a single message/response from an agent

.. code-block:: python

   class Note:
       message: str                    # The actual content
       artefact_id: Optional[str]      # Reference to stored artifact
       agent_name: Optional[str]       # Which agent generated this

**Messages**: Container for conversation history

.. code-block:: python

   class Messages:
       utterances: List[Utterance]     # List of conversation turns

**Utterance**: Single turn in conversation

.. code-block:: python

   class Utterance:
       role: str                       # "user", "assistant", "system"
       content: str                    # Message content

**Artefact**: Stored content from agents

.. code-block:: python

   class Artefact:
       type: str                       # "table", "image", etc.
       data: Optional[Any]             # Structured data
       code: Optional[str]             # Code that generated this
       description: Optional[str]      # Human-readable description
       image: Optional[str]            # Base64 encoded image
       id: str                         # Unique identifier