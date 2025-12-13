YAAAF Documentation
===================

**YAAAF** (Yet Another Autonomous Agents Framework) is an **artifact-first** framework for building intelligent agentic applications.

The Core Philosophy
-------------------

YAAAF is not about agents. It is about **artifacts**.

In YAAAF, you do not route queries to agents. Instead, the system builds a **railway** - a planned pipeline that moves artifacts from sources to their final destination. Agents are merely the stations along this railway, transforming artifacts as they pass through.

When you ask "Show me a chart of sales by region", YAAAF:

1. Plans a railway: Database -> Table -> Chart
2. Builds the track: SqlAgent produces a table, VisualizationAgent consumes it
3. Runs the train: The artifact (data) flows through each station until it reaches its destination (an image)

This is artifact-first design: **the artifact is the primary citizen, not the agent**.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   core_concepts
   agent_taxonomy
   agents
   planning_system
   configuration
   architecture
   development

Core Idea
---------

Unlike traditional agent systems that route queries to individual agents, YAAAF takes a fundamentally different approach:

1. **Goal Analysis**: The system extracts the user's goal and determines the required output type
2. **Workflow Planning**: A planner creates a DAG (directed acyclic graph) defining how artifacts should flow
3. **Artifact Flow**: Data moves through the planned pipeline - extracted, transformed, and finally output

The planner uses RAG-based example retrieval from 50,000+ planning scenarios to generate high-quality workflows for any query.

Quick Links
-----------

* :doc:`getting_started` - Run YAAAF in 5 minutes
* :doc:`core_concepts` - Understand artifact-driven execution
* :doc:`agents` - Detailed reference for all agents
* :doc:`configuration` - Configure sources, agents, and tools

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
