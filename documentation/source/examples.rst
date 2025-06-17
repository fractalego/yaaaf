Examples
========

This section provides practical examples of using YAAAF for various tasks.

Basic Usage Examples
-------------------

Simple Query Processing
~~~~~~~~~~~~~~~~~~~~~~

**Example**: Basic question answering

.. code-block:: python

   from yaaaf.components.orchestrator_builder import OrchestratorBuilder
   from yaaaf.components.data_types import Messages
   from yaaaf.server.config import get_config
   
   # Build orchestrator with default configuration
   orchestrator = OrchestratorBuilder(get_config()).build()
   
   # Create a simple query
   messages = Messages().add_user_utterance("How many users are in the database?")
   
   # Process the query
   response = await orchestrator.query(messages)
   print(response)

**Expected Output**:

.. code-block:: text

   <sqlagent>
   SELECT COUNT(*) FROM users;
   </sqlagent>
   
   The query returned 1,247 users in the database.
   <Artefact>table_abc123</Artefact>

Data Analysis Workflow
~~~~~~~~~~~~~~~~~~~~~

**Example**: Complete data analysis pipeline

.. code-block:: python

   import asyncio
   from yaaaf.components.orchestrator_builder import OrchestratorBuilder
   from yaaaf.components.data_types import Messages
   
   async def analyze_sales_data():
       orchestrator = OrchestratorBuilder().build()
       
       # Step 1: Get sales data
       query1 = Messages().add_user_utterance(
           "Get sales data for the last 12 months by region"
       )
       response1 = await orchestrator.query(query1)
       
       # Step 2: Create visualization
       query2 = Messages().add_user_utterance(
           f"Create a bar chart showing sales by region. {response1}"
       )
       response2 = await orchestrator.query(query2)
       
       return response2
   
   # Run the analysis
   result = asyncio.run(analyze_sales_data())

Web Search Integration
~~~~~~~~~~~~~~~~~~~~~

**Example**: Combining web search with local data

.. code-block:: python

   async def research_with_context():
       orchestrator = OrchestratorBuilder().build()
       
       # Search for external information
       search_query = Messages().add_user_utterance(
           "Search for current AI industry trends and market size"
       )
       search_results = await orchestrator.query(search_query)
       
       # Combine with local analysis
       analysis_query = Messages().add_user_utterance(
           f"Compare our AI product sales with these industry trends: {search_results}"
       )
       analysis = await orchestrator.query(analysis_query)
       
       return analysis

Agent-Specific Examples
----------------------

SQL Agent Usage
~~~~~~~~~~~~~~

**Direct SQL Agent Usage**:

.. code-block:: python

   from yaaaf.components.agents.sql_agent import SqlAgent
   from yaaaf.components.sources.sqlite_source import SqliteSource
   from yaaaf.components.client import OllamaClient
   from yaaaf.components.data_types import Messages
   
   # Setup
   client = OllamaClient(model="qwen2.5:32b")
   source = SqliteSource("data/sales.db")
   sql_agent = SqlAgent(client, source)
   
   # Query examples
   queries = [
       "How many customers do we have?",
       "Show me top 10 products by revenue",
       "What's the average order value this month?",
       "List customers who haven't ordered in 6 months"
   ]
   
   for query in queries:
       messages = Messages().add_user_utterance(query)
       result = await sql_agent.query(messages)
       print(f"Query: {query}")
       print(f"Result: {result}\n")

**Example Output**:

.. code-block:: text

   Query: How many customers do we have?
   Result: ```SQL
   SELECT COUNT(*) FROM customers;
   ```
   The result is in this artifact <artefact type='table'>customers_count_456</artefact>.

Visualization Agent Usage
~~~~~~~~~~~~~~~~~~~~~~~~

**Creating Visualizations**:

.. code-block:: python

   from yaaaf.components.agents.visualization_agent import VisualizationAgent
   
   # Setup visualization agent
   viz_agent = VisualizationAgent(client)
   
   # Create visualization from SQL results
   messages = Messages().add_user_utterance(
       """Create a line chart showing monthly sales trends.
       <artefact>monthly_sales_data_789</artefact>"""
   )
   
   result = await viz_agent.query(messages)
   print(result)

**Visualization Instructions**:

