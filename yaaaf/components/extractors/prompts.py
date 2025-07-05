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

summary_extractor_prompt = PromptTemplate(
    prompt="""
Based on the following conversation and results, create a comprehensive summary in markdown format with the following sections (if applicable):

## Main Finding
[Summarize the key findings, results, or answers discovered]

## Reasoning
[Explain the logical steps and reasoning that led to these findings]

## Links
[Include any relevant URLs, references, or sources mentioned]

## Visual Content
[Describe any charts, graphs, images, or tables that were generated]

Conversation content:
{conversation_content}

Please provide a concise but comprehensive summary that captures the essence of the conversation and its outcomes.
"""
)
