# YAAAF - Yet Another Autonomous Agents Framework

YAAAF is a modular framework for building intelligent agentic applications with both Python backend and Next.js frontend components. The system features an orchestrator pattern with specialized agents for different tasks like SQL queries, web search, visualization, machine learning, and reflection.

## 🚀 Key Features

- **🤖 Modular Agent System**: Specialized agents for SQL, visualization, web search, ML, RAG, and more
- **🎯 Orchestrator Pattern**: Central coordinator that intelligently routes queries to appropriate agents
- **⚡ Real-time Streaming**: Live updates through WebSocket-like streaming with structured Note objects
- **📊 Artifact Management**: Centralized storage for generated content (tables, images, models, etc.)
- **🌐 Modern Frontend**: React-based UI with real-time chat interface and agent attribution
- **🔧 Extensible**: Easy to add new agents and capabilities with standardized interfaces
- **🏷️ Tag-Based Routing**: HTML-like tags for intuitive agent selection (`<sqlagent>`, `<visualizationagent>`, etc.)

## 🏗️ Architecture Overview

```
┌─────────────────┐    HTTP/REST     ┌──────────────────┐
│  Frontend       │ ◄──────────────► │  Backend         │
│  (Next.js)      │                  │  (FastAPI)       │
└─────────────────┘                  └──────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Orchestrator    │
                                    │  Agent           │
                                    └──────────────────┘
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        ▼                     ▼                     ▼
              ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
              │  SQL Agent      │   │ Visualization   │   │ Web Search      │
              │                 │   │ Agent           │   │ Agent           │
              └─────────────────┘   └─────────────────┘   └─────────────────┘
                        ▼                     ▼                     ▼
              ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
              │ Centralized     │   │ Artifact        │   │ Storage         │
              │ Artifact Storage│   │ Management      │   │ System          │
              └─────────────────┘   └─────────────────┘   └─────────────────┘
```

## 🚀 Quick Start

### Installation & Setup

```bash
# Clone the repository
git clone <repository-url>
cd agents_framework

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
pnpm install
cd ..
```

### Running YAAAF

**Start the backend server** (default port 4000):
```bash
python -m yaaaf backend
```

**Start the frontend server** (default port 3000):
```bash
python -m yaaaf frontend
```

**Custom ports**:
```bash
python -m yaaaf backend 8080         # Backend on port 8080
python -m yaaaf frontend 3001        # Frontend on port 3001
```

**HTTPS Support**:
HTTPS mode is currently not fully supported in the standalone distribution. For HTTPS in production, use a reverse proxy like nginx:

```bash
# Start YAAAF on HTTP
python -m yaaaf frontend 3000

# Configure nginx with SSL to proxy to port 3000
```


### First Steps

1. Open your browser to `http://localhost:3000`
2. Start chatting with the AI system
3. Try these example queries:
   - "How many records are in the database?"
   - "Create a visualization of the sales data"
   - "Search for recent AI developments"
   - "Analyze customer demographics and show trends"

## 🤖 Available Agents

| Agent | Purpose | Usage Tag | Capabilities |
|-------|---------|-----------|-------------|
| **OrchestratorAgent** | Central coordinator | `<orchestratoragent>` | Routes queries, manages flow |
| **SqlAgent** | Database queries | `<sqlagent>` | Natural language to SQL, data retrieval |
| **VisualizationAgent** | Charts & graphs | `<visualizationagent>` | Matplotlib visualizations from data |
| **WebSearchAgent** | Web search | `<websearchagent>` | DuckDuckGo search integration |
| **ReflectionAgent** | Planning & reasoning | `<reflectionagent>` | Step-by-step problem breakdown |
| **RAGAgent** | Document retrieval | `<ragagent>` | Retrieval-augmented generation |
| **MleAgent** | Machine learning | `<mleagent>` | sklearn model training & analysis |
| **ReviewerAgent** | Data analysis | `<revieweragent>` | Extract insights from artifacts |
| **ToolAgent** | External tools | `<toolagent>` | MCP (Model Context Protocol) integration |
| **BashAgent** | Filesystem operations | `<bashagent>` | File reading, writing, directory operations (with user confirmation) |

## 💡 Example Usage

### Simple Query
```python
from yaaaf.components.orchestrator_builder import OrchestratorBuilder
from yaaaf.components.data_types import Messages

orchestrator = OrchestratorBuilder().build()
messages = Messages().add_user_utterance("How many users are in the database?")
response = await orchestrator.query(messages)
```

## 🛠️ Development

