from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ToolFunction(BaseModel):
    """Function definition for a tool."""

    name: str = Field(..., description="The name of the function")
    description: str = Field(..., description="A description of what the function does")
    parameters: Dict[str, Any] = Field(
        ..., description="The parameters schema for the function"
    )


class Tool(BaseModel):
    """Tool definition with type and function."""

    type: str = Field(..., description="The type of the tool, e.g., 'function'")
    function: ToolFunction = Field(..., description="The function definition")


class ToolCall(BaseModel):
    """Represents a tool call made by the model."""

    id: str = Field(..., description="Unique identifier for the tool call")
    type: str = Field(..., description="The type of the tool call, e.g., 'function'")
    function: Dict[str, Any] = Field(..., description="The function call details")


class ClientResponse(BaseModel):
    """Response from the client containing messages and tool calls."""

    message: str = Field(..., description="The response message content")
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None, description="List of tool calls made by the model"
    )
    thinking_content: Optional[str] = Field(
        default=None, description="The thinking content extracted from <think> tags"
    )
