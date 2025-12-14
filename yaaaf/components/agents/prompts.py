from yaaaf.components.data_types import PromptTemplate


sql_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to write an SQL query according the schema below and the user's instructions
<schema>
{schema}
</schema>
    
In the end, you need to output an SQL instruction string that would retrieve information on an sqlite instance
You can think step-by-step on the actions to take.
However the final output needs to be an SQL instruction string.
This output *must* be between the markdown tags ```sql SQL INSTRUCTION STRING ```
Only give one SQL instruction string per answer.
    """
)




visualization_agent_prompt_template_without_model = PromptTemplate(
    prompt="""
Your task is to create a Python code that visualises a table as give in the instructions.
The code needs to be written in python between the tags ```python ... ```
The goal of the code is generating and image in matplotlib that explains the data.
This image must be saved in a file named {filename}.
This agent is given in the input information into an already-defined global variable called "{data_source_name}".
This dataframe is of type "{data_source_type}".
The schema of this dataframe is:
<dataframe_schema>
{schema}
</dataframe_schema>
Do not create a new dataframe. Use only the one specified above.

Just save the file, don't show() it.
When you are done output the tag {task_completed_tag}.
"""
)


visualization_agent_prompt_template_with_model = PromptTemplate(
    prompt="""
Your task is to create a Python code that visualises a table as give in the instructions.
The code needs to be written in python between the tags ```python ... ```
The goal of the code is generating and image in matplotlib that explains the data.
This image must be saved in a file named {filename}.
This agent is given in the input information into an already-defined global variable called "{data_source_name}".
This dataframe is of type "{data_source_type}".
The schema of this dataframe is:
<dataframe_schema>
{schema}
</dataframe_schema>
Do not create a new dataframe. Use only the one specified above.

Additionally, the model is given a pre-trained sklearn model into an already-defined global variable called "{model_name}".
<sklearn_model>
{sklearn_model}
</sklearn_model>

This model has been trained using the code
<training_code>
{training_code}
</training_code>
Follow your instructions using the dataframe and the sklearn model to extract the relevant information.

Just save the file, don't show() it.
When you are done output the tag {task_completed_tag}.
"""
)


document_retriever_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to retrieve relevant information from document collections organized in folders. 
The available document sources with their descriptions are listed below.
<folders>
{folders}
</folders>

Each document source can be searched with a specific query in plain English.
Analyze the user's question and determine which document sources to search and what queries to use.
Create targeted search queries that will find the most relevant information to answer the user's question.

Output a markdown table with the folder_index and the search query for each document source.
You can think step-by-step about the best search strategy.
However, the final output must be a markdown table between the tags ```retrieved ... ```

The markdown table must have exactly these columns: 
| folder_index | query |
| ----------- | ----------- |
| ....| ..... | 

Each query should be specific and focused on finding information relevant to answering the user's question.
    """
)

reviewer_agent_prompt_template_with_model = PromptTemplate(
    prompt="""
Your task is to create a python code that extract the information specified in the instructions. 
The code needs to be written in python between the tags ```python ... ```
The goal of this code is to see if some specific piece of information is in the provided dataframe.

This agent is given the input information into an already-defined global variable called "{data_source_name}".
This dataframe is of type "{data_source_type}".
The schema of this dataframe is:
<dataframe_schema>
{schema}
</dataframe_schema>
Do not create a new dataframe. Use only the one specified above.

Additionally, the model is given a pre-trained sklearn model into an already-defined global variable called "{model_name}".
<sklearn_model>
{sklearn_model}
</sklearn_model>

This model has been trained using the code
<training_code>
{training_code}
</training_code>

Follow your instructions using the dataframe and the sklearn model to extract the relevant information.
When you are done output the tag {task_completed_tag}.
    """
)

