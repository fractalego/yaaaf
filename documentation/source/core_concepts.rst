Core Concepts
=============

YAAAF is built around a single core idea: **artifacts flow through a planned pipeline from sources to outputs**. This page explains how this works.

Artifact-First, Not Agent-First
-------------------------------

YAAAF is an **artifact-first** framework. This is a fundamental design philosophy:

- **Traditional systems**: Query -> Agent -> Response
- **YAAAF**: Query -> Plan Railway -> Flow Artifacts -> Response

In traditional agent systems, you ask "which agent should handle this?" In YAAAF, you ask "what artifacts need to be created, and how do they flow from source to destination?"

The agents are not the stars of the show. They are the **stations** on a railway. The **artifacts** are the trains that move through them.

Artifact-Driven Execution
-------------------------

Traditional agent systems work by routing queries to individual agents that handle requests independently. YAAAF takes a fundamentally different approach.

When you ask YAAAF a question like "Show me a chart of monthly sales", the system does not simply call a visualization agent. Instead, it:

1. **Analyzes your goal** - Determines you want an image (chart) as output
2. **Plans the workflow** - Creates a DAG showing that data must first be extracted, then visualized
3. **Executes the plan** - Runs SqlAgent to get the data, then VisualizationAgent to create the chart
4. **Returns the artifact** - Delivers the final image to you

The key insight is that **artifacts are the primary citizens**, not agents. Agents are merely the workers that transform artifacts from one form to another.

What is an Artifact?
--------------------

An artifact is any piece of data produced during workflow execution. Artifacts have types:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Type
     - Description
   * - **table**
     - Tabular data (pandas DataFrames) - query results, structured data
   * - **text**
     - Unstructured text content - documents, summaries, answers
   * - **image**
     - Visual outputs - charts, plots, diagrams
   * - **model**
     - Trained machine learning models
   * - **json**
     - Structured data in JSON format

Artifacts are stored in a central artifact storage and referenced by unique IDs. This allows workflows to pass data between agents without copying large datasets.

The Railway Metaphor
--------------------

Think of YAAAF as a railway network:

- **Stations** are agents - each performs a specific transformation
- **Trains** are artifacts - they carry data between stations
- **The planner** is the route designer - it determines which stations each train visits
- **The workflow engine** is the dispatcher - it ensures trains arrive at stations in the right order

For each query, the planner designs a custom route. A simple question might need just one station. A complex analysis might need data to flow through five or six stations before reaching its destination.

::

    [Database] ──── SqlAgent ────► [Table: sales_data]
                                          │
                                          ▼
                               VisualizationAgent
                                          │
                                          ▼
                                  [Image: chart.png]

The Workflow DAG
----------------

Workflows are represented as Directed Acyclic Graphs (DAGs) in YAML format:

.. code-block:: yaml

   assets:
     # First artifact: extracted from database
     sales_data:
       agent: SqlAgent
       description: "Get monthly sales figures"
       type: table

     # Second artifact: depends on first
     sales_chart:
       agent: VisualizationAgent
       description: "Create bar chart"
       type: image
       inputs: [sales_data]  # This creates the dependency

The ``inputs`` field defines dependencies. The workflow engine ensures that ``sales_data`` is created before ``sales_chart`` is attempted.

Why This Matters
----------------

The artifact-driven approach has several advantages:

1. **Composability** - Complex workflows are built from simple, reusable agents
2. **Transparency** - You can see exactly what data flows where
3. **Reliability** - Each step produces a concrete artifact that can be inspected
4. **Parallelism** - Independent branches of the DAG can execute concurrently
5. **Reusability** - Artifacts can be cached and reused across queries

Artifact Types and Compatibility
--------------------------------

Not all agents can process all artifact types. Each agent declares:

- **Accepts**: What artifact types it can receive as input
- **Produces**: What artifact types it generates as output

The planner uses this information to build valid workflows. It will not create a plan that passes an image to SqlAgent, because SqlAgent only accepts queries (no input artifacts).

Example compatibility:

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Agent
     - Accepts
     - Produces
   * - SqlAgent
     - None (source)
     - table
   * - VisualizationAgent
     - table
     - image
   * - AnswererAgent
     - table, text
     - table
   * - MleAgent
     - table
     - model

Next Steps
----------

* :doc:`agent_taxonomy` - Learn how agents are classified by their role
* :doc:`planning_system` - Deep dive into how workflows are generated
* :doc:`agents` - Detailed reference for each agent
