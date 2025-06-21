# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YAAAF (Yet Another Autonomous Agents Framework) is a modular framework for building agentic applications with both Python backend and Next.js frontend components. The system features an orchestrator pattern with specialized agents for different tasks like SQL queries, web search, visualization, and reflection.

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
- `components/agents/`: Specialized agents (SQL, visualization, web search, reflection, reviewer)
- `components/data_types.py`: Core data structures (Messages, Utterances, PromptTemplate)
- `components/client.py`: LLM client implementations (OllamaClient)
- `components/orchestrator_builder.py`: Factory for creating orchestrator with agents
- `server/`: FastAPI server with streaming endpoints
- `connectors/`: MCP (Model Context Protocol) integration

**Agent System:**
- `orchestrator_agent.py`: Main coordinator that routes queries to specialized agents
- `base_agent.py`: Abstract base class for all agents
- Each agent has specific capabilities (SQL querying, web search, visualization, etc.)
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

### Data Flow
1. User query → Frontend chat interface
2. Frontend → Backend API (`/create_stream`)
3. OrchestratorAgent routes to appropriate specialized agents
4. Agents process and return responses with artifacts
5. Results streamed back to frontend with real-time updates

## Key Files to Understand

- `yaaaf/components/orchestrator_builder.py`: Agent registration and orchestrator setup
- `yaaaf/components/data_types.py`: Core message/conversation structures
- `yaaaf/server/routes.py`: API endpoints for chat streaming and artifacts
- `frontend/apps/www/components/ui/chat.tsx`: Main chat interface component
- `tests/`: Unit tests for all major components. All the tests go into this folder.

## Development Notes

- The system uses async/await patterns throughout for streaming responses
- Agents are designed to be modular and easily extensible
- Frontend uses Turbo monorepo with pnpm for package management
- Backend uses FastAPI with CORS enabled for frontend integration
- Tests use Python's unittest framework, not pytest