Brave Search Agent
==================

The Brave Search Agent provides web search capabilities using the Brave Search API, offering an alternative to the DuckDuckGo search agent with a focus on privacy and independent search results.

Overview
--------

The Brave Search Agent integrates with Brave's independent search index to provide web search functionality within YAAAF. It maintains the same interface patterns as other search agents while leveraging Brave's privacy-focused search infrastructure.

**Key Features:**

* **Independent Search**: Uses Brave's own search index, not relying on Google or Bing
* **Privacy-Focused**: Aligns with Brave's privacy-first approach
* **API Authentication**: Secure API key-based authentication
* **Structured Results**: Returns formatted results in DataFrame format
* **Artifact Storage**: Results stored as artifacts for frontend display
* **Error Handling**: Robust error handling for API failures

Configuration
-------------

API Key Setup
^^^^^^^^^^^^^

To use the Brave Search Agent, you need a Brave Search API key:

1. **Sign up** for Brave Search API at `https://api.search.brave.com/`
2. **Obtain your API key** from the Brave developer console
3. **Configure the key** in your YAAAF configuration

Configuration File
^^^^^^^^^^^^^^^^^^

Add the Brave Search Agent to your configuration:

.. code-block:: json

   {
     "agents": [
       "reflection",
       "visualization", 
       "sql",
       "websearch",
       "brave_search",
       "url_reviewer"
     ],
     "api_keys": {
       "brave_search_api_key": "YOUR_BRAVE_SEARCH_API_KEY_HERE"
     }
   }

Environment Variables
^^^^^^^^^^^^^^^^^^^^^

Alternatively, you can set the API key via environment variable (if supported in future versions):

.. code-block:: bash

   export BRAVE_SEARCH_API_KEY="your-api-key-here"

Usage
-----

Agent Tag
^^^^^^^^^

To use the Brave Search Agent in conversations, use the agent tag:

.. code-block:: text

   <bravesearchagent>search query here</bravesearchagent>

**Example:**

.. code-block:: text

   <bravesearchagent>latest developments in renewable energy 2024</bravesearchagent>

Orchestrator Integration
^^^^^^^^^^^^^^^^^^^^^^^^

The agent integrates seamlessly with the orchestrator system. When the orchestrator determines that web search is needed, it can choose between DuckDuckGo and Brave search agents based on availability and configuration.

**Example conversation:**

.. code-block:: text

   User: "Find recent news about artificial intelligence breakthroughs"
   
   Orchestrator: <bravesearchagent>artificial intelligence breakthroughs 2024 recent news</bravesearchagent>
   
   Response: The result is in this artifact <artefact type='brave-search-result'>search-123</artefact>.

API Details
-----------

Endpoint
^^^^^^^^

The agent makes requests to the Brave Search API:

* **URL**: ``https://api.search.brave.com/res/v1/web/search``
* **Method**: ``GET``
* **Authentication**: ``X-Subscription-Token`` header

Request Parameters
^^^^^^^^^^^^^^^^^^

* ``q``: Search query string
* ``count``: Number of results to return (default: 5, max: 20)

Response Format
^^^^^^^^^^^^^^^

The agent processes Brave's JSON response and extracts:

* **Title**: Page title
* **Summary**: Page description/snippet  
* **URL**: Page URL

Results are formatted into a pandas DataFrame with columns: ``Title``, ``Summary``, ``URL``.

Error Handling
--------------

The Brave Search Agent includes comprehensive error handling:

**API Errors:**
  * Network timeouts
  * HTTP status errors
  * Authentication failures
  * Rate limiting

**Data Errors:**
  * JSON parsing errors
  * Missing response fields
  * Empty result sets

**Graceful Degradation:**
  * Returns empty results on errors
  * Logs detailed error information
  * Continues conversation flow

Frontend Integration
--------------------

React Component
^^^^^^^^^^^^^^^

The frontend includes a dedicated React component for displaying Brave search operations:

.. code-block:: typescript

   <BraveSearchAgent text="search query" />

**Styling:**
  * Orange background (``bg-orange-100``)
  * Shield-check icon (representing privacy focus)
  * Dark mode support (``dark:bg-orange-800``)

Markdown Rendering
^^^^^^^^^^^^^^^^^^

The agent tag is automatically rendered in the chat interface:

.. code-block:: text

   <bravesearchagent>renewable energy innovations</bravesearchagent>

This displays as a styled component showing the search operation.

Implementation Details
----------------------

Class Structure
^^^^^^^^^^^^^^^

