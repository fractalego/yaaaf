import base64
import logging
import os
import tempfile
from io import StringIO
from typing import Any, Tuple, Optional, Dict, List

from yaaaf.components.agents.artefacts import Artefact, ArtefactStorage
from yaaaf.components.agents.tokens_utils import get_first_text_between_tags
from yaaaf.components.agents.artefact_utils import get_artefacts_from_utterance_content
from yaaaf.components.data_types import Messages, Note

from .base import ToolExecutor

_logger = logging.getLogger(__name__)


class PythonExecutor(ToolExecutor):
    """Executor for Python code execution."""

    def __init__(self, output_type: str = "text", max_image_size_mb: float = 10.0):
        """Initialize Python executor.

        Args:
            output_type: Expected output type - "text" or "image"
            max_image_size_mb: Maximum allowed image size in MB
        """
        self._output_type = output_type
        self._max_image_size_mb = max_image_size_mb
        self._storage = ArtefactStorage()
        self._temp_image_path = None

    async def prepare_context(
        self, messages: Messages, notes: Optional[List[Note]] = None
    ) -> Dict[str, Any]:
        """Prepare execution context by extracting artifacts.

        Args:
            messages: The conversation messages
            notes: Optional notes containing artifacts

        Returns:
            Dictionary with artifacts and global variables
        """
        # Extract artifacts from the last user message
        last_utterance = messages.utterances[-1]
        artefact_list = get_artefacts_from_utterance_content(last_utterance)

        # Set up global variables for execution
        global_variables = self._setup_globals(artefact_list)

        return {
            "artifacts": artefact_list,
            "globals": global_variables,
            "last_utterance": last_utterance,
        }

    def extract_instruction(self, response: str) -> Optional[str]:
        """Extract Python code from response.

        Args:
            response: The agent's response

        Returns:
            The Python code or None
        """
        return get_first_text_between_tags(response, "python", "python")

    async def execute_operation(
        self, instruction: str, context: Dict[str, Any]
    ) -> Tuple[Any, Optional[str]]:
        """Execute Python code.

        Args:
            instruction: The Python code to execute
            context: The prepared context with globals

        Returns:
            Tuple of (result, error message)
        """
        globals_dict = context["globals"]

        try:
            # Execute the code
            exec(instruction, globals_dict)

            if self._output_type == "image":
                # Check if image was saved
                if self._temp_image_path and os.path.exists(self._temp_image_path):
                    # Read and encode the image
                    with open(self._temp_image_path, "rb") as f:
                        image_data = f.read()

                    # Check size
                    size_mb = len(image_data) / (1024 * 1024)
                    if size_mb > self._max_image_size_mb:
                        return (
                            None,
                            f"Generated image is too large ({size_mb:.1f}MB > {self._max_image_size_mb}MB)",
                        )

                    # Encode to base64
                    image_base64 = base64.b64encode(image_data).decode("utf-8")

                    # Clean up temp file
                    os.remove(self._temp_image_path)
                    self._temp_image_path = None

                    return image_base64, None
                else:
                    return (
                        None,
                        "No image was generated. Make sure your code saves an image using plt.savefig().",
                    )
            else:
                # Return captured stdout
                output = globals_dict["_stdout"].getvalue()
                if output:
                    return output, None
                else:
                    return "Code executed successfully (no output)", None

        except Exception as e:
            error_msg = f"Python execution error: {str(e)}"
            _logger.error(error_msg)
            return None, error_msg
        finally:
            # Clean up temp file if it exists
            if self._temp_image_path and os.path.exists(self._temp_image_path):
                os.remove(self._temp_image_path)
                self._temp_image_path = None

    def validate_result(self, result: Any) -> bool:
        """Validate execution result.

        Args:
            result: The execution result

        Returns:
            True if valid result
        """
        if result is None:
            return False

        if self._output_type == "image":
            # For images, result should be base64 string
            return isinstance(result, str) and len(result) > 0
        else:
            # For text, any non-None result is valid
            return True

    def transform_to_artifact(
        self, result: Any, instruction: str, artifact_id: str
    ) -> Artefact:
        """Transform execution result to appropriate artifact.

        Args:
            result: The execution result
            instruction: The Python code
            artifact_id: The ID for the artifact

        Returns:
            An Artefact of appropriate type
        """
        if self._output_type == "image":
            return Artefact(
                type=Artefact.Types.IMAGE,
                description="Generated visualization",
                code=instruction,
                data=result,  # base64 encoded image
                id=artifact_id,
            )
        else:
            return Artefact(
                type=Artefact.Types.CODE,
                description="Code execution output",
                code=instruction,
                data=result,  # stdout output
                id=artifact_id,
            )

    def _setup_globals(self, artifacts: List[Artefact]) -> Dict[str, Any]:
        """Set up global variables for code execution.

        Args:
            artifacts: List of artifacts to make available

        Returns:
            Dictionary of global variables
        """
        # Redirect stdout
        stdout_buffer = StringIO()

        # Basic imports
        globals_dict = {
            "_stdout": stdout_buffer,
            "print": lambda *args, **kwargs: print(*args, file=stdout_buffer, **kwargs),
            "__name__": "__main__",
        }

        # Add common libraries
        try:
            import numpy as np
            import pandas as pd
            import matplotlib

            matplotlib.use("Agg")  # Non-interactive backend
            import matplotlib.pyplot as plt

            globals_dict.update(
                {"np": np, "pd": pd, "plt": plt, "matplotlib": matplotlib}
            )
        except ImportError as e:
            _logger.warning(f"Could not import library: {e}")

        # Add artifacts as DataFrames
        for artifact in artifacts:
            if artifact.type == Artefact.Types.TABLE and hasattr(
                artifact.data, "to_dict"
            ):
                # Add DataFrame with sanitized name
                var_name = f"df_{artifact.id[:8]}"
                globals_dict[var_name] = artifact.data
                _logger.info(f"Added DataFrame '{var_name}' to globals")

        # For image output, override plt.savefig
        if self._output_type == "image":
            original_savefig = (
                globals_dict.get("plt", {}).savefig if "plt" in globals_dict else None
            )

            def custom_savefig(*args, **kwargs):
                # Create temp file for image
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    self._temp_image_path = tmp.name

                # Call original savefig with our temp path
                if args:
                    args = (self._temp_image_path,) + args[1:]
                else:
                    kwargs["fname"] = self._temp_image_path

                if original_savefig:
                    original_savefig(*args, **kwargs)

            if "plt" in globals_dict:
                globals_dict["plt"].savefig = custom_savefig

        return globals_dict

    def get_feedback_message(self, error: str) -> str:
        """Generate Python-specific error feedback.

        Args:
            error: The error message

        Returns:
            Formatted feedback
        """
        if "SyntaxError" in error:
            return f"Syntax Error in Python code: {error}. Please check your code syntax and try again."
        elif "NameError" in error:
            return f"Name Error: {error}. Make sure all variables and functions are defined."
        elif "No image was generated" in error:
            return "No image was generated. Please ensure your code creates a plot and calls plt.savefig()."
        else:
            return f"Python Error: {error}. Please fix the error and try again."
