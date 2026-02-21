"""Utilities for analyzing step failures and detecting failure types."""

import re
import logging
from typing import Tuple, Optional
from yaaaf.components.validators.replan_context import FailureType, FailureDetails

_logger = logging.getLogger(__name__)


def analyze_bash_output(output: str, exit_code: Optional[int] = None) -> Tuple[FailureType, FailureDetails]:
    """Analyze bash/test output to determine failure type and extract details.

    Args:
        output: The bash command output
        exit_code: Exit code if available

    Returns:
        Tuple of (FailureType, FailureDetails)
    """
    # Extract exit code from output if not provided
    if exit_code is None:
        # Look for exit code patterns in output
        exit_code_match = re.search(r"exit code[:\s]+(\d+)", output, re.IGNORECASE)
        if exit_code_match:
            exit_code = int(exit_code_match.group(1))

    # Detect timeout
    if "timeout" in output.lower() or "timed out" in output.lower():
        return (
            FailureType.TIMEOUT,
            FailureDetails(
                exit_code=exit_code,
                raw_output=output,
                error_message="Command execution timed out",
            ),
        )

    # Detect infrastructure errors (environment, dependencies, etc.)
    infra_patterns = [
        r"command not found",
        r"no such file or directory",
        r"permission denied",
        r"cannot execute",
        r"modulenotfounderror",
        r"importerror",
        r"segmentation fault",
        r"killed",
        r"syntaxerror",  # Python syntax errors
        r"indentationerror",  # Python indentation errors
        r"unexpectedindent",  # Alternative IndentationError pattern
        r"invalid syntax",  # Generic syntax errors
    ]
    for pattern in infra_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            # Extract error line
            error_match = re.search(pattern, output, re.IGNORECASE)
            error_message = error_match.group(0) if error_match else "Infrastructure error detected"
            return (
                FailureType.INFRASTRUCTURE_ERROR,
                FailureDetails(
                    exit_code=exit_code,
                    raw_output=output,
                    error_message=error_message,
                ),
            )

    # Detect test failures by exit code (pytest)
    # Exit code 1 = tests failed, 4 = usage error/no tests found, 5 = no tests collected
    if exit_code in (1, 4, 5):
        # Check if this is actually a test run (has pytest/test markers)
        is_test_run = bool(
            re.search(r"pytest|test.*\.py|test session|collected \d+ item", output, re.IGNORECASE)
        )

        if is_test_run:
            error_message = _extract_test_failure_summary(output)

            # For exit code 4 or 5, provide more specific message
            if exit_code in (4, 5):
                if "not found:" in output or "no match" in output:
                    error_message = "No tests found - test path may be incorrect"
                elif "collected 0 items" in output:
                    error_message = "No tests collected - check test selection"

            return (
                FailureType.TESTS_FAILED,
                FailureDetails(
                    exit_code=exit_code,
                    raw_output=output,
                    error_message=error_message,
                ),
            )

    # Detect test failures by output patterns (pytest, unittest, jest, etc.)
    test_patterns = [
        r"(\d+) failed",  # pytest
        r"FAILED.*test_",  # pytest test names
        r"FAIL:",  # unittest
        r"AssertionError",  # generic
        r"Tests run: \d+, Failures: (\d+)",  # Java/JUnit style
        r"✗",  # jest/mocha
    ]

    for pattern in test_patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            # Try to extract failure count
            failure_count = None
            if match.groups():
                try:
                    failure_count = int(match.group(1))
                except (ValueError, IndexError):
                    pass

            # Extract a summary error message
            error_message = _extract_test_failure_summary(output)

            additional_context = {}
            if failure_count is not None:
                additional_context["failure_count"] = failure_count

            return (
                FailureType.TESTS_FAILED,
                FailureDetails(
                    exit_code=exit_code or 1,  # Tests typically exit with 1
                    raw_output=output,
                    error_message=error_message,
                    additional_context=additional_context,
                ),
            )

    # Exit code 0 means success (shouldn't be here, but handle it)
    if exit_code == 0:
        _logger.warning("analyze_bash_output called on successful execution (exit_code=0)")
        return (
            FailureType.VALIDATION_ERROR,
            FailureDetails(
                exit_code=0,
                raw_output=output,
                error_message="Step succeeded but was flagged for analysis",
            ),
        )

    # Unknown error type - default to validation error
    return (
        FailureType.VALIDATION_ERROR,
        FailureDetails(
            exit_code=exit_code,
            raw_output=output,
            error_message="Output did not match expected format or requirements",
        ),
    )


def _extract_test_failure_summary(output: str) -> str:
    """Extract a concise summary of test failures from output.

    Args:
        output: Test output

    Returns:
        Summary string
    """
    # Look for common test failure patterns
    lines = output.split("\n")

    # Count failed tests
    failed_count = 0
    passed_count = 0
    for line in lines:
        if re.search(r"FAILED|FAIL:", line, re.IGNORECASE):
            failed_count += 1
        if re.search(r"PASSED|PASS:", line, re.IGNORECASE):
            passed_count += 1

    # Look for summary lines
    summary_patterns = [
        r"(\d+) failed.*(\d+) passed",
        r"FAILED.*=\s*(\d+)",
        r"Failures: (\d+)",
    ]

    for pattern in summary_patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return match.group(0)

    # Fallback: build summary from counts
    if failed_count > 0:
        summary = f"{failed_count} test(s) failed"
        if passed_count > 0:
            summary += f", {passed_count} passed"
        return summary

    # Last resort: generic message
    return "Tests failed (see output for details)"


def create_failure_summary(failure_type: FailureType, failure_details: FailureDetails) -> str:
    """Create a human-readable one-line summary of a failure.

    Args:
        failure_type: Type of failure
        failure_details: Detailed failure information

    Returns:
        One-line summary string
    """
    if failure_type == FailureType.TESTS_FAILED:
        failure_count = failure_details.additional_context.get("failure_count")
        if failure_count:
            return f"{failure_count} test(s) failed: {failure_details.error_message}"
        return f"Tests failed: {failure_details.error_message}"

    elif failure_type == FailureType.INFRASTRUCTURE_ERROR:
        return f"Infrastructure error: {failure_details.error_message}"

    elif failure_type == FailureType.TIMEOUT:
        return "Execution timed out"

    elif failure_type == FailureType.VALIDATION_ERROR:
        return f"Validation failed: {failure_details.error_message}"

    return f"Step failed: {failure_details.error_message}"
