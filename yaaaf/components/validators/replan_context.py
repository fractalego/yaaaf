"""Pydantic models for replanning context and failure tracking."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FailureType(str, Enum):
    """Types of step failures that can trigger replanning."""
    TESTS_FAILED = "tests_failed"  # Tests ran but some failed
    INFRASTRUCTURE_ERROR = "infrastructure_error"  # Tool/env issue
    TIMEOUT = "timeout"  # Step exceeded time limit
    VALIDATION_ERROR = "validation_error"  # Output artifact invalid


class ArtifactMetadata(BaseModel):
    """Metadata about an artifact without its full contents."""
    id: str = Field(description="Unique artifact identifier")
    type: str = Field(description="Artifact type (text, code_edit, bash_output, etc.)")
    name: str = Field(description="Name of the step that produced this artifact")
    description: str = Field(description="Human-readable description of the artifact")
    size_bytes: int = Field(description="Size of artifact content in bytes")
    agent_name: str = Field(description="Agent that produced this artifact")
    files_changed: Optional[List[str]] = Field(
        default=None,
        description="For code_edit artifacts, list of files modified"
    )


class FailureDetails(BaseModel):
    """Detailed information about why a step failed."""
    exit_code: Optional[int] = Field(
        default=None,
        description="Exit code for bash/execution steps"
    )
    raw_output: str = Field(description="Full unprocessed output from the failed step")
    error_message: Optional[str] = Field(
        default=None,
        description="Extracted error message if available"
    )
    additional_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra context specific to the failure type"
    )


class ReplanContext(BaseModel):
    """Context provided to the planner when creating a continuation plan.

    This context allows the planner to create a new plan that builds on
    artifacts from a previous plan execution that failed.
    """

    # What we're trying to achieve
    original_goal: str = Field(description="The user's original request/goal")
    iteration: int = Field(
        description="Which replan attempt this is (1 = first replan, 2 = second, etc.)",
        ge=1
    )

    # What already happened
    prior_plan_id: str = Field(description="ID of the plan that failed")
    completed_artifacts: List[ArtifactMetadata] = Field(
        description="Artifacts successfully produced before failure"
    )
    failed_artifact: ArtifactMetadata = Field(
        description="The artifact from the step that failed"
    )

    # Why it failed
    failure_type: FailureType = Field(description="Category of failure")
    failure_summary: str = Field(
        description="Human-readable one-line summary created by validator"
    )
    failure_details: FailureDetails = Field(
        description="Structured details about the failure"
    )