.. code-block:: text

   # Different chart types
   "Create a bar chart showing sales by category"
   "Generate a scatter plot of price vs. quantity sold"
   "Make a pie chart of market share by competitor"
   "Create a histogram of customer ages"
   "Show a time series of website traffic"

Web Search Agent Usage
~~~~~~~~~~~~~~~~~~~~~

**Performing Web Searches**:

.. code-block:: python

   from yaaaf.components.agents.websearch_agent import DuckDuckGoSearchAgent
   
   # Setup web search agent
   search_agent = DuckDuckGoSearchAgent(client)
   
   # Search queries
   search_topics = [
       "Latest developments in artificial intelligence",
       "Python best practices 2024",
       "Market trends in e-commerce",
       "Customer service automation tools"
   ]
   
   for topic in search_topics:
       messages = Messages().add_user_utterance(topic)
       results = await search_agent.query(messages)
       print(f"Search: {topic}")
       print(f"Results: {results}\n")

Complex Workflow Examples
-------------------------

Multi-Agent Analysis Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Example**: Comprehensive business analysis

.. code-block:: python

   async def business_intelligence_report():
       orchestrator = OrchestratorBuilder().build()
       notes = []
       
       # Step 1: Reflection and planning
       planning_query = Messages().add_user_utterance(
           """Plan a comprehensive analysis of our business performance. 
           Consider sales data, market trends, and competitive landscape."""
       )
       plan = await orchestrator.query(planning_query, notes)
       
       # Step 2: Get internal sales data
       sales_query = Messages().add_user_utterance(
           "Get our sales performance data for the last year by product category"
       )
       sales_data = await orchestrator.query(sales_query, notes)
       
       # Step 3: Research market trends
       market_query = Messages().add_user_utterance(
           "Search for current market trends in our industry"
       )
       market_trends = await orchestrator.query(market_query, notes)
       
       # Step 4: Create visualizations
       viz_query = Messages().add_user_utterance(
           f"""Create visualizations showing:
           1. Our sales trends over time
           2. Product category performance
           
           Use this data: {sales_data}"""
       )
       visualizations = await orchestrator.query(viz_query, notes)
       
       # Step 5: Generate final report
       report_query = Messages().add_user_utterance(
           f"""Generate a comprehensive business intelligence report combining:
           - Sales analysis: {sales_data}
           - Market trends: {market_trends}
           - Visualizations: {visualizations}
           
           Provide insights and recommendations."""
       )
       final_report = await orchestrator.query(report_query, notes)
       
       return final_report, notes

RAG-Based Document Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Example**: Document-based question answering

.. code-block:: python

   from yaaaf.components.agents.rag_agent import RAGAgent
   from yaaaf.components.sources.text_source import TextSource
   
   # Setup RAG agent with document sources
   document_sources = [
       TextSource("documents/policies/"),
       TextSource("documents/procedures/"),
       TextSource("documents/guidelines/")
   ]
   
   rag_agent = RAGAgent(client, document_sources)
   
   # Document-based queries
   queries = [
       "What is our vacation policy for new employees?",
       "How do we handle customer complaints?",
       "What are the safety procedures for the warehouse?",
       "What's the process for requesting equipment?"
   ]
   
   for query in queries:
       messages = Messages().add_user_utterance(query)
       answer = await rag_agent.query(messages)
       print(f"Q: {query}")
       print(f"A: {answer}\n")

Machine Learning Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~

**Example**: Training and using ML models

.. code-block:: python

   async def ml_analysis_pipeline():
       orchestrator = OrchestratorBuilder().build()
       
       # Step 1: Get training data
       data_query = Messages().add_user_utterance(
           "Get customer data including demographics and purchase history"
       )
       training_data = await orchestrator.query(data_query)
       
       # Step 2: Train ML model
       ml_query = Messages().add_user_utterance(
           f"""Train a machine learning model to predict customer churn
           using this data: {training_data}"""
       )
       model_results = await orchestrator.query(ml_query)
       
       # Step 3: Visualize model performance
       viz_query = Messages().add_user_utterance(
           f"""Create visualizations showing:
           1. Model performance metrics
           2. Feature importance
           3. Prediction accuracy
           
           Use model results: {model_results}"""
       )
       performance_viz = await orchestrator.query(viz_query)
       
       return model_results, performance_viz

