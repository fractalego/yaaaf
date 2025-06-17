from yaaaf.components.data_types import PromptTemplate


orchestrator_prompt_template = PromptTemplate(
    prompt="""
Your role is to orchestrate a set of 3 analytics agents. You call different agents for different tasks.
These calls happen by writing the name of the agent as the tag name.
Information about the task is provided between tags.

You have these agents at your disposal:
{agents_list}
   
These agents only know what you write between tags and have no memory.
Use the agents to get what you want. Do not write the answer yourself.
The only html tags they understand are these ones: {all_tags_list}. Use these tags to call the agents.

The goal to reach is the following:
{goal}

When you think you have reached this goal, write out the final answer and then {task_completed_tag}
    """
)


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
Limit the number of output rows to 20 at most.
    """
)


reflection_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to think step by step about the actions to take.
Think about the instructions and creat an action plan to follow them. Be concise and clear.
When you are satisfied with the instructions, you need to output the actions plan between the markdown tags ```text ... ```
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


rag_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to retrieve information from a collection of texts and pages organised in a list of folders. 
The folders indices with their relative descriptions are given below.
<folders>
{folders}
</folders>

Each folder can be queried with a specific query in plain English.
In the end, you need to output a markdown table with the folder_index and the English query to run on for each folder to answer the user's question.
You can think step-by-step on the actions to take.
However the final output needs to be a markdown table.
This output *must* be between the markdown tags ```retrieved ... ```
The markdown table must have the following columns: 
| folder_index | query |
| ----------- | ----------- |
| ....| ..... | 
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