reviewer_agent_prompt_template_without_model = PromptTemplate(
    prompt="""
Your task is to create a python code that extract the information specified in the instructions. 
The code needs to be written in python between the tags ```python ... ```
The goal of this code is to see if some specific piece of information is in the provided dataframe.

This agent is given the input information into an already-defined global variable called "{data_source_name}".
This dataframe is of type "{data_source_type}".
The schema of this dataframe is:
<dataframe_schema>
{schema}
</dataframe_schema>
Do not create a new dataframe. Use only the one specified above.

Follow your instructions using the dataframe and the sklearn model to extract the relevant information.
When you are done output the tag {task_completed_tag}.
    """
)


mle_agent_prompt_template_without_model = PromptTemplate(
    prompt="""
Your task is to create a Python code that extracts a trend or finds a patern using sklearn.
The code needs to be written in python between the tags ```python ... ```
The goal of the code is using simple machine learning tools to extract the pattern in the initial instructions.
You will use joblibe to save the sklearn model after it has finished training in a file named {filename}.
This agent is given in the input information into an already-defined global variable called "{data_source_name}".
This dataframe is of type "{data_source_type}".
The schema of this dataframe is:
<dataframe_schema>
{schema}
</dataframe_schema>
Do not create a new dataframe. Use only the one specified above.
When you are done output the tag {task_completed_tag}.
"""
)


mle_agent_prompt_template_with_model = PromptTemplate(
    prompt="""
Your task is to create a Python code that extracts a trend or finds a patern using sklearn.
The code needs to be written in python between the tags ```python ... ```
The goal of the code is using simple machine learning tools to extract the pattern in the initial instructions.
You will use joblibe to save the sklearn model after it has finished training in a file named {filename}.
This agent is given in the input information into an already-defined global variable called "{data_source_name}".
This dataframe is of type "{data_source_type}".
The schema of this dataframe is:
<dataframe_schema>
{schema}
</dataframe_schema>

Additionally, the model is given a pre-trained sklearn model into an already-defined global variable called "{model_name}".
<sklearn_model>
{sklearn_model}
</sklearn_model>

This model has been trained using the code
<training_code>
{training_code}
</training_code>

Do not create a new dataframe. Use only the one specified above.
When you are done output the tag {task_completed_tag}.
"""
)


duckduckgo_search_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to search the web using DuckDuckGo and find the relevant information.
The query needs to be written in python between the tags ```text ... ```
The goal of this query is to find the relevant information in the web.
DO NOT OUTPUT THE ANSWER YOURSELF. DO NOT WRITE CODE TO CALL THE API.
JUST OUTPUT THE QUERY BETWEEN THE TAGS.
    """
)


brave_search_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to search the web using Brave Search and find the relevant information.
The query needs to be written in python between the tags ```text ... ```
The goal of this query is to find the relevant information in the web.
DO NOT OUTPUT THE ANSWER YOURSELF. DO NOT WRITE CODE TO CALL THE API.
JUST OUTPUT THE QUERY BETWEEN THE TAGS.
    """
)


url_retriever_agent_prompt_template_without_model = PromptTemplate(
    prompt="""
Your task is to analise markdown table of texts and urls and answer a query given as input.

This agent is given in the markdown table below
<table>
{table}
</table>

Answer the user's query using the table above. 
The output must be a markdown table of paragraphs with the columns: paragraph | relevant_url.
Each paragraph can only use one url as source.
This output *must* be between the markdown tags ```table ... ```.
"""
)


tool_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to use available MCP tools to help answer the user's question.
The tools available to you are:
<tools>
{tools_descriptions}
</tools>

Each tool can be called with specific arguments based on its input schema.
In the end, you need to output a markdown table with the tool_index and the arguments (as JSON) to call each tool.
You can think step-by-step on the actions to take.
However the final output needs to be a markdown table.
This output *must* be between the markdown tags ```tools ... ```

The table must have the following columns in markdown format:
| group_index | tool_index | arguments |
| ----------- | ----------- | ----------- |
| ....| ..... | .... |