Frontend Integration Examples
----------------------------

Chat Interface Usage
~~~~~~~~~~~~~~~~~~~

**Example**: Frontend chat integration

.. code-block:: typescript

   // React component for chat interface
   import { useState } from 'react'
   import { Chat } from '@/components/ui/chat'
   
   export function BusinessAnalytics() {
     const [messages, setMessages] = useState<Message[]>([])
     
     const handleSendMessage = async (content: string) => {
       // Add user message
       const userMessage = {
         id: Date.now().toString(),
         content,
         role: 'user' as const,
         timestamp: new Date()
       }
       setMessages(prev => [...prev, userMessage])
       
       // Send to backend
       const response = await fetch('/api/chat', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           messages: [{ role: 'user', content }],
           session_id: 'analytics_session'
         })
       })
       
       // Handle streaming response
       // ... streaming logic
     }
     
     return (
       <div className="analytics-dashboard">
         <h1>Business Analytics Chat</h1>
         <Chat
           messages={messages}
           onSendMessage={handleSendMessage}
           placeholder="Ask about sales, customers, or market trends..."
         />
       </div>
     )
   }

Real-time Data Dashboard
~~~~~~~~~~~~~~~~~~~~~~~

**Example**: Live dashboard with agent integration

.. code-block:: typescript

   import { useEffect, useState } from 'react'
   
   interface DashboardData {
     salesMetrics: any
     customerAnalytics: any
     marketTrends: any
   }
   
   export function LiveDashboard() {
     const [data, setData] = useState<DashboardData>()
     const [loading, setLoading] = useState(true)
     
     useEffect(() => {
       const updateDashboard = async () => {
         setLoading(true)
         
         // Trigger multiple agent queries
         const queries = [
           'Get current sales metrics and KPIs',
           'Analyze customer behavior trends',
           'Search for relevant market updates'
         ]
         
         const results = await Promise.all(
           queries.map(query => 
             fetch('/api/chat', {
               method: 'POST',
               body: JSON.stringify({
                 messages: [{ role: 'user', content: query }],
                 session_id: `dashboard_${Date.now()}`
               })
             }).then(r => r.json())
           )
         )
         
         setData({
           salesMetrics: results[0],
           customerAnalytics: results[1],
           marketTrends: results[2]
         })
         setLoading(false)
       }
       
       // Update every 5 minutes
       updateDashboard()
       const interval = setInterval(updateDashboard, 5 * 60 * 1000)
       
       return () => clearInterval(interval)
     }, [])
     
     if (loading) return <div>Loading dashboard...</div>
     
     return (
       <div className="dashboard-grid">
         <DashboardCard title="Sales Metrics" data={data?.salesMetrics} />
         <DashboardCard title="Customer Analytics" data={data?.customerAnalytics} />
         <DashboardCard title="Market Trends" data={data?.marketTrends} />
       </div>
     )
   }

API Usage Examples
------------------

Direct API Calls
~~~~~~~~~~~~~~~~

**Example**: Using YAAAF API directly

.. code-block:: javascript

   // Create a new conversation stream
   async function startConversation(query) {
     const streamId = `session_${Date.now()}`
     
     // Create stream
     await fetch('http://localhost:4000/create_stream', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({
         stream_id: streamId,
         messages: [{ role: 'user', content: query }]
       })
     })
     
     // Poll for responses
     const pollForUpdates = async () => {
       const response = await fetch('http://localhost:4000/get_utterances', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({ stream_id: streamId })
       })
       
       const notes = await response.json()
       return notes
     }
     
     // Check for updates every second
     const interval = setInterval(async () => {
       const notes = await pollForUpdates()
       if (notes.length > 0) {
         console.log('New responses:', notes)
         // Process notes...
       }
     }, 1000)
     
     return { streamId, stopPolling: () => clearInterval(interval) }
   }
   
   // Usage
   const conversation = await startConversation("Analyze our sales performance")

Batch Processing
~~~~~~~~~~~~~~~

**Example**: Processing multiple queries

