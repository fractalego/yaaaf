from src.components.data_types import PromptTemplate


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

When you think you have reached your goal, write out the final answer and then <task-completed/>
    """
)


sql_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to write an SQL query according the schema below and the user's instructions
<schema>
{schema}
</schema>
    
In the end, you need to output and SQL instruction string that would retrieve information on an sqlite instance
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


visualization_agent_prompt_template = PromptTemplate(
    prompt="""
Your task is to create a Python code that visualises a table as give in the instructions.
The code needs to be written in python between the tags ```python ... ```
The goal of the code is generating and image in matplotlib that explains the data.
This image must be saved in a file named {filename}.
Just save the file, don't show() it.

If the code runs without errors, just write <task-completed/> at the beginning of your answer.
"""
)
