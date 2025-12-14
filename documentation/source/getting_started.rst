Getting Started
===============

This guide will get you running YAAAF in under 5 minutes.

YAAAF is an **artifact-first** framework. When you send a query, the system plans a railway for artifacts to flow from sources (databases, documents, APIs) through transformation stations (agents) to their final destination (your answer). You will see this in action once you run your first query.

Prerequisites
-------------

Before installing YAAAF, ensure you have:

1. **Python 3.11 or higher**

   .. code-block:: bash

      python --version  # Should show 3.11+

2. **Ollama** installed and running

   Ollama is the LLM backend that YAAAF uses. Install it from https://ollama.ai/

   .. code-block:: bash

      # Verify Ollama is running
      curl http://localhost:11434/api/tags

3. **A compatible model** pulled in Ollama

   .. code-block:: bash

      # Pull the recommended model
      ollama pull qwen2.5:32b

      # Or a smaller model for testing
      ollama pull qwen2.5:14b

4. **Node.js 18+** and **pnpm** (for frontend, optional)

   .. code-block:: bash

      node --version  # Should show 18+
      pnpm --version

Installation
------------

Clone and install YAAAF:

.. code-block:: bash

   # Clone the repository
   git clone <repository-url>
   cd agents_framework

   # Install Python package
   pip install -e .

   # Install frontend dependencies (optional)
   cd frontend
   pnpm install
   cd ..

Running the Backend
-------------------

The backend is a FastAPI server that handles all agent execution:

.. code-block:: bash

   # Start on default port 4000
   python -m yaaaf backend

   # Or specify a custom port
   python -m yaaaf backend 8080

You should see output like:

.. code-block:: text

   INFO:     Uvicorn running on http://0.0.0.0:4000
   INFO:     Successfully connected to Ollama at http://localhost:11434
   INFO:     Model 'qwen2.5:32b' is available

The backend is now ready to accept requests.

Running the Frontend
--------------------

The frontend is a Next.js application providing a chat interface:

.. code-block:: bash

   # Start on default port 3000
   python -m yaaaf frontend

   # Or specify a custom port
   python -m yaaaf frontend 3001

Open your browser to http://localhost:3000 to access the chat interface.

Running Both Together
---------------------

For a complete setup, run both in separate terminals:

**Terminal 1 - Backend:**

.. code-block:: bash

   python -m yaaaf backend

**Terminal 2 - Frontend:**

.. code-block:: bash

   python -m yaaaf frontend

Then open http://localhost:3000 in your browser.

Your First Query
----------------

Once both servers are running, try these example queries in the chat interface:

1. **Simple question** (uses AnswererAgent):

   .. code-block:: text

      What is the capital of France?

2. **Database query** (uses SqlAgent, requires configured database):

   .. code-block:: text

      How many records are in the users table?

3. **Web search** (uses BraveSearchAgent or DuckDuckGoSearchAgent):

   .. code-block:: text

      Search for the latest news about artificial intelligence

4. **Visualization** (uses SqlAgent + VisualizationAgent pipeline):

   .. code-block:: text

      Show me a chart of sales by month from the database

Watch the chat interface - you will see the system:

1. Extract your goal
2. Generate a workflow plan
3. Execute agents in sequence
4. Return the final artifact

Verifying the Installation
--------------------------

Test that everything is working:

.. code-block:: bash

   # Test backend health
   curl http://localhost:4000/health

   # Run unit tests
   python -m unittest discover tests/

Common Issues
-------------

**Ollama not running:**

.. code-block:: text

   Connection Error: Cannot connect to Ollama

Solution: Start Ollama with ``ollama serve`` or check if it's running.

**Model not found:**

.. code-block:: text

   Model 'qwen2.5:32b' is not available

Solution: Pull the model with ``ollama pull qwen2.5:32b``

**Port already in use:**

.. code-block:: text

   Address already in use

Solution: Use a different port with ``python -m yaaaf backend 8080``

**Frontend build issues:**

.. code-block:: bash

   # Clear cache and reinstall
   cd frontend
   rm -rf node_modules .next
   pnpm install

Next Steps
----------

* :doc:`core_concepts` - Understand how artifact-driven execution works
* :doc:`configuration` - Configure databases, agents, and external tools
* :doc:`agents` - Learn about each agent's capabilities
