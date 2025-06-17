Getting Started
===============

This guide will help you get YAAF up and running on your system.

Installation
------------

Prerequisites
~~~~~~~~~~~~~

* Python 3.8 or higher
* Node.js 18 or higher (for frontend development)
* pnpm (for frontend package management)

Backend Setup
~~~~~~~~~~~~~

1. **Clone the repository**:

   .. code-block:: bash

      git clone <repository-url>
      cd agents_framework

2. **Install Python dependencies**:

   .. code-block:: bash

      pip install -r requirements.txt

3. **Set up environment variables** (optional):

   .. code-block:: bash

      export YAAF_CONFIG=path/to/your/config.json

Frontend Setup
~~~~~~~~~~~~~~

1. **Navigate to frontend directory**:

   .. code-block:: bash

      cd frontend

2. **Install dependencies**:

   .. code-block:: bash

      pnpm install

3. **Build the registry** (if needed):

   .. code-block:: bash

      pnpm build:registry

Running YAAF
------------

Using the CLI
~~~~~~~~~~~~~

The easiest way to run YAAF is using the command-line interface:

**Start the backend server**:

.. code-block:: bash

   python -m yaaf backend

This starts the backend server on the default port 4000.

**Start the frontend server**:

.. code-block:: bash

   python -m yaaf frontend

This starts the frontend server on the default port 3000.

**Custom ports**:

.. code-block:: bash

   python -m yaaf backend 8080    # Backend on port 8080
   python -m yaaf frontend 3001   # Frontend on port 3001

Manual Setup
~~~~~~~~~~~~

You can also run the servers manually:

**Backend**:

.. code-block:: python

   from yaaf.server.run import run_server
   run_server(host="0.0.0.0", port=4000)

**Frontend**:

.. code-block:: bash

   cd frontend
   pnpm dev

Configuration
-------------

YAAF can be configured through environment variables or a configuration file.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

* ``YAAF_CONFIG``: Path to configuration JSON file
* ``ANTHROPIC_MODEL``: Default model for agents (e.g., "qwen2.5:32b")

Configuration File
~~~~~~~~~~~~~~~~~~

Create a JSON configuration file:

.. code-block:: json

   {
     "model": "qwen2.5:32b",
     "temperature": 0.4,
     "max_tokens": 1000,
     "query_suggestions": [
       "How many records are in the database?",
       "Show me a visualization of the data",
       "Search for recent news about AI"
     ]
   }

First Steps
-----------

Once both servers are running:

1. **Open your browser** to ``http://localhost:3000``
2. **Start a conversation** with the AI system
3. **Try different queries**:

   * "How many records are in the database?"
   * "Create a visualization of the sales data"
   * "Search for recent AI developments"
   * "Analyze the customer demographics"

Understanding the Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The chat interface displays messages with agent identifiers:

* Messages are wrapped in agent tags: ``<sqlagent>...</sqlagent>``
* Artifacts are shown as: ``<Artefact>artifact_id</Artefact>``
* Each agent specializes in different types of tasks

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**Backend won't start**:

* Check if port 4000 is already in use
* Verify Python dependencies are installed
* Check for configuration file errors

**Frontend build errors**:

* Ensure Node.js 18+ is installed
* Try deleting ``node_modules`` and running ``pnpm install`` again
* Check for TypeScript compilation errors

**No agents responding**:

* Verify the backend is running and accessible
* Check browser console for API errors
* Ensure the correct model is configured and available

Getting Help
~~~~~~~~~~~~

* Check the logs for error messages
* Verify all dependencies are correctly installed
* Ensure configuration matches your environment