### Backend Development
```bash
# Run tests
python -m unittest discover tests/

# Code formatting
ruff format .
ruff check .

# Start with debugging
YAAAF_DEBUG=true python -m yaaaf backend
```

### Frontend Development
```bash
cd frontend

# Development server
pnpm dev

# Type checking
pnpm typecheck

# Linting & formatting
pnpm lint
pnpm format:write

# Build for production
pnpm build
```

## 📊 Data Flow

1. **User Input**: Query submitted through frontend chat interface
2. **Stream Creation**: Backend creates conversation stream
3. **Orchestration**: OrchestratorAgent analyzes query and routes to appropriate agents
4. **Agent Processing**: Specialized agents process their portions of the request
5. **Artifact Generation**: Agents create structured artifacts (tables, images, etc.)
6. **Note Creation**: Results packaged as Note objects with agent attribution
7. **Real-time Streaming**: Notes streamed back to frontend with live updates
8. **UI Rendering**: Frontend displays formatted responses with agent identification

## 🔧 Configuration

### LLM Requirements

**⚠️ Important**: YAAAF currently supports **Ollama only** for LLM integration. You must have Ollama installed and running on your system.

**Prerequisites:**
- Install [Ollama](https://ollama.ai/) on your system
- Download and run a compatible model (e.g., `ollama pull qwen2.5:32b`)
- Ensure Ollama is running (usually on `http://localhost:11434`)

YAAAF uses the `OllamaClient` for all LLM interactions. Support for other LLM providers (OpenAI, Anthropic, etc.) may be added in future versions.

### Environment Variables
- `YAAAF_CONFIG`: Path to configuration JSON file

### Configuration File
```json
{
  "client": {
    "model": "qwen2.5:32b",
    "temperature": 0.7,
    "max_tokens": 1024,
    "host": "http://localhost:11434"
  },
  "agents": [
    "reflection",
    {
      "name": "visualization",
      "model": "qwen2.5-coder:32b",
      "temperature": 0.1
    },
    "sql",
    {
      "name": "rag",
      "model": "qwen2.5:14b", 
      "temperature": 0.8,
      "max_tokens": 4096,
      "host": "http://localhost:11435"
    },
    "reviewer",
    "websearch",
    "url_reviewer",
    "bash"
  ],
  "sources": [
    {
      "name": "london_archaeological_data",
      "type": "sqlite",
      "path": "../../data/london_archaeological_data.db"
    }
  ]
}
```

**Per-Agent Configuration:**
- **Simple format**: `"agent_name"` uses default client settings
- **Object format**: `{"name": "agent_name", "model": "...", "temperature": 0.1, "host": "..."}` overrides specific parameters
- **Fallback**: Any unspecified parameters use the default client configuration
- **Examples**: Use specialized models for specific tasks (e.g., coding models for visualization, larger models for RAG)
- **Host configuration**: Set different Ollama instances per agent or use default host

## 📚 Documentation

Comprehensive documentation is available in the `documentation/` folder:

```bash
cd documentation
pip install -r requirements.txt
make html
open build/html/index.html
```

**Documentation includes:**
- 📖 Getting Started Guide
- 🏗️ Architecture Overview  
- 🤖 Agent Development Guide
- 🔌 API Reference
- 🌐 Frontend Development
- 💻 Development Practices
- 📋 Usage Examples

## 🧪 Testing

```bash
# Backend tests
python -m unittest discover tests/

# Specific agent tests
python -m unittest tests.test_sql_agent
python -m unittest tests.test_orchestrator_agent

# Frontend tests
cd frontend
pnpm test
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Follow code style**: Run `ruff format .` and `pnpm format:write`
4. **Add tests**: Ensure new features have test coverage
5. **Update docs**: Add documentation for new features
6. **Submit PR**: Create a pull request with clear description

## 📋 Requirements

**Backend:**
- Python 3.11+
- FastAPI
- Pydantic
- pandas
- matplotlib
- sqlite3

**Frontend:**
- Node.js 18+
- Next.js 14
- TypeScript
- Tailwind CSS
- pnpm

**Package Distribution:**
- The yaaaf wheel includes a complete standalone frontend (`yaaaf/client/standalone/`)
- No additional frontend setup required for basic usage
- Frontend source code available in `frontend/` for development

## 📄 License

MIT License (MIT)

## 🆘 Support

- 📖 **Documentation**: Check the `documentation/` folder
- 🐛 **Issues**: Report bugs via GitHub Issues
- 💬 **Discussions**: Join GitHub Discussions for questions

---

**YAAAF** - Building the future of agentic applications, one intelligent agent at a time! 🚀