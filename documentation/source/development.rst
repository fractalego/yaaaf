Development Guide
=================

This guide covers development practices, testing, debugging, and contributing to YAAF.

Development Environment
-----------------------

Prerequisites
~~~~~~~~~~~~

**System Requirements**:
   * Python 3.11+
   * Node.js 18+
   * Git
   * pnpm (for frontend)

**Recommended Tools**:
   * VSCode or PyCharm
   * Python debugger
   * Browser developer tools
   * Database browser (for SQLite)

Setting Up Development Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Clone Repository**:

   .. code-block:: bash

      git clone <repository-url>
      cd agents_framework

2. **Backend Setup**:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate
      pip install -r requirements.txt

3. **Frontend Setup**:

   .. code-block:: bash

      cd frontend
      pnpm install
      pnpm build:registry

4. **Development Database**:

   .. code-block:: bash

      # Create test database or use existing one
      sqlite3 data/test.db < schema.sql

Code Style and Standards
------------------------

Python Standards
~~~~~~~~~~~~~~~

**Code Formatting**:
   Use ``ruff`` for formatting and linting:

   .. code-block:: bash

      ruff format .        # Format code
      ruff check .         # Check for issues
      ruff check . --fix   # Auto-fix issues

**Type Hints**:
   All Python code should include type hints:

   .. code-block:: python

      def process_query(messages: Messages, timeout: Optional[int] = None) -> str:
          """Process a query with optional timeout."""
          return result

**Docstrings**:
   Use Google-style docstrings:

   .. code-block:: python

      def create_agent(name: str, config: Dict[str, Any]) -> BaseAgent:
          """Create a new agent instance.
          
          Args:
              name: The name of the agent to create
              config: Configuration dictionary for the agent
              
          Returns:
              BaseAgent: The configured agent instance
              
          Raises:
              ValueError: If agent name is not recognized
          """

**Imports**:
   Organize imports according to PEP8:

   .. code-block:: python

      # Standard library
      import os
      import sys
      from typing import List, Optional
      
      # Third-party
      import pandas as pd
      from pydantic import BaseModel
      
      # Local imports
      from yaaf.components.agents.base_agent import BaseAgent
      from yaaf.components.data_types import Messages

TypeScript/Frontend Standards
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Code Formatting**:
   Use Prettier and ESLint:

   .. code-block:: bash

      pnpm lint           # Check linting
      pnpm format:check   # Check formatting
      pnpm format:write   # Apply formatting

**Type Safety**:
   Ensure all TypeScript code is properly typed:

   .. code-block:: typescript

      interface ChatMessage {
        id: string
        content: string
        role: 'user' | 'assistant'
        timestamp: Date
        agentName?: string
      }

**Component Structure**:
   Follow consistent component patterns:

   .. code-block:: tsx

      interface ComponentProps {
        title: string
        onAction?: () => void
      }
      
      export function Component({ title, onAction }: ComponentProps) {
        return (
          <div>
            <h1>{title}</h1>
            {onAction && <button onClick={onAction}>Action</button>}
          </div>
        )
      }

Testing
-------

Backend Testing
~~~~~~~~~~~~~~

**Unit Tests**:
   Use Python's unittest framework:

   .. code-block:: python

      import unittest
      from yaaf.components.agents.sql_agent import SqlAgent
      
      class TestSqlAgent(unittest.TestCase):
          def setUp(self):
              self.agent = SqlAgent(mock_client, mock_source)
          
          def test_query_processing(self):
              messages = Messages().add_user_utterance("Get user count")
              result = asyncio.run(self.agent.query(messages))
              self.assertIn("SELECT", result)

**Running Tests**:

   .. code-block:: bash

      # Run all tests
      python -m unittest discover tests/
      
      # Run specific test
      python -m unittest tests.test_sql_agent
      
      # Run with coverage
      coverage run -m unittest discover tests/
      coverage report

**Test Structure**:

   .. code-block:: text

      tests/
      ├── test_agents/
      │   ├── test_base_agent.py
      │   ├── test_sql_agent.py
      │   └── test_orchestrator_agent.py
      ├── test_data_types/
      │   ├── test_messages.py
      │   └── test_notes.py
      └── test_server/
          ├── test_routes.py
          └── test_accessories.py

Frontend Testing
~~~~~~~~~~~~~~~

**Jest Testing**:

   .. code-block:: bash

      cd frontend
      pnpm test           # Run tests
      pnpm test:watch     # Watch mode
      pnpm test:coverage  # With coverage

**Component Testing**:

   .. code-block:: tsx

      import { render, screen } from '@testing-library/react'
      import { Chat } from '@/components/chat'
      
      describe('Chat Component', () => {
        it('renders chat interface', () => {
          render(<Chat />)
          expect(screen.getByRole('textbox')).toBeInTheDocument()
        })
      })

Integration Testing
~~~~~~~~~~~~~~~~~~

**End-to-End Tests**:
   Test complete workflows:

   .. code-block:: python

      class TestIntegration(unittest.TestCase):
          def test_complete_query_flow(self):
              # Test: User query -> Orchestrator -> SQL Agent -> Response
              orchestrator = build_orchestrator()
              messages = Messages().add_user_utterance("How many users?")
              
              response = asyncio.run(orchestrator.query(messages))
              self.assertIn("users", response.lower())

Debugging
---------

Backend Debugging
~~~~~~~~~~~~~~~~

