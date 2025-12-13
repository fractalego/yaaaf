Planning System
===============

The planning system is the brain of YAAAF. It analyzes user goals and generates workflows that transform those goals into concrete artifacts.

Overview
--------

When a query arrives, YAAAF does not simply route it to an agent. Instead:

1. **Goal Extraction**: The system identifies what the user wants to achieve
2. **Target Type Detection**: It determines what type of artifact (table, image, text) should be produced
3. **Plan Generation**: The PlannerAgent creates a YAML workflow
4. **Workflow Execution**: The workflow engine executes the plan, flowing artifacts between agents

::

    User: "Show me a chart of sales by region"
                    |
                    v
    +----------------------------------+
    | Goal: Visualize sales by region  |
    | Target: image                    |
    +----------------------------------+
                    |
                    v
    +----------------------------------+
    |         PlannerAgent             |
    |   (generates YAML workflow)      |
    +----------------------------------+
                    |
                    v
    +----------------------------------+
    | assets:                          |
    |   sales_data:                    |
    |     agent: SqlAgent              |
    |     type: table                  |
    |   sales_chart:                   |
    |     agent: VisualizationAgent    |
    |     type: image                  |
    |     inputs: [sales_data]         |
    +----------------------------------+
                    |
                    v
    +----------------------------------+
    |       Workflow Engine            |
    |   (executes DAG in order)        |
    +----------------------------------+

Goal Extraction
---------------

The first step is understanding what the user wants. The goal extractor analyzes the query to determine:

- **Goal statement**: A clear description of what needs to be achieved
- **Target artifact type**: What kind of output is expected (table, image, text, model)

Examples:

.. list-table::
   :header-rows: 1
   :widths: 50 30 20

   * - Query
     - Goal
     - Target Type
   * - "How many users registered last month?"
     - Count user registrations
     - table
   * - "Show me a pie chart of expenses"
     - Visualize expense distribution
     - image
   * - "Summarize the quarterly report"
     - Extract key information from report
     - text
   * - "Train a model to predict churn"
     - Build predictive model
     - model

RAG-Based Example Retrieval
---------------------------

The planning system uses Retrieval-Augmented Generation (RAG) to find relevant examples from a dataset of 50,000+ planning scenarios.

How it works:

1. **Query embedding**: The user's query is processed using BM25 tokenization
2. **Similarity search**: The system finds the most similar scenarios in the dataset
3. **Example retrieval**: Top 3 most relevant examples are retrieved
4. **Prompt injection**: These examples are included in the planner's prompt

This approach ensures that the planner sees relevant examples for any type of query, leading to higher-quality workflow generation.

**Example dataset entry**:

.. code-block:: text

   Scenario: "Gather customer feedback from our website, analyze the sentiments
   expressed, and generate a report summarizing the key insights along with
   visualizations to highlight major trends."

   Workflow:
   assets:
     customer_feedback_data:
       agent: UserInputAgent
       description: "Gather customer feedback from the website"
       type: text

     analyzed_sentiment_data:
       agent: MleAgent
       description: "Analyze sentiments expressed in customer feedback"
       type: model
       inputs: [customer_feedback_data]

     sentiment_summary_report:
       agent: AnswererAgent
       description: "Generate a report summarizing key insights"
       type: table
       inputs: [analyzed_sentiment_data]

     sentiment_trend_visualization:
       agent: VisualizationAgent
       description: "Create visualizations to highlight major sentiment trends"
       type: image
       inputs: [sentiment_summary_report]

Workflow YAML Format
--------------------

Workflows are defined in YAML with the following structure:

.. code-block:: yaml

   assets:
     asset_name:
       agent: AgentName
       description: "What this step does"
       type: artifact_type
       inputs: [dependency1, dependency2]  # optional
       checks:                              # optional
         - "validation rule"
       params:                              # optional
         key: value

**Required fields**:

- ``agent``: The agent that will execute this step
- ``description``: Human-readable description of the task
- ``type``: The artifact type this step produces (table, text, image, model)

**Optional fields**:

- ``inputs``: List of asset names this step depends on
- ``checks``: Validation rules for the output
- ``params``: Additional parameters for the agent

Workflow Execution
------------------

The workflow engine executes the DAG by:

