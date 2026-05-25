from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnthropicContentType(str):
    TEXT = "text"
    IMAGE = "image"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"


class AnthropicTextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class AnthropicThinkingBlock(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str


class AnthropicToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class AnthropicToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str | list[dict[str, Any]]


class AnthropicImageBlock(BaseModel):
    type: Literal["image"] = "image"
    source: dict[str, Any]


AnthropicContentBlock = (
    AnthropicTextBlock
    | AnthropicThinkingBlock
    | AnthropicToolUseBlock
    | AnthropicToolResultBlock
    | AnthropicImageBlock
    | dict
)


class AnthropicMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[AnthropicContentBlock]


class AnthropicToolInputSchema(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class AnthropicTool(BaseModel):
    name: str
    description: str | None = None
    input_schema: AnthropicToolInputSchema


class AnthropicThinkingConfig(BaseModel):
    type: str = "enabled"
    budget_tokens: int = 10000


class AnthropicRequest(BaseModel):
    model: str
    messages: list[AnthropicMessage]
    system: str | list[dict[str, Any]] | None = None
    tools: list[AnthropicTool] | None = None
    tool_choice: str | dict | None = None
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int = 4096
    metadata: dict[str, Any] | None = None
    thinking: AnthropicThinkingConfig | dict | None = None

    class Config:
        extra = "allow"


class AnthropicUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class AnthropicResponse(BaseModel):
    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[AnthropicContentBlock]
    stop_reason: str | None = None
    stop_sequence: str | None = None
    usage: AnthropicUsage


class AnthropicStreamEvent(BaseModel):
    type: str
    message: AnthropicResponse | None = None
    index: int | None = None
    content_block: AnthropicContentBlock | None = None
    delta: dict[str, Any] | None = None
    usage: AnthropicUsage | None = None