.. code-block:: python

   async def batch_analysis(queries):
       orchestrator = OrchestratorBuilder().build()
       results = []
       
       for query in queries:
           try:
               messages = Messages().add_user_utterance(query)
               response = await orchestrator.query(messages)
               results.append({
                   'query': query,
                   'response': response,
                   'status': 'success'
               })
           except Exception as e:
               results.append({
                   'query': query,
                   'error': str(e),
                   'status': 'error'
               })
       
       return results
   
   # Batch queries
   queries = [
       "Get monthly sales totals",
       "Find top performing products",
       "Analyze customer demographics",
       "Create sales trend visualization"
   ]
   
   results = await batch_analysis(queries)
   for result in results:
       print(f"Query: {result['query']}")
       if result['status'] == 'success':
           print(f"Response: {result['response'][:100]}...")
       else:
           print(f"Error: {result['error']}")
       print()

Error Handling Examples
----------------------

Robust Error Handling
~~~~~~~~~~~~~~~~~~~~~

**Example**: Comprehensive error handling

.. code-block:: python

   import logging
   from typing import Optional
   
   logger = logging.getLogger(__name__)
   
   async def robust_query_processing(query: str) -> Optional[str]:
       try:
           orchestrator = OrchestratorBuilder().build()
           messages = Messages().add_user_utterance(query)
           
           response = await orchestrator.query(messages)
           return response
           
       except ConnectionError as e:
           logger.error(f"Database connection failed: {e}")
           return "Sorry, I'm having trouble accessing the database right now."
           
       except ValueError as e:
           logger.error(f"Invalid query format: {e}")
           return "I don't understand that query. Could you rephrase it?"
           
       except Exception as e:
           logger.error(f"Unexpected error processing query '{query}': {e}")
           return "Something went wrong. Please try again later."

Frontend Error Handling
~~~~~~~~~~~~~~~~~~~~~~~

**Example**: User-friendly error handling

.. code-block:: typescript

   async function handleChatMessage(message: string) {
     try {
       setLoading(true)
       setError(null)
       
       const response = await fetch('/api/chat', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify({
           messages: [{ role: 'user', content: message }],
           session_id: sessionId
         })
       })
       
       if (!response.ok) {
         throw new Error(`Server error: ${response.status}`)
       }
       
       const data = await response.json()
       // Process successful response
       
     } catch (error) {
       console.error('Chat error:', error)
       
       if (error instanceof TypeError) {
         setError('Network connection problem. Please check your internet.')
       } else if (error.message.includes('500')) {
         setError('Server is temporarily unavailable. Please try again.')
       } else {
         setError('Something went wrong. Please try again.')
       }
     } finally {
       setLoading(false)
     }
   }

Performance Optimization Examples
--------------------------------

Efficient Query Processing
~~~~~~~~~~~~~~~~~~~~~~~~~

**Example**: Optimized batch processing

.. code-block:: python

   import asyncio
   from concurrent.futures import ThreadPoolExecutor
   
   async def parallel_analysis(queries: List[str]):
       orchestrator = OrchestratorBuilder().build()
       
       # Process queries in parallel
       tasks = []
       for query in queries:
           messages = Messages().add_user_utterance(query)
           task = orchestrator.query(messages)
           tasks.append(task)
       
       # Wait for all results
       results = await asyncio.gather(*tasks, return_exceptions=True)
       
       # Process results
       processed_results = []
       for i, result in enumerate(results):
           if isinstance(result, Exception):
               processed_results.append({
                   'query': queries[i],
                   'error': str(result)
               })
           else:
               processed_results.append({
                   'query': queries[i],
                   'response': result
               })
       
       return processed_results

Caching Strategy
~~~~~~~~~~~~~~~

**Example**: Response caching

.. code-block:: python

   from functools import lru_cache
   import hashlib
   
   class CachedOrchestrator:
       def __init__(self):
           self.orchestrator = OrchestratorBuilder().build()
           self.cache = {}
       
       def _hash_query(self, query: str) -> str:
           return hashlib.md5(query.encode()).hexdigest()
       
       async def query(self, query: str) -> str:
           query_hash = self._hash_query(query)
           
           # Check cache first
           if query_hash in self.cache:
               print(f"Cache hit for query: {query[:50]}...")
               return self.cache[query_hash]
           
           # Process query
           messages = Messages().add_user_utterance(query)
           response = await self.orchestrator.query(messages)
           
           # Cache response
           self.cache[query_hash] = response
           print(f"Cached response for query: {query[:50]}...")
           
           return response