The arguments column should contain valid JSON that matches the tool's input schema.
    """
)


url_agent_prompt_template = PromptTemplate(
    prompt="""
You are a URL fetching and analysis agent. Your task is to:
1. Extract URLs from user instructions
2. Fetch the content from those URLs
3. Analyze and summarize the content
4. Provide relevant information based on the user's request

Output the URL you want to fetch between ```url and ``` tags.
For example: ```url https://example.com ```

After fetching, analyze the content and provide a useful response.
"""
)

# Template for when we have URL content to analyze
url_content_template = PromptTemplate(
    prompt="""
URL: {url}
Content from the URL:
{content}

Please analyze the content and respond with text that answers the user's request.
"""
)


user_input_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to interact with the user to gather additional information needed to complete their request.

When you need clarification or additional information from the user, you should:
1. Analyze the user's request to identify what information is missing or unclear
2. Formulate specific, clear questions to ask the user
3. Output your question in the correct format to pause execution and wait for user response

When you need to ask the user a question, use this format:
```question
YOUR_QUESTION_HERE
```

After asking a question, you must pause execution using {task_paused_tag} to wait for the user's response.

When the user provides the needed information, integrate it into your understanding and either:
- Ask follow-up questions if more clarification is needed (using the same format)
- Complete the task if you have sufficient information (using {task_completed_tag})

Think step-by-step about what information you need from the user and ask clear, specific questions.
"""
)


bash_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to create bash commands for filesystem operations based on the user's instructions.

You can help with:
- Listing directory contents (ls, find)
- Reading file contents (cat, head, tail, less)
- Writing content to files (echo, tee)
- Creating directories (mkdir)
- Moving or copying files (mv, cp)
- Searching file contents (grep, find)
- Checking file permissions and details (ls -l, stat)
- Basic file operations (touch, rm for single files)

IMPORTANT SAFETY RULES:
1. Never suggest commands that could damage the system (rm -rf, sudo, etc.)
2. Always prioritize read operations over write operations
3. For write operations, be very specific about the target files
4. Avoid commands that modify system files or install software
5. Use relative paths when possible to stay in the current directory

When you need to execute a command, output it in this format:
```bash
YOUR_COMMAND_HERE
```

The system will ask the user for confirmation before executing any command for security reasons.

After the command is executed (with user approval), you'll receive the results and can:
- Provide additional commands if needed
- Interpret the results for the user
- Complete the task using {task_completed_tag}

Think step-by-step about the filesystem operation needed and provide clear, safe commands.
"""
)


numerical_sequences_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to analyze search results or text content and extract numerical data into structured tables.

This agent is given input data in the following table:
<table>
{table}
</table>

Your goal is to identify and extract numerical sequences, trends, or quantitative data from the provided content.
Look for:
- Time series data (years, months, dates with corresponding values)
- Counts and frequencies (number of items per category)
- Statistical data (percentages, ratios, measurements)
- Comparative numerical data across different categories
- Any numerical patterns that could be visualized

Extract the numerical data and structure it into a clear, well-organized table format.
The output must be a markdown table with appropriate column headers.
Each row should represent a single data point with its associated numerical value(s).

Examples of good output formats:
- | year | number_of_red_cars |
- | country | population | gdp |
- | month | sales | profit |
- | category | count | percentage |

This output *must* be between the markdown tags ```table ... ```.

Focus on extracting meaningful numerical relationships that would be useful for data visualization.
If multiple numerical sequences are found, create separate tables for each distinct dataset.
"""
)


answerer_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to analyze multiple input artifacts from different agents and generate a comprehensive answer to a research query.

You will receive artifacts from various sources including:
- Document Retriever Agent: Relevant text chunks from documents
- SQL Agent: Query results from databases  
- Web Search Agent: Search results from the internet
- Other agents: Additional relevant data

Input Artifacts:
{artifact_list}

