"""Configuration models for loop constructs in workflows."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExitConditionType(str, Enum):
    """Types of loop exit conditions."""
    ALL_VALID = "all_valid"  # All assets in loop body must pass validation
    ANY_VALID = "any_valid"  # At least one specified asset must pass validation
    CUSTOM = "custom"  # Custom condition expression


class LoopExitCondition(BaseModel):
    """Configuration for when a loop should exit."""
    type: ExitConditionType = Field(description="Type of exit condition")
    assets: Optional[List[str]] = Field(
        default=None,
        description="For any_valid: which assets to check. For all_valid: optional filter"
    )
    condition: Optional[str] = Field(
        default=None,
        description="For custom: condition expression to evaluate"
    )


class LoopConfig(BaseModel):
    """Configuration for a loop node in a workflow.

    A loop node executes a sub-workflow (loop_body) repeatedly until
    an exit condition is met or max_iterations is reached.
    """

    type: str = Field(default="loop", description="Must be 'loop'")
    description: str = Field(description="Human-readable description of the loop")
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of loop iterations (safety limit)"
    )
    exit_condition: LoopExitCondition = Field(
        description="Condition that determines when the loop exits"
    )
    loop_body: Dict[str, Any] = Field(
        description="Sub-workflow to execute each iteration (must have 'assets' key)"
    )
    loop_output: str = Field(
        description="Name of the asset in loop_body whose result should be returned"
    )
    inputs: Optional[List[str]] = Field(
        default=None,
        description="Optional inputs from outside the loop"
    )


class LoopIterationResult(BaseModel):
    """Result from a single loop iteration."""
    iteration: int = Field(description="Iteration number (0-based)")
    assets: Dict[str, str] = Field(
        description="Asset results from this iteration (asset_name -> result_string)"
    )
    all_valid: bool = Field(
        description="Whether all assets passed validation"
    )
    validation_results: Dict[str, bool] = Field(
        description="Validation result for each asset (asset_name -> is_valid)"
    )
    exit_condition_met: bool = Field(
        description="Whether the exit condition was satisfied"
    )