.. code-block:: python

   class BraveSearchAgent(BaseAgent):
       def __init__(self, client: BaseClient)
       async def query(self, messages: Messages, notes: Optional[List[str]] = None) -> str
       def _search_brave(self, query: str, max_results: int = 5) -> List[Dict[str, str]]
       def get_description(self) -> str

Key Methods
^^^^^^^^^^^

**``__init__``**
  * Initializes the agent with API key validation
  * Raises ``ValueError`` if API key is missing

**``query``**
  * Main entry point for search operations
  * Handles multi-step conversation flow
  * Returns artifact references for results

**``_search_brave``**
  * Internal method for API communication
  * Handles authentication and response parsing
  * Returns structured result list

Configuration Validation
^^^^^^^^^^^^^^^^^^^^^^^^^

The agent validates configuration on initialization:

.. code-block:: python

   if not self._api_key:
       raise ValueError(
           "Brave Search API key is required but not found in configuration. "
           "Please set 'api_keys.brave_search_api_key' in your config."
       )

Testing
-------

Unit Tests
^^^^^^^^^^

Comprehensive test suite covering:

* **Initialization**: With and without API keys
* **API Communication**: Success and error scenarios  
* **Response Parsing**: Various response formats
* **Integration**: End-to-end query processing

**Running Tests:**

.. code-block:: bash

   python -m unittest tests.test_brave_search_agent -v

Mock Testing
^^^^^^^^^^^^

Tests use mocked API responses to avoid external dependencies:

.. code-block:: python

   @patch('yaaaf.components.agents.brave_search_agent.requests.get')
   def test_search_brave_success(self, mock_get):
       # Test implementation with mocked API response

Comparison with DuckDuckGo Agent
---------------------------------

**Similarities:**
  * Same interface and usage patterns
  * Identical DataFrame output format
  * Same artifact storage mechanism
  * Compatible orchestrator integration

**Differences:**
  * **Search Index**: Uses Brave's independent index vs DuckDuckGo
  * **Authentication**: Requires API key vs free API
  * **Privacy Focus**: Aligns with Brave's privacy-first approach
  * **Result Sources**: May provide different or more diverse results

**When to Use Brave vs DuckDuckGo:**
  * **Brave**: When you need API key-based access, privacy-focused results, or independent search index
  * **DuckDuckGo**: For quick setup without API requirements, or when API limits are a concern

Troubleshooting
---------------

Common Issues
^^^^^^^^^^^^^

**"API key is required" Error:**
  * Ensure ``brave_search_api_key`` is set in configuration
  * Verify the key is valid and active
  * Check for trailing spaces or formatting issues

**No Search Results:**
  * Verify API key has sufficient quota
  * Check network connectivity to Brave API
  * Review query formatting and length

**Rate Limiting:**
  * Monitor API usage against your plan limits
  * Implement query caching if needed
  * Consider upgrading API plan for higher limits

**API Authentication Errors:**
  * Verify API key is correctly formatted
  * Check that the key hasn't expired
  * Ensure proper header formatting

Debug Logging
^^^^^^^^^^^^^

Enable debug logging to troubleshoot issues:

.. code-block:: bash

   # Set logging level to see detailed API interactions
   export PYTHONPATH=/path/to/yaaaf
   python -c "
   import logging
   logging.basicConfig(level=logging.DEBUG)
   # Your YAAAF code here
   "

Best Practices
--------------

API Usage
^^^^^^^^^

* **Monitor Quotas**: Keep track of API usage limits
* **Cache Results**: Consider caching for frequently searched terms
* **Error Handling**: Always handle API errors gracefully
* **Rate Limiting**: Respect API rate limits in high-usage scenarios

Security
^^^^^^^^

* **Secure Storage**: Store API keys securely, never in source code
* **Environment Variables**: Use environment variables for production deployments
* **Key Rotation**: Regularly rotate API keys as security best practice
* **Access Control**: Limit API key access to necessary personnel only

Performance
^^^^^^^^^^^

* **Result Limits**: Use appropriate result limits (5-10 for most use cases)
* **Query Optimization**: Craft specific queries for better results
* **Timeout Handling**: Implement appropriate timeouts for API calls
* **Fallback Strategy**: Consider fallback to DuckDuckGo if Brave API fails

Future Enhancements
-------------------

Planned improvements for the Brave Search Agent include:

* **Advanced Filtering**: Support for date ranges, language filters, and content types
* **Image Search**: Integration with Brave's image search capabilities  
* **News Search**: Dedicated news search functionality
* **Search Analytics**: Usage statistics and performance metrics
* **Caching Layer**: Built-in result caching to reduce API calls
* **Batch Processing**: Support for multiple simultaneous queries

For the latest updates and feature requests, check the YAAAF project repository.