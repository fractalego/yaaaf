from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Union


class ArtifactType(Enum):
    """Types of artifacts that can be passed between agents."""
    TABLE = "TABLE"  # DataFrame/tabular data
    TEXT = "TEXT"  # Text content, documents, strings
    IMAGE = "IMAGE"  # Visual outputs (PNG, JPG, etc.)
    MODEL = "MODEL"  # Trained ML models
    JSON = "JSON"  # Structured JSON data
    PLAN = "PLAN"  # Execution plans in YAML format
    ANY = "ANY"  # Can handle any artifact type


@dataclass
class AgentArtifactSpec:
    """Specification of artifact types an agent accepts and produces.
    
    Attributes:
        accepts: List of artifact types this agent can consume as input
        produces: List of artifact types this agent can generate as output
    """
    accepts: List[ArtifactType]
    produces: List[ArtifactType]
    
    @classmethod
    def source_agent(cls, output_type: ArtifactType) -> "AgentArtifactSpec":
        """Create spec for a source agent that produces artifacts without input."""
        return cls(accepts=[], produces=[output_type])
    
    @classmethod
    def sink_agent(cls, input_type: Union[ArtifactType, List[ArtifactType]]) -> "AgentArtifactSpec":
        """Create spec for a sink agent that consumes artifacts."""
        if isinstance(input_type, ArtifactType):
            input_types = [input_type]
        else:
            input_types = input_type
        return cls(accepts=input_types, produces=[])
    
    @classmethod
    def transformer_agent(
        cls, 
        input_type: Union[ArtifactType, List[ArtifactType]], 
        output_type: Union[ArtifactType, List[ArtifactType]]
    ) -> "AgentArtifactSpec":
        """Create spec for a transformer agent."""
        if isinstance(input_type, ArtifactType):
            input_types = [input_type]
        else:
            input_types = input_type
            
        if isinstance(output_type, ArtifactType):
            output_types = [output_type]
        else:
            output_types = output_type
            
        return cls(accepts=input_types, produces=output_types)
    
    def can_accept(self, artifact_type: ArtifactType) -> bool:
        """Check if this agent can accept a given artifact type."""
        return ArtifactType.ANY in self.accepts or artifact_type in self.accepts
    
    def can_produce(self, artifact_type: ArtifactType) -> bool:
        """Check if this agent can produce a given artifact type."""
        return ArtifactType.ANY in self.produces or artifact_type in self.produces
    
    def can_connect_to(self, other: "AgentArtifactSpec") -> List[ArtifactType]:
        """Check which artifact types can flow from this agent to another.
        
        Returns list of compatible artifact types that can be passed.
        """
        compatible = []
        for produced in self.produces:
            if other.can_accept(produced):
                compatible.append(produced)
        return compatible


# Predefined artifact specifications for all agents
AGENT_ARTIFACT_SPECS = {
    # Source agents (extractors)
    "SqlAgent": AgentArtifactSpec.source_agent(ArtifactType.TABLE),
    "DocumentRetrieverAgent": AgentArtifactSpec.source_agent(ArtifactType.TEXT),
    "BraveSearchAgent": AgentArtifactSpec.source_agent(ArtifactType.TABLE),  # Actually returns TABLE
    "DuckDuckGoSearchAgent": AgentArtifactSpec.source_agent(ArtifactType.TABLE),  # Actually returns TABLE
    "UrlAgent": AgentArtifactSpec.source_agent(ArtifactType.TEXT),
    "UserInputAgent": AgentArtifactSpec.source_agent(ArtifactType.TEXT),
    
    # Transformer agents
    "ReviewerAgent": AgentArtifactSpec.transformer_agent(
        ArtifactType.TABLE, ArtifactType.TABLE
    ),
    "NumericalSequencesAgent": AgentArtifactSpec.transformer_agent(
        [ArtifactType.TEXT, ArtifactType.TABLE], ArtifactType.TABLE
    ),
    "MleAgent": AgentArtifactSpec.transformer_agent(
        ArtifactType.TABLE, ArtifactType.MODEL
    ),
    "ToolAgent": AgentArtifactSpec.transformer_agent(
        ArtifactType.TEXT, [ArtifactType.JSON, ArtifactType.TEXT]
    ),
    
    # Synthesizer agents
    "AnswererAgent": AgentArtifactSpec.transformer_agent(
        [ArtifactType.TABLE, ArtifactType.TEXT, ArtifactType.MODEL], 
        ArtifactType.TABLE
    ),
    "UrlRetrieverAgent": AgentArtifactSpec.transformer_agent(
        ArtifactType.TEXT, ArtifactType.TABLE
    ),
    "OrchestratorAgent": AgentArtifactSpec.transformer_agent(
        [ArtifactType.ANY], [ArtifactType.ANY]
    ),
    
    # Sink agents (generators)
    "VisualizationAgent": AgentArtifactSpec(
        accepts=[ArtifactType.TABLE], 
        produces=[ArtifactType.IMAGE]
    ),
    "BashAgent": AgentArtifactSpec.transformer_agent(
        ArtifactType.TEXT, ArtifactType.TEXT
    ),
    "PlannerAgent": AgentArtifactSpec.transformer_agent(
        ArtifactType.TEXT, ArtifactType.PLAN
    ),
}


def get_agent_artifact_spec(agent_class_name: str) -> AgentArtifactSpec:
    """Get the artifact specification for a specific agent class.
    
    Args:
        agent_class_name: The class name of the agent (e.g., "SqlAgent")
        
    Returns:
        The AgentArtifactSpec for the agent
        
    Raises:
        KeyError: If the agent class is not found in the specifications
    """
    if agent_class_name not in AGENT_ARTIFACT_SPECS:
        raise KeyError(f"No artifact specification defined for agent: {agent_class_name}")
    return AGENT_ARTIFACT_SPECS[agent_class_name]