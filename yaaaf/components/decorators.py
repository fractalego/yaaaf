import functools
import logging
from typing import Callable, Any

_logger = logging.getLogger(__name__)


def handle_exceptions(func: Callable) -> Callable:
    """
    Decorator that catches exceptions in agent query methods,
    logs the error, and returns a formatted error message with task completion.

    Usage:
        @handle_exceptions
        async def query(self, messages, notes=None):
            # method implementation
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> str:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Get the class name for logging context
            class_name = args[0].__class__.__name__ if args else "Unknown"
            error_msg = f"{class_name}: {str(e)}"

            _logger.error(
                f"Exception in {class_name}.{func.__name__}: {e}", exc_info=True
            )

            # Return formatted error message with task completion
            return f"{error_msg} <taskcompleted/>"

    return wrapper


def handle_exceptions_sync(func: Callable) -> Callable:
    """
    Decorator for synchronous methods that catches exceptions,
    logs the error, and returns a formatted error message with task completion.

    Usage:
        @handle_exceptions_sync
        def some_method(self, ...):
            # method implementation
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Get the class name for logging context
            class_name = args[0].__class__.__name__ if args else "Unknown"
            error_msg = f"{class_name}: {str(e)}"

            _logger.error(
                f"Exception in {class_name}.{func.__name__}: {e}", exc_info=True
            )

            # Return formatted error message with task completion
            return f"{error_msg} <taskcompleted/>"

    return wrapper