1. **Topological sorting**: Determining the correct execution order
2. **Dependency resolution**: Waiting for inputs to be available
3. **Parallel execution**: Running independent branches concurrently
4. **Artifact passing**: Providing input artifacts to each agent
5. **Result collection**: Storing output artifacts for downstream use

Example execution flow:

::

    Step 1: SqlAgent (no dependencies)
       |
       +---> sales_data artifact
       |
    Step 2: VisualizationAgent (depends on sales_data)
       |
       +---> sales_chart artifact (FINAL)

Validation and Checks
---------------------

Workflows can include validation rules:

.. code-block:: yaml

   assets:
     query_results:
       agent: SqlAgent
       description: "Get user data"
       type: table
       checks:
         - "row_count > 0"
         - "columns: [id, name, email]"
         - "no_null_values: [id]"

Common validation rules:

- ``row_count > N``: Minimum number of rows
- ``columns: [list]``: Required columns
- ``no_null_values: [columns]``: Columns that must not contain nulls
- ``file_size < N``: Maximum file size for images
- ``accuracy > N``: Minimum accuracy for models

Error Handling and Replanning
-----------------------------

When workflow execution fails, the system can attempt replanning:

1. **Error capture**: The specific error is recorded
2. **Completed assets**: Successfully created artifacts are preserved
3. **Replan request**: PlannerAgent is asked to create a revised plan
4. **Context inclusion**: The error and completed assets inform the new plan

.. code-block:: text

   Original plan failed at step 3 with error:
   "VisualizationAgent: No numeric columns found in data"

   Replanning with context:
   - Completed: sales_data (table)
   - Error: No numeric columns for visualization
   - Suggestion: Add data transformation step

Planning Constraints
--------------------

The planner respects several constraints:

**Agent availability**: Only configured agents can be used in plans.

**Type compatibility**: Artifact types must match:

- SqlAgent produces ``table``
- VisualizationAgent accepts ``table``, produces ``image``
- The planner will not create invalid connections

**Taxonomy rules**:

- Only EXTRACTORS can start a workflow (they have no inputs)
- GENERATORS typically end workflows
- TRANSFORMERS and SYNTHESIZERS connect sources to sinks

Debugging Plans
---------------

To see the generated plan, enable debug logging:

.. code-block:: bash

   YAAAF_DEBUG=true python -m yaaaf backend

The logs will show:

- Extracted goal and target type
- Retrieved examples from RAG
- Generated YAML workflow
- Execution progress for each step

Custom Planning
---------------

For advanced use cases, you can generate plans programmatically:

.. code-block:: python

   from yaaaf.components.agents.planner_agent import PlannerAgent

   planner = PlannerAgent(client, available_agents)
   messages = Messages().add_user_utterance("Create a sales report")

   response = await planner.query(messages)
   # response contains YAML workflow

Adding Examples for Custom Agents
---------------------------------

The planner relies entirely on the example dataset for learning how to use agents. If you create a custom agent, **you must add examples to the planner dataset** or the planner will not know how to incorporate your agent into workflows.

The dataset is located at ``yaaaf/data/planner_dataset.csv``.

**Required columns**:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Column
     - Description
   * - ``scenario``
     - Natural language description of the task
   * - ``workflow_yaml``
     - Complete YAML workflow using your agent
   * - ``agents_used``
     - Python list of agent names used
   * - ``num_agents``
     - Count of distinct agents
   * - ``num_steps``
     - Number of workflow steps
   * - ``complexity``
     - Workflow type: simple_chain, parallel, conditional
   * - ``is_valid``
     - Set to True for valid examples
   * - ``error_message``
     - Leave empty for valid examples

**Best practices for examples**:

1. Add at least 5-10 examples per custom agent
2. Show your agent in different positions (start, middle, end of workflow)
3. Combine your agent with various other agents
4. Use diverse scenario descriptions to improve retrieval
5. Include both simple and complex workflow examples

Without examples, the BM25 retrieval will never surface your agent as a possibility, and the planner will not include it in generated workflows.

Next Steps
----------

* :doc:`agents` - Detailed reference for each agent
* :doc:`configuration` - Configure available agents and sources
* :doc:`architecture` - System architecture overview
