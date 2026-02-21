"""Structured exceptions for the YAAAF framework.

This module provides Pydantic-based exception models for clear error handling
and proper categorization of failure modes.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel


class FailureMode(str, Enum):
    """Enumeration of possible failure modes in plan execution."""

    VALIDATION_FAILED = "validation_failed"
    USER_DECISION_REQUIRED = "user_decision_required"
    PLAN_EXECUTION_FAILED = "plan_execution_failed"
    CONDITION_FAILED = "condition_failed"
    UNEXPECTED_ERROR = "unexpected_error"


class PlanExecutionFailure(BaseModel):
    """Structured information about a plan execution failure."""

    mode: FailureMode
    message: str
    attempts: int
    last_error: str
    asset_name: Optional[str] = None
    partial_results: Optional[Dict[str, Any]] = None

    def get_user_message(self) -> str:
        """Generate a user-friendly error message based on failure mode."""
        mode_prefixes = {
            FailureMode.VALIDATION_FAILED: "❌ **Validation Failed**",
            FailureMode.USER_DECISION_REQUIRED: "⚠️ **User Decision Required**",
            FailureMode.PLAN_EXECUTION_FAILED: "❌ **Plan Execution Failed**",
            FailureMode.CONDITION_FAILED: "❌ **Condition Failed**",
            FailureMode.UNEXPECTED_ERROR: "❌ **System Error**",
        }
        prefix = mode_prefixes.get(self.mode, "❌ **Error**")

        if self.asset_name:
            return f"{prefix}: {self.message} (asset: {self.asset_name})\n\n<taskcompleted/>"
        return f"{prefix}: {self.message}\n\n<taskcompleted/>"


class PlanExecutionError(Exception):
    """Exception raised when plan execution fails.

    This exception carries structured failure information via a PlanExecutionFailure
    model, allowing for proper error categorization and user-friendly messaging.
    """

    def __init__(self, failure: PlanExecutionFailure):
        self.failure = failure
        super().__init__(failure.message)

    @classmethod
    def validation_failed(
        cls,
        attempts: int,
        last_error: str,
        asset_name: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> "PlanExecutionError":
        """Create a validation failure exception."""
        return cls(PlanExecutionFailure(
            mode=FailureMode.VALIDATION_FAILED,
            message=f"Validation failed after {attempts} attempts. {last_error}",
            attempts=attempts,
            last_error=last_error,
            asset_name=asset_name,
            partial_results=partial_results,
        ))

    @classmethod
    def user_decision_required(
        cls,
        attempts: int,
        last_error: str,
        asset_name: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> "PlanExecutionError":
        """Create a user decision required exception."""
        return cls(PlanExecutionFailure(
            mode=FailureMode.USER_DECISION_REQUIRED,
            message=f"User decision required after {attempts} attempts. {last_error}",
            attempts=attempts,
            last_error=last_error,
            asset_name=asset_name,
            partial_results=partial_results,
        ))

    @classmethod
    def plan_failed(
        cls,
        attempts: int,
        last_error: str,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> "PlanExecutionError":
        """Create a general plan execution failure exception."""
        return cls(PlanExecutionFailure(
            mode=FailureMode.PLAN_EXECUTION_FAILED,
            message=f"Plan execution failed after {attempts} attempts. {last_error}",
            attempts=attempts,
            last_error=last_error,
            partial_results=partial_results,
        ))

    @classmethod
    def condition_failed(
        cls,
        attempts: int,
        last_error: str,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> "PlanExecutionError":
        """Create a condition failure exception."""
        return cls(PlanExecutionFailure(
            mode=FailureMode.CONDITION_FAILED,
            message=f"Condition check failed after {attempts} attempts. {last_error}",
            attempts=attempts,
            last_error=last_error,
            partial_results=partial_results,
        ))

    @classmethod
    def unexpected_error(
        cls,
        attempts: int,
        last_error: str,
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> "PlanExecutionError":
        """Create an unexpected error exception."""
        return cls(PlanExecutionFailure(
            mode=FailureMode.UNEXPECTED_ERROR,
            message=f"Unexpected error after {attempts} attempts. {last_error}",
            attempts=attempts,
            last_error=last_error,
            partial_results=partial_results,
        ))
