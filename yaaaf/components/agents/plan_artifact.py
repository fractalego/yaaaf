from uuid import uuid4
from typing import Dict, Any
from yaaaf.components.agents.artefacts import Artefact


class PlanArtifact(Artefact):
    """Execution plan stored as an artifact."""

    def __init__(self, plan_yaml: str, goal: str, target_artifact_type: str):
        super().__init__(
            id=f"plan_{uuid4().hex[:8]}",
            type=Artefact.Types.PLAN,
            code=plan_yaml,
            description=f"Execution plan for: {goal}",
            summary=f"Plan to produce {target_artifact_type} for goal: {goal}",
        )
        self.goal = goal
        self.target_artifact_type = target_artifact_type

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "type": self.type,
            "code": self.code,
            "description": self.description,
            "summary": self.summary,
            "goal": self.goal,
            "target_artifact_type": self.target_artifact_type,
        }
