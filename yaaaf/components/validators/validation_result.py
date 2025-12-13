"""Validation result model."""

from dataclasses import dataclass
from typing import Optional


# Confidence thresholds
REPLAN_THRESHOLD = 0.5  # Below this: attempt replan
ASK_USER_THRESHOLD = 0.3  # Below this: ask user what to do


@dataclass
class ValidationResult:
    """Result of artifact validation.

    Attributes:
        is_valid: Whether the artifact meets expectations
        confidence: Confidence score from 0.0 to 1.0
            - 1.0: Perfect match
            - 0.5-1.0: Acceptable, minor issues
            - 0.3-0.5: Problematic, should replan
            - 0.0-0.3: Completely wrong, ask user
        reason: Explanation of why it passed/failed
        should_ask_user: True if confidence is too low to auto-replan
        suggested_fix: What to do differently if replanning
        asset_name: Name of the asset that was validated
    """

    is_valid: bool
    confidence: float
    reason: str
    should_ask_user: bool = False
    suggested_fix: Optional[str] = None
    asset_name: Optional[str] = None

    def __post_init__(self):
        """Set should_ask_user based on confidence if not explicitly set."""
        if self.confidence < ASK_USER_THRESHOLD and not self.is_valid:
            self.should_ask_user = True

    @property
    def should_replan(self) -> bool:
        """Whether the system should attempt replanning."""
        return (
            not self.is_valid
            and not self.should_ask_user
            and self.confidence < REPLAN_THRESHOLD
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "reason": self.reason,
            "should_ask_user": self.should_ask_user,
            "suggested_fix": self.suggested_fix,
            "asset_name": self.asset_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationResult":
        """Create from dictionary."""
        return cls(
            is_valid=data.get("is_valid", False),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", "Unknown"),
            should_ask_user=data.get("should_ask_user", False),
            suggested_fix=data.get("suggested_fix"),
            asset_name=data.get("asset_name"),
        )

    @classmethod
    def valid(cls, reason: str = "Artifact matches expectations", asset_name: str = None) -> "ValidationResult":
        """Create a valid result."""
        return cls(
            is_valid=True,
            confidence=1.0,
            reason=reason,
            should_ask_user=False,
            asset_name=asset_name,
        )

    @classmethod
    def invalid_replan(
        cls, reason: str, suggested_fix: str, confidence: float = 0.4, asset_name: str = None
    ) -> "ValidationResult":
        """Create an invalid result that should trigger replanning."""
        return cls(
            is_valid=False,
            confidence=confidence,
            reason=reason,
            should_ask_user=False,
            suggested_fix=suggested_fix,
            asset_name=asset_name,
        )

    @classmethod
    def invalid_ask_user(cls, reason: str, asset_name: str = None) -> "ValidationResult":
        """Create an invalid result that requires user input."""
        return cls(
            is_valid=False,
            confidence=0.1,
            reason=reason,
            should_ask_user=True,
            suggested_fix=None,
            asset_name=asset_name,
        )
