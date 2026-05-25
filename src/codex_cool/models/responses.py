from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ResponseStatus(str, Enum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"


class FunctionTool(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None
    strict: bool = False


class WebSearchTool(BaseModel):
    type: Literal["web_search"] = "web_search"


class FileSearchTool(BaseModel):
    type: Literal["file_search"] = "file_search"
    vector_store_ids: list[str] = Field(default_factory=list)


class ToolChoiceAuto(BaseModel):
    type: Literal["auto"] = "auto"


class ToolChoiceRequired(BaseModel):
    type: Literal["required"] = "required"


class ToolChoiceNone(BaseModel):
    type: Literal["none"] = "none"


class ToolChoiceFunction(BaseModel):
    type: Literal["function"] = "function"
    name: str


ToolChoice = ToolChoiceAuto | ToolChoiceRequired | ToolChoiceNone | ToolChoiceFunction | str


class InputTextContent(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class InputImageContent(BaseModel):
    type: Literal["input_image"] = "input_image"
    image_url: str | None = None
    detail: str | None = None


class OutputTextContent(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str
    annotations: list[dict[str, Any]] = Field(default_factory=list)


InputContent = InputTextContent | InputImageContent | OutputTextContent | str | dict


class InputMessageItem(BaseModel):
    type: Literal["message"] = "message"
    role: Role
    content: str | list[InputContent]


class FunctionCallOutputItem(BaseModel):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: str


class FunctionCallInputItem(BaseModel):
    type: Literal["function_call"] = "function_call"
    call_id: str
    name: str
    arguments: str


class ReasoningInputItem(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    id: str | None = None
    summary: list[dict[str, Any]] = Field(default_factory=list)
    encrypted_content: str | None = None


InputItem = InputMessageItem | FunctionCallOutputItem | FunctionCallInputItem | ReasoningInputItem | dict | str


OutputContent = OutputTextContent | dict


class OutputMessageItem(BaseModel):
    type: Literal["message"] = "message"
    id: str | None = None
    role: Literal["assistant"] = "assistant"
    content: list[OutputContent] = Field(default_factory=list)
    status: str | None = None


class OutputFunctionCallItem(BaseModel):
    type: Literal["function_call"] = "function_call"
    id: str | None = None
    call_id: str
    name: str
    arguments: str
    status: str | None = None


class OutputReasoningItem(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    id: str | None = None
    summary: list[dict[str, Any]] = Field(default_factory=list)
    encrypted_content: str | None = None
    status: str | None = None


OutputItem = OutputMessageItem | OutputFunctionCallItem | OutputReasoningItem | dict


class ResponsesRequest(BaseModel):
    model: str
    input: str | list[InputItem]
    instructions: str | None = None
    tools: list[FunctionTool | WebSearchTool | FileSearchTool | dict] = Field(default_factory=list)
    tool_choice: ToolChoice | None = None
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    previous_response_id: str | None = None
    metadata: dict[str, Any] | None = None

    class Config:
        extra = "allow"


class ResponsesResponse(BaseModel):
    id: str
    object: Literal["response"] = "response"
    model: str
    status: ResponseStatus = ResponseStatus.COMPLETED
    output: list[OutputItem] = Field(default_factory=list)
    usage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    created_at: int | None = None

    class Config:
        extra = "allow"


class ResponseStreamEvent(BaseModel):
    type: str
    item: OutputItem | None = None
    output_index: int | None = None
    content_index: int | None = None
    delta: str | None = None
    response: ResponsesResponse | None = None