**Logging Setup**:

   .. code-block:: python

      import logging
      
      logging.basicConfig(
          level=logging.DEBUG,
          format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      )

**Debug Configuration**:

   .. code-block:: python

      # Enable debug mode
      import os
      os.environ['YAAF_DEBUG'] = 'true'

**Common Debug Points**:
   * Agent query processing
   * Message routing in orchestrator
   * Artifact creation and storage
   * Database connection issues

Frontend Debugging
~~~~~~~~~~~~~~~~~

**Browser DevTools**:
   * Use React Developer Tools
   * Monitor Network tab for API calls
   * Check Console for errors
   * Use Sources tab for breakpoints

**Debug Logging**:

   .. code-block:: typescript

      console.log('Processing note:', note)
      console.error('API call failed:', error)
      console.debug('State update:', newState)

**Common Issues**:
   * API connectivity problems
   * State management issues
   * Component rendering problems
   * TypeScript type errors

Performance Monitoring
---------------------

Backend Performance
~~~~~~~~~~~~~~~~~

**Timing Decorators**:

   .. code-block:: python

      import time
      import functools
      
      def timing_decorator(func):
          @functools.wraps(func)
          async def wrapper(*args, **kwargs):
              start = time.time()
              result = await func(*args, **kwargs)
              duration = time.time() - start
              logger.info(f"{func.__name__} took {duration:.2f}s")
              return result
          return wrapper

**Memory Monitoring**:

   .. code-block:: python

      import psutil
      import os
      
      def log_memory_usage():
          process = psutil.Process(os.getpid())
          memory_mb = process.memory_info().rss / 1024 / 1024
          logger.info(f"Memory usage: {memory_mb:.1f} MB")

Frontend Performance
~~~~~~~~~~~~~~~~~~

**React DevTools Profiler**:
   Use the Profiler tab to identify slow components

**Web Vitals**:

   .. code-block:: typescript

      import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'
      
      getCLS(console.log)
      getFID(console.log)
      getFCP(console.log)
      getLCP(console.log)
      getTTFB(console.log)

Contributing
-----------

Git Workflow
~~~~~~~~~~~

**Branch Naming**:
   * ``feature/description`` - New features
   * ``fix/description`` - Bug fixes
   * ``docs/description`` - Documentation updates
   * ``refactor/description`` - Code refactoring

**Commit Messages**:
   Use conventional commit format:

   .. code-block:: bash

      feat: add new RAG agent for document retrieval
      fix: resolve SQL injection vulnerability in queries
      docs: update API documentation for new endpoints
      refactor: simplify orchestrator agent routing logic

**Pull Request Process**:

1. **Create Feature Branch**:

   .. code-block:: bash

      git checkout -b feature/new-agent-type
      git commit -m "feat: implement new agent type"
      git push origin feature/new-agent-type

2. **Create Pull Request**:
   * Provide clear description
   * Include test coverage
   * Update documentation
   * Follow code review feedback

Code Review Guidelines
~~~~~~~~~~~~~~~~~~~~~

**Review Checklist**:
   * Code follows style guidelines
   * Tests are included and passing
   * Documentation is updated
   * No security vulnerabilities
   * Performance implications considered

**Review Process**:
   * At least one reviewer required
   * All tests must pass
   * Documentation must be updated
   * Security review for sensitive changes

Documentation
~~~~~~~~~~~~

**API Documentation**:
   Update docstrings and API reference when adding new features

**User Documentation**:
   Update guides and examples for user-facing changes

**Code Comments**:
   Add comments for complex logic or business rules

Release Process
--------------

Version Management
~~~~~~~~~~~~~~~~~

**Semantic Versioning**:
   * ``MAJOR.MINOR.PATCH`` format
   * Major: Breaking changes
   * Minor: New features (backward compatible)
   * Patch: Bug fixes

**Release Branches**:

   .. code-block:: bash

      git checkout -b release/1.2.0
      # Update version numbers
      # Final testing
      git tag v1.2.0
      git push origin v1.2.0

Deployment
~~~~~~~~~

**Backend Deployment**:

   .. code-block:: bash

      # Production deployment
      python -m yaaf backend 4000
      
      # With production config
      YAAF_CONFIG=production.json python -m yaaf backend

**Frontend Deployment**:

   .. code-block:: bash

      cd frontend
      pnpm build
      pnpm start

**Docker Deployment**:

   .. code-block:: dockerfile

      # Backend Dockerfile
      FROM python:3.9
      WORKDIR /app
      COPY requirements.txt .
      RUN pip install -r requirements.txt
      COPY . .
      CMD ["python", "-m", "yaaf", "backend", "4000"]

Best Practices
--------------

Security
~~~~~~~

* **Input Validation**: Validate all user inputs
* **SQL Injection**: Use parameterized queries
* **XSS Prevention**: Sanitize HTML output
* **Authentication**: Implement proper auth for production
* **Secrets Management**: Use environment variables for secrets

Performance
~~~~~~~~~~

* **Database Optimization**: Use indexes and efficient queries
* **Caching**: Implement appropriate caching strategies
* **Resource Management**: Monitor memory and CPU usage
* **Async Operations**: Use async/await for I/O operations

Maintainability
~~~~~~~~~~~~~~

* **Modular Design**: Keep components loosely coupled
* **Clear Interfaces**: Define clear APIs between components
* **Documentation**: Maintain up-to-date documentation
* **Testing**: Achieve good test coverage
* **Monitoring**: Implement logging and error tracking