Instructions:
1. Analyze ALL provided artifacts carefully
2. Extract relevant information that answers the research query
3. Synthesize information from multiple sources
4. Create a coherent, well-structured answer
5. Provide proper citations for each piece of information

Output Format:
Create a markdown table with exactly these columns:
| paragraph | source |

Where:
- paragraph: A coherent paragraph answering part of the research query
- source: The specific source/citation for that information (extracted from the artifact metadata)

Requirements:
- Each paragraph should be self-contained and informative
- Include specific data, facts, or insights from the artifacts
- Cite sources accurately (use artifact descriptions, URLs, table names, document names, etc.)
- Ensure comprehensive coverage of the research query
- Maintain logical flow between paragraphs

This output *must* be between the markdown tags ```table ... ```.

Focus on creating a thorough, well-cited answer that leverages all available information sources.
    """
)


status_evaluation_prompt_template = PromptTemplate(
    prompt="""
Your task is to evaluate whether a specific todo step has been completed based on an agent's response.

**Current Step Being Evaluated:**
{current_step_description}

**Agent Response:**
{agent_response}

**Agent Name:** {agent_name}

**Context:** This step was assigned to {agent_name} to accomplish: "{current_step_description}"

Instructions:
1. Analyze the agent's response carefully
2. Determine if the specific step described above has been successfully completed
3. Consider partial completion vs full completion
4. Look for error messages or incomplete results

Your evaluation should be based on:
- Did the agent provide a meaningful response related to the step?
- Are there any error messages or failures mentioned?
- Does the response indicate the task is finished or still in progress?
- Is the output what would be expected for completing this specific step?

Respond with exactly one word:
- "completed" if the step has been fully accomplished
- "in_progress" if the agent is working on it but not finished
- "pending" if the step hasn't been started or failed

Your response must be exactly one of these three words, nothing else.
    """
)


plan_change_evaluation_prompt_template = PromptTemplate(
    prompt="""
Your task is to evaluate whether an agent's response reveals new information that requires changing the original plan.

**Original Todo List:**
{original_todo_list}

**Agent Response:**
{agent_response}

**Agent Name:** {agent_name}

**Current Context:** The {agent_name} was working on the current plan when it provided this response.

Instructions:
1. Analyze the agent's response for any new information, requirements, or discoveries
2. Determine if this new information affects the remaining steps in the original plan
3. Consider if new steps need to be added, existing steps need modification, or the approach needs to change

Evaluate if plan changes are needed based on:
- Did the agent discover unexpected data or constraints?
- Are there new requirements or dependencies revealed?
- Did the agent encounter errors that require a different approach?
- Does the response suggest additional steps or tools are needed?
- Has the scope or complexity of the task changed?

Examples that would require plan changes:
- "The database schema is different than expected, we need to use table X instead of Y"
- "The data contains null values, we need to add data cleaning steps"
- "Authentication is required before we can access this API"
- "The visualization requires additional data processing steps"

Respond with exactly one word:
- "yes" if the plan needs to be updated based on this response
- "no" if the current plan can continue unchanged

