from enum import Enum
from dataclasses import dataclass
from typing import Optional


class DataFlow(Enum):
    """Defines how an agent interacts with data."""
    EXTRACTOR = "extractor"  # Pulls data from sources
    TRANSFORMER = "transformer"  # Reshapes or analyzes data
    SYNTHESIZER = "synthesizer"  # Combines multiple inputs
    GENERATOR = "generator"  # Creates new artifacts


class InteractionMode(Enum):
    """Defines how an agent interacts with users and other agents."""
    AUTONOMOUS = "autonomous"  # Works independently
    INTERACTIVE = "interactive"  # Requires user input
    COLLABORATIVE = "collaborative"  # Works with other agents


class OutputPermanence(Enum):
    """Defines the persistence characteristics of agent outputs."""
    EPHEMERAL = "ephemeral"  # Results for immediate use
    PERSISTENT = "persistent"  # Creates lasting artifacts
    STATEFUL = "stateful"  # Maintains context across calls


@dataclass
class AgentTaxonomy:
    """Taxonomy classification for an agent.
    
    Attributes:
        data_flow: How the agent processes data (extractor, transformer, etc.)
        interaction_mode: How the agent interacts (autonomous, interactive, etc.)
        output_permanence: The persistence of agent outputs
        description: Optional human-readable description of the agent's role
    """
    data_flow: DataFlow
    interaction_mode: InteractionMode
    output_permanence: OutputPermanence
    description: Optional[str] = None
    
    def __str__(self) -> str:
        """Return a human-readable string representation."""
        desc = f"AgentTaxonomy({self.data_flow.value}, {self.interaction_mode.value}, {self.output_permanence.value})"
        if self.description:
            desc += f" - {self.description}"
        return desc
    
    @classmethod
    def for_source_agent(cls) -> "AgentTaxonomy":
        """Create taxonomy for a typical source agent."""
        return cls(
            data_flow=DataFlow.EXTRACTOR,
            interaction_mode=InteractionMode.AUTONOMOUS,
            output_permanence=OutputPermanence.EPHEMERAL,
            description="Source agent that extracts data"
        )
    
    @classmethod
    def for_processor_agent(cls) -> "AgentTaxonomy":
        """Create taxonomy for a typical processor agent."""
        return cls(
            data_flow=DataFlow.TRANSFORMER,
            interaction_mode=InteractionMode.AUTONOMOUS,
            output_permanence=OutputPermanence.EPHEMERAL,
            description="Processor agent that transforms data"
        )
    
    @classmethod
    def for_sink_agent(cls) -> "AgentTaxonomy":
        """Create taxonomy for a typical sink agent."""
        return cls(
            data_flow=DataFlow.GENERATOR,
            interaction_mode=InteractionMode.AUTONOMOUS,
            output_permanence=OutputPermanence.PERSISTENT,
            description="Sink agent that produces final outputs"
        )