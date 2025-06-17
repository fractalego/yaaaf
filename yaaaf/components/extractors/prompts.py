from yaaaf.components.data_types import PromptTemplate

goal_extractor_prompt = PromptTemplate(
    prompt="""
You are a goal extractor. Your task is to extract the goal from the given message.
The goal is a specific task that the user wants to accomplish.
The goal should be a single sentence that summarizes the user's latest intention.

Please analyze the following message exchange between the user and the assistant:
<messages>
{messages}
</messages>
"""
)
