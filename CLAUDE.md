# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YAAAF (Yet Another Autonomous Agents Framework) is an **artifact-first** framework for building agentic applications.

**Core Philosophy**: YAAAF is not about agents - it is about artifacts. The system builds a **railway** (a planned DAG) that moves artifacts from sources to their final destination. Agents are merely stations along this railway, transforming artifacts as they pass through.

```
Query -> Planner -> Railway (DAG) -> Artifacts flow through agents -> Response
```

- **Artifacts** are the trains (data flowing through the system)
- **Agents** are the stations (they transform artifacts)
- **Planner** builds the railway (creates YAML workflow with dependencies)
- **Workflow Engine** runs the trains (executes the DAG)

## Development Commands

### Backend (Python)
- **Start backend server**: `python -m yaaaf backend 4000`
- **Run specific tests**: `python -m unittest tests.test_clients`
- **Run all tests**: `python -m unittest discover tests/`
- **Code formatting**: `ruff format .`
- **Linting**: `ruff check .`

### Frontend (Next.js)
- **Development server**: `cd frontend && pnpm dev`
- **Build**: `cd frontend && pnpm build`
- **Lint**: `cd frontend && pnpm lint`
- **Type check**: `cd frontend && pnpm typecheck`
- **Format check**: `cd frontend && pnpm format:check`
- **Format fix**: `cd frontend && pnpm format:write`
- **Component registry build**: `cd frontend && pnpm build:registry`

### Running the Full System
- Backend: `python -m yaaaf backend 4000` 
- Frontend: `python -m yaaaf frontend 3000` (or `cd frontend && pnpm dev`)

## Architecture

### Core Components

**Backend (`yaaaf/`):**
- `components/agents/`: Specialized agents and executor framework
  - `executors/`: Tool execution abstractions (SQL, web search, Python code)
  - `base_agent_enhanced.py`: Enhanced base class with common query loop
  - Individual agents: SQL, visualization, web search, reflection, reviewer
- `components/data_types/`: Core data structures (Messages, Utterances, PromptTemplate)
- `components/client.py`: LLM client implementations (OllamaClient)
- `components/orchestrator_builder.py`: Factory for creating orchestrator with agents
- `server/`: FastAPI server with streaming endpoints
- `connectors/`: MCP (Model Context Protocol) integration

**Agent System Architecture:**
- **Executor Pattern**: Agents delegate tool-specific operations to ToolExecutor implementations
- **BaseAgentEnhanced**: Provides common multi-step query loop and artifact management
- **ToolExecutors**: Handle specific operations (SQLExecutor, PythonExecutor, WebSearchExecutor)
- `orchestrator_agent.py`: Main coordinator that routes queries to specialized agents
- Each agent combines an executor with domain-specific prompts
- Agents communicate through Messages containing Utterances (role + content)

**Frontend (`frontend/`):**
- Monorepo structure with `apps/www/` containing main Next.js application
- Built on shadcn/ui component system
- Registry-based component architecture for chatbot UI components
- Real-time chat interface with streaming support

### Configuration
- Config loaded from `YAAAF_CONFIG` environment variable or default settings
- Default model: `qwen2.5:32b` with Ollama client
- Supports multiple data sources (SQLite) and configurable agent selection

### Data Flow (Artifact-First)
1. User query → Frontend chat interface
2. Frontend → Backend API (`/create_stream`)
3. **Goal Extraction**: System determines what artifact type the user wants
4. **Railway Planning**: PlannerAgent creates YAML workflow (DAG) using RAG-retrieved examples
5. **Artifact Flow**: WorkflowExecutor runs the DAG:
   - Each agent (station) receives input artifacts
   - Agent transforms artifacts and produces output
   - Output artifacts flow to next station(s)
6. Final artifact returned to user

## Key Files to Understand

### Agent Framework
- `yaaaf/components/agents/base_agent_enhanced.py`: Enhanced base class with common query loop
- `yaaaf/components/agents/executors/base.py`: ToolExecutor abstract interface
- `yaaaf/components/agents/executors/sql_executor.py`: SQL query execution
- `yaaaf/components/agents/executors/websearch_executor.py`: Web search implementations
- `yaaaf/components/agents/executors/python_executor.py`: Python code execution
- Refactored agents: `*_agent_refactored.py` files for simplified implementations

### Core System
- `yaaaf/components/agents/orchestrator_agent.py`: Plan-driven orchestrator (goal extraction + workflow execution)
- `yaaaf/components/agents/planner_agent.py`: Creates YAML workflows using RAG-retrieved examples
- `yaaaf/components/retrievers/planner_example_retriever.py`: BM25-based retrieval from planner dataset
- `yaaaf/data/planner_dataset.csv`: 50k+ examples for RAG-based planning
- `yaaaf/components/orchestrator_builder.py`: Agent registration and orchestrator setup
- `yaaaf/components/data_types.py`: Core message/conversation structures
- `yaaaf/server/routes.py`: API endpoints for chat streaming and artifacts
- `frontend/apps/www/components/ui/chat.tsx`: Main chat interface component
- `tests/`: Unit tests for all major components. All the tests go into this folder.

## Files to ignore
- `yaaaf/client/standalone/`: Contains standalone client code that is built from the frontend when run in production mode. It is not used in development.

## Auxiliary Scripts

### Scripts Directory (`scripts/`)
The `scripts/` directory contains auxiliary scripts for various tasks:

- **`planner_dataset/`**: Scripts for generating synthetic planning datasets
  - Uses OpenAI GPT-4o-mini to generate diverse realistic scenarios
  - Creates execution plan workflows using the PlannerAgent prompt format
  - Independent from the main repo with its own `requirements.txt`
  - Outputs stratified datasets in CSV format with varying workflow complexity
  - Default: 100 examples, scalable to 1000+

## Development Notes

### Agent Development
- **Executor Pattern**: New agents should use the ToolExecutor pattern for consistency
- **Simplified Agents**: Agents now just define their executor and system prompt (~40 lines vs 200+)
- **Common Logic**: Multi-step loops, response processing, and artifact management handled by BaseAgentEnhanced
- **Tool Extension**: Add new tools by implementing ToolExecutor interface

### General Development
- The system uses async/await patterns throughout for streaming responses
- Agents are designed to be modular and easily extensible through the executor pattern
- Frontend uses Turbo monorepo with pnpm for package management
- Backend uses FastAPI with CORS enabled for frontend integration
- Tests use Python's unittest framework, not pytest
- **NEVER USE MOCKS IN TESTS** - use real implementations or skip the test
- **ALL PROMPTS GO IN `prompts.py`** - never define prompts inline in agent files
- Don't use pip to install dependencies, use `uv add` to add dependencies to the `pyproject.toml` file

### Creating New Agents
1. Implement a ToolExecutor for your specific tool/operation
2. Create an agent class inheriting from BaseAgentEnhanced
3. Set the executor and system prompt in the constructor
4. Register the agent in `orchestrator_builder.py`
5. **Important**: Add 5-10 examples to `yaaaf/data/planner_dataset.csv` so the planner knows how to use your agent in workflows
