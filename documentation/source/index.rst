YAAAF Documentation
===================

**YAAAF** (Yet Another Autonomous Agents Framework) is an artifact-driven framework for building intelligent agentic applications. The system plans and executes workflows where artifacts flow from sources through transformers to final outputs, like trains moving along a railway network planned specifically for each query.

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