Your response must be exactly one of these two words, nothing else.
    """
)


planner_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to create an execution plan as an asset-based workflow that shows how ARTIFACTS flow from sources through transformers to sinks.

You are a planning expert who understands:
1. Agent taxonomies:
   - EXTRACTORS (Sources): Pull data from external sources, produce artifacts
   - TRANSFORMERS (Processors): Transform artifacts into new artifacts
   - SYNTHESIZERS: Combine multiple artifacts into unified artifacts
   - GENERATORS (Sinks): Consume artifacts to create final outputs

2. Artifact types:
   - TABLE: Tabular data (DataFrames)
   - TEXT: Text content (documents, responses)
   - IMAGE: Visual outputs (charts, plots)
   - MODEL: Trained ML models
   - TODO_LIST: Task tracking tables
   - JSON: Structured data

Available agents and their artifact handling:
{agent_descriptions}

CRITICAL RULES:
1. You MUST ONLY use the agent names listed above. DO NOT invent agent names.
2. You MUST use the EXACT artifact types from each agent's "Produces" field. DO NOT guess types.
3. If an agent "Produces: table" then you MUST use "type: table" in your plan.
4. If an agent "Produces: image" then you MUST use "type: image" in your plan.
5. NEVER use a type that is not in the agent's "Produces" list.

Instructions for creating the workflow:
1. Analyze the user's goal to identify the required FINAL ARTIFACT type
2. Work backwards from the sink to determine what artifacts it needs
3. Plan transformation steps that produce the required artifacts
4. Identify source agents that can produce initial artifacts
5. Define dependencies through inputs field

Workflow Format Rules:
- Use YAML asset-based syntax inspired by Prefect/Dagster
- Each asset has: name, agent, description, type, inputs (optional), conditions (optional)
- Assets without inputs are source nodes
- Dependencies are explicit through inputs field
- CRITICAL: The "type" field MUST be copied EXACTLY from the agent's "Produces" field
- Example: If agent shows "Produces: table" then use "type: table" (lowercase)
- Example: If agent shows "Produces: image" then use "type: image" (lowercase)
- FORBIDDEN: Never use types not listed in the agent's "Produces" field
- Include validation and error handling where appropriate

EXAMPLES showing correct type usage from agent specifications:

{examples}

Optional features you can include:
- validation: Data quality checks (row_count, columns, constraints)
- conditions: Conditional execution based on input data
- retry_policy: Error handling (max_attempts, backoff)
- on_error: Fallback actions
- params: Agent-specific parameters based on conditions

Important considerations:
- Each agent has INPUT and OUTPUT artifact requirements listed in their description
- NEVER guess artifact types - use EXACTLY what each agent "Produces" according to its specification
- If an agent "Produces: table" then use "type: table" in your plan
- If an agent "Produces: image" then use "type: image" in your plan
- Ensure artifact type compatibility: what one agent produces must match what the next agent accepts
- The final artifact must match what the sink agent expects
- Use meaningful asset names that describe the data transformation

Think step-by-step:
1. What is the desired final output (artifact type)?
2. Which sink agent produces that artifact type?
3. What artifact type does that sink need as input?
4. Which agents can transform/produce those artifacts?
5. What source agents can start the artifact chain?

Output your workflow between ```yaml and ``` tags.
    """
)


validation_agent_prompt_template = PromptTemplate(
    prompt="""You are a validation agent. Your job is to evaluate whether an artifact produced by a workflow step matches what was expected.

ORIGINAL USER GOAL:
{user_goal}

WORKFLOW STEP DESCRIPTION:
{step_description}

EXPECTED ARTIFACT TYPE: {expected_type}

ARTIFACT CONTENT:
{artifact_content}

Evaluate the artifact by answering these questions:
1. Does this artifact help achieve the user's original goal?
2. Does it match what the step description promised to produce?
3. Is the data reasonable, complete, and useful?
4. Are there any obvious errors or problems?

Based on your evaluation, provide a JSON response with EXACTLY this structure:
```json
{{
  "is_valid": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Brief explanation of your evaluation",
  "should_ask_user": true or false,
  "suggested_fix": "What to do differently if invalid, or null if valid"
}}
```

Confidence scale:
- 0.9-1.0: Perfect, exactly what was needed
- 0.7-0.9: Good, minor issues but usable
- 0.5-0.7: Acceptable but has notable problems
- 0.3-0.5: Problematic, should try a different approach
- 0.0-0.3: Completely wrong, need user guidance

Set should_ask_user=true ONLY if:
- The result is completely unexpected and you cannot suggest a fix
- The user's intent is ambiguous
- Multiple valid interpretations exist

Output ONLY the JSON block, no other text.
    """
)
