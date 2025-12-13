"""Agent taxonomy definitions for all agents in the framework."""

from yaaaf.components.data_types import AgentTaxonomy, DataFlow, InteractionMode, OutputPermanence


# Define taxonomy for each agent type
AGENT_TAXONOMIES = {
    "AnswererAgent": AgentTaxonomy(
        data_flow=DataFlow.SYNTHESIZER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Combines multiple artifacts into comprehensive answers"
    ),
    
    "BashAgent": AgentTaxonomy(
        data_flow=DataFlow.GENERATOR,
        interaction_mode=InteractionMode.INTERACTIVE,
        output_permanence=OutputPermanence.PERSISTENT,
        description="Creates effects through filesystem operations"
    ),
    
    "BraveSearchAgent": AgentTaxonomy(
        data_flow=DataFlow.EXTRACTOR,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Pulls data from Brave web search API"
    ),
    
    "DuckDuckGoSearchAgent": AgentTaxonomy(
        data_flow=DataFlow.EXTRACTOR,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Pulls data from DuckDuckGo search API"
    ),
    
    "DocumentRetrieverAgent": AgentTaxonomy(
        data_flow=DataFlow.EXTRACTOR,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Pulls relevant chunks from document collections"
    ),
    
    "MleAgent": AgentTaxonomy(
        data_flow=DataFlow.TRANSFORMER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.PERSISTENT,
        description="Analyzes data to extract patterns and create ML models"
    ),
    
    "NumericalSequencesAgent": AgentTaxonomy(
        data_flow=DataFlow.TRANSFORMER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Reshapes unstructured data into structured tables"
    ),
    
    "OrchestratorAgent": AgentTaxonomy(
        data_flow=DataFlow.SYNTHESIZER,
        interaction_mode=InteractionMode.COLLABORATIVE,
        output_permanence=OutputPermanence.STATEFUL,
        description="Combines outputs from multiple agents and maintains context"
    ),
    
    "ReviewerAgent": AgentTaxonomy(
        data_flow=DataFlow.TRANSFORMER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Analyzes and validates information"
    ),
    
    "SqlAgent": AgentTaxonomy(
        data_flow=DataFlow.EXTRACTOR,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Pulls data from databases via SQL queries"
    ),
    
    "ToolAgent": AgentTaxonomy(
        data_flow=DataFlow.TRANSFORMER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Converts instructions into MCP tool calls"
    ),
    
    "UrlAgent": AgentTaxonomy(
        data_flow=DataFlow.EXTRACTOR,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Fetches content from specific URLs"
    ),
    
    "UrlRetrieverAgent": AgentTaxonomy(
        data_flow=DataFlow.SYNTHESIZER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Combines URL content into structured summaries"
    ),
    
    "UserInputAgent": AgentTaxonomy(
        data_flow=DataFlow.EXTRACTOR,
        interaction_mode=InteractionMode.INTERACTIVE,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Gathers information from users"
    ),
    
    "VisualizationAgent": AgentTaxonomy(
        data_flow=DataFlow.GENERATOR,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.PERSISTENT,
        description="Creates visual artifacts from data"
    ),
    
    "PlannerAgent": AgentTaxonomy(
        data_flow=DataFlow.SYNTHESIZER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Creates execution DAGs showing optimal data flow paths"
    ),

    "ValidationAgent": AgentTaxonomy(
        data_flow=DataFlow.TRANSFORMER,
        interaction_mode=InteractionMode.AUTONOMOUS,
        output_permanence=OutputPermanence.EPHEMERAL,
        description="Validates artifacts against user goals and step descriptions"
    ),
}


def get_agent_taxonomy(agent_class_name: str) -> AgentTaxonomy:
    """Get the taxonomy for a specific agent class.
    
    Args:
        agent_class_name: The class name of the agent (e.g., "SqlAgent")
        
    Returns:
        The AgentTaxonomy for the agent
        
    Raises:
        KeyError: If the agent class is not found in the taxonomy definitions
    """
    if agent_class_name not in AGENT_TAXONOMIES:
        raise KeyError(f"No taxonomy defined for agent: {agent_class_name}")
    return AGENT_TAXONOMIES[agent_class_name]


def get_all_agents_with_taxonomy():
    """Get all available agents with their taxonomy information.
    
    Returns:
        Dict[str, AgentTaxonomy]: Dictionary mapping agent class names to their taxonomies
    """
    return AGENT_TAXONOMIES.copy()