Agent Taxonomy
==============

Every agent in YAAAF is classified according to its role in the artifact flow. This classification helps the planner build valid workflows and helps you understand what each agent does.

The Four Roles
--------------

Agents are classified into four primary roles based on how they handle artifacts:

EXTRACTOR
~~~~~~~~~

**Purpose**: Pull data from external sources into the system.

Extractors are the starting points of workflows. They reach outside YAAAF to retrieve data from databases, APIs, documents, or users. They produce artifacts but do not consume them.

Characteristics:

- No artifact inputs (they are sources)
- Produce artifacts from external data
- Examples: SqlAgent, DocumentRetrieverAgent, BraveSearchAgent

::

    [External Source] ──── EXTRACTOR ────► [Artifact]

TRANSFORMER
~~~~~~~~~~~

**Purpose**: Convert artifacts from one form to another.

Transformers take artifacts as input and produce new artifacts as output. They change the shape, format, or content of data without creating final outputs.

Characteristics:

- Accept one or more artifacts as input
- Produce one artifact as output
- Do not interact with external systems (except tools)
- Examples: MleAgent, ReviewerAgent, ToolAgent

::

    [Artifact A] ──── TRANSFORMER ────► [Artifact B]

SYNTHESIZER
~~~~~~~~~~~

**Purpose**: Combine multiple artifacts into unified outputs.

Synthesizers merge information from multiple sources into coherent wholes. They are used when a query requires information from different agents to be brought together.

Characteristics:

- Accept multiple artifacts as input
- Produce a single unified artifact
- Often used near the end of complex workflows
- Examples: AnswererAgent, UrlReviewerAgent, PlannerAgent

::

    [Artifact A] ───┐
                    ├──── SYNTHESIZER ────► [Combined Artifact]
    [Artifact B] ───┘

GENERATOR
~~~~~~~~~

**Purpose**: Create final outputs or side effects.

Generators produce artifacts that are typically the end goal of a workflow - visualizations, files, or system effects. They represent the "sinks" in the data flow.

Characteristics:

- Accept artifacts as input
- Produce final output artifacts
- May have side effects (file creation, system changes)
- Examples: VisualizationAgent, BashAgent

::

    [Artifact] ──── GENERATOR ────► [Final Output]

Additional Classifications
--------------------------

Beyond the primary data flow role, agents have two additional classifications:

Interaction Mode
~~~~~~~~~~~~~~~~

How the agent interacts during execution:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Mode
     - Description
   * - **AUTONOMOUS**
     - Executes without human intervention
   * - **INTERACTIVE**
     - May pause to request user input
   * - **COLLABORATIVE**
     - Coordinates with other agents

Output Permanence
~~~~~~~~~~~~~~~~~

What happens to the agent's output:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Permanence
     - Description
   * - **EPHEMERAL**
     - Output exists only for the current workflow
   * - **PERSISTENT**
     - Output is saved (files, trained models)
   * - **STATEFUL**
     - Maintains state across interactions

Complete Agent Classification
-----------------------------

Here is every agent with its full classification:

.. list-table::
   :header-rows: 1
   :widths: 25 20 20 20

   * - Agent
     - Data Flow
     - Interaction
     - Permanence
   * - SqlAgent
     - EXTRACTOR
     - AUTONOMOUS
     - EPHEMERAL
   * - DocumentRetrieverAgent
     - EXTRACTOR
     - AUTONOMOUS
     - EPHEMERAL
   * - BraveSearchAgent
     - EXTRACTOR
     - AUTONOMOUS
     - EPHEMERAL
   * - DuckDuckGoSearchAgent
     - EXTRACTOR
     - AUTONOMOUS
     - EPHEMERAL
   * - UrlAgent
     - EXTRACTOR
     - AUTONOMOUS
     - EPHEMERAL
   * - UserInputAgent
     - EXTRACTOR
     - INTERACTIVE
     - EPHEMERAL
   * - MleAgent
     - TRANSFORMER
     - AUTONOMOUS
     - PERSISTENT
   * - ReviewerAgent
     - TRANSFORMER
     - AUTONOMOUS
     - EPHEMERAL
   * - ToolAgent
     - TRANSFORMER
     - AUTONOMOUS
     - EPHEMERAL
   * - NumericalSequencesAgent
     - TRANSFORMER
     - AUTONOMOUS
     - EPHEMERAL
   * - AnswererAgent
     - SYNTHESIZER
     - AUTONOMOUS
     - EPHEMERAL
   * - UrlReviewerAgent
     - SYNTHESIZER
     - AUTONOMOUS
     - EPHEMERAL
   * - PlannerAgent
     - SYNTHESIZER
     - AUTONOMOUS
     - EPHEMERAL
   * - VisualizationAgent
     - GENERATOR
     - AUTONOMOUS
     - PERSISTENT
   * - BashAgent
     - GENERATOR
     - INTERACTIVE
     - PERSISTENT

How the Planner Uses Taxonomy
-----------------------------

The planner uses taxonomy information to build valid workflows:

1. **Source identification**: Only EXTRACTORS can start a workflow (they have no inputs)
2. **Type matching**: The planner ensures artifact types flow correctly between agents
3. **Goal mapping**: The planner identifies which GENERATOR or SYNTHESIZER can produce the desired output type
4. **Path finding**: The planner works backwards from the goal to find valid paths through TRANSFORMERS to EXTRACTORS

For example, if the goal is an image:

1. Planner identifies VisualizationAgent (GENERATOR) produces images
2. VisualizationAgent accepts tables
3. SqlAgent (EXTRACTOR) produces tables
4. Valid workflow: SqlAgent -> VisualizationAgent

Next Steps
----------

* :doc:`agents` - Detailed reference for each agent
* :doc:`planning_system` - How workflows are generated
* :doc:`core_concepts` - Understanding artifact flow
