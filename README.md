# YAAAF - Yet Another Autonomous Agents Framework

YAAAF is an **artifact-first** framework for building intelligent agentic applications.

## The Core Philosophy

YAAAF is not about agents. It is about **artifacts**.

In YAAAF, you do not route queries to agents. Instead, the system builds a **railway** - a planned pipeline that moves artifacts from sources to their final destination. Agents are merely the stations along this railway, transforming artifacts as they pass through.

```
[Source] -----> [Station A] -----> [Station B] -----> [Destination]
   |                |                   |                   |
Database        SqlAgent          VisualizationAgent      Image
   |                |                   |                   |
   +--- artifact -->+--- artifact ----->+--- artifact -----+
        (query)          (table)             (chart)
```

This is artifact-first design: **the artifact is the primary citizen, not the agent**.

## How It Works

Unlike traditional agent systems that route queries to individual agents, YAAAF takes a fundamentally different approach:

1. **Goal Analysis**: The system extracts the user's goal and determines the required output type
2. **Workflow Planning**: A planner creates a DAG (directed acyclic graph) defining how artifacts should flow
3. **Artifact Flow**: Data moves through the planned pipeline - extracted, transformed, and finally output
4. **Validation**: Each artifact is validated against the user's goal; failed validations trigger automatic replanning

```
User Query
    |
    v
+-------------------+
|  Goal Extraction  |  "What does the user want?"
+-------------------+
    |
    v
+-------------------+
|  Plan Generation  |  Creates YAML workflow with artifact dependencies
+-------------------+
    |
    v
+-------------------+
|  Workflow Engine  |  Executes DAG, flowing artifacts between agents
+-------------------+
    |
    v
+-------------------+
|    Validation     |  Checks each artifact against goal (replan if needed)
+-------------------+
    |
    v
  Result
```

## Agent Taxonomy

Agents are classified by their role in the artifact flow:

| Role | Description |
|------|-------------|
| **EXTRACTOR** | Pulls data from external sources (databases, APIs, documents) |
| **TRANSFORMER** | Converts artifacts from one form to another |
| **SYNTHESIZER** | Combines multiple artifacts into unified outputs |
| **GENERATOR** | Creates final outputs (visualizations, files, effects) |

## Available Agents

| Agent | Role | Description |
|-------|------|-------------|
| SqlAgent | EXTRACTOR | Executes SQL queries against configured databases |
| DocumentRetrieverAgent | EXTRACTOR | Retrieves relevant text from document collections |
| BraveSearchAgent | EXTRACTOR | Searches the web via Brave Search API |
| DuckDuckGoSearchAgent | EXTRACTOR | Searches the web via DuckDuckGo |
| UrlAgent | EXTRACTOR | Fetches and extracts content from URLs |
| UserInputAgent | EXTRACTOR | Collects information from users interactively |
| MleAgent | TRANSFORMER | Trains machine learning models on tabular data |
| ReviewerAgent | TRANSFORMER | Analyzes and validates artifacts |
| ToolAgent | TRANSFORMER | Executes external tools via MCP protocol |
| NumericalSequencesAgent | TRANSFORMER | Structures unformatted data into tables |
| AnswererAgent | SYNTHESIZER | Combines artifacts into comprehensive answers |
| UrlReviewerAgent | SYNTHESIZER | Aggregates and summarizes URL content |
| VisualizationAgent | GENERATOR | Creates charts and visualizations from data |
| BashAgent | GENERATOR | Performs filesystem operations |
| PlannerAgent | SYNTHESIZER | Creates execution workflows from goals |
| ValidationAgent | TRANSFORMER | Validates artifacts against user goals, triggers replanning |

## How Planning Works

When a query arrives, the planner generates a YAML workflow defining the artifact flow:

```yaml
assets:
  sales_data:
    agent: SqlAgent
    description: "Extract quarterly sales figures"
    type: table

  sales_chart:
    agent: VisualizationAgent
    description: "Create bar chart of sales by quarter"
    type: image
    inputs: [sales_data]
```

The planner uses **RAG-based example retrieval** to find similar scenarios from a dataset of 50,000+ planning examples, ensuring high-quality workflow generation.

## Quick Start

### Installation

```bash
git clone <repository-url>
cd agents_framework
pip install -e .

# Frontend (optional)
cd frontend && pnpm install
```

### Running

```bash
# Backend (default port 4000)
python -m yaaaf backend

# Frontend (default port 3000)
python -m yaaaf frontend

# Custom ports
python -m yaaaf backend 8080
python -m yaaaf frontend 3001
```

### Requirements

- Python 3.11+
- Ollama running locally (default: http://localhost:11434)
- A compatible model (e.g., `ollama pull qwen2.5:32b`)

## Configuration

Set `YAAAF_CONFIG` environment variable to point to your configuration file:

```json
{
  "client": {
    "model": "qwen2.5:32b",
    "temperature": 0.7,
    "host": "http://localhost:11434"
  },
  "agents": [
    "sql",
    "visualization",
    "websearch",
    "document_retriever",
    "answerer",
    "reviewer"
  ],
  "sources": [
    {
      "name": "my_database",
      "type": "sqlite",
      "path": "./data/database.db"
    }
  ]
}
```

### Agent-Specific Configuration

Override model settings per agent:

```json
{
  "agents": [
    "sql",
    {
      "name": "visualization",
      "model": "qwen2.5-coder:32b",
      "temperature": 0.1
    }
  ]
}
```

### MCP Tool Integration

Add external tools via Model Context Protocol:

```json
{
  "tools": [
    {
      "name": "math_server",
      "type": "sse",
      "url": "http://localhost:8080/sse"
    },
    {
      "name": "file_tools",
      "type": "stdio",
      "command": "python",
      "args": ["-m", "my_mcp_server"]
    }
  ]
}
```

## Architecture

```
Frontend (Next.js)  <--HTTP-->  Backend (FastAPI)
                                      |
                                      v
                              +---------------+
                              | Orchestrator  |
                              +---------------+
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                  +------------+           +----------------+
                  |  Planner   |           | Workflow Engine|
                  +------------+           +----------------+
                         |                         |
                         v                         v
                  YAML Workflow  ------>   Agent Execution
                                           (artifact flow)
```

### Key Components

- **Orchestrator**: Entry point that coordinates goal extraction and workflow execution
- **Planner**: Generates YAML workflows using RAG-retrieved examples
- **Workflow Engine**: Executes the DAG, managing artifact dependencies
- **Validation**: Inspects each artifact and triggers replanning if it doesn't match the goal
- **Artifact Storage**: Centralized store for generated artifacts (tables, images, models)

## Development

```bash
# Run tests
python -m unittest discover tests/

# Code formatting
ruff format .
ruff check .

# Frontend development
cd frontend && pnpm dev
```

## Project Structure

```
yaaaf/
  components/
    agents/           # Agent implementations
    retrievers/       # RAG and search components
    executors/        # Workflow and tool executors
    sources/          # Data source connectors
  server/             # FastAPI backend
  data/               # Packaged datasets (planner examples)
frontend/             # Next.js application
tests/                # Unit tests
```

## License

MIT License

## Support

- Documentation: `documentation/` folder
- Issues: GitHub Issues
- Discussions: GitHub Discussions
