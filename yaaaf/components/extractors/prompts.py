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

enhanced_goal_extractor_prompt = PromptTemplate(
    prompt="""
You are a goal extractor. Your task is to extract the goal and identify the required final artifact type.

Please analyze the following message exchange:
<messages>
{messages}
</messages>

Extract:
1. The user's goal (single sentence)
2. The type of final artifact needed:
   - TABLE: If user wants data, analysis results, or structured information
   - IMAGE: If user wants visualization, chart, or graph  
   - TEXT: If user wants a report, summary, or explanation
   - MODEL: If user wants a trained ML model
   - TODO_LIST: If user wants a task list or action items

Output in this exact format:
Goal: [single sentence goal]
Artifact Type: [TABLE|IMAGE|TEXT|MODEL|TODO_LIST]
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
chunk_extractor_prompt = PromptTemplate(
    prompt="""
You are a chunk extractor. Your task is to identify and extract relevant text chunks from a document that are related to a specific query.

Given the following text, extract the most relevant chunks of text that directly answer or relate to the user query.

Text:
{text}

Instructions:
1. Identify text chunks that are directly relevant to the query
2. Each chunk should be a coherent piece of text (sentences or paragraphs)
3. Extract the exact text verbatim from the input - do not paraphrase or modify
4. Include position information (page number, section, or paragraph number if available)
5. Return results as a JSON array with the format:
   [{{\"relevant_chunk_text\": \"exact text from input\", \"position_in_document\": \"page/section identifier\"}}]

Please be flexible in finding relevant information, as it may not always be in a single contiguous section.
The relevant information may be spread across different parts of the text.
Use the largest chunks possible that still maintain coherence.

The page/section identifier can be a page number, section title, or paragraph number specifically related to the text chunk (these coordinates should help locate the chunk in the original document).

If no relevant chunks are found, return an empty array [].
Only return the JSON array, no other text.
"""
)
