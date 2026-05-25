from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRole(str):
    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[ChatToolCall] | None = None
    tool_call_id: str | None = None
    reasoning_content: str | None = None


class ChatToolCallFunction(BaseModel):
    name: str
    arguments: str


class ChatToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ChatToolCallFunction


class ChatFunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None
    strict: bool | None = None


class ChatTool(BaseModel):
    type: Literal["function"] = "function"
    function: ChatFunctionDefinition


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    tools: list[ChatTool] | None = None
    tool_choice: str | dict | None = None
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stop: str | list[str] | None = None
    metadata: dict[str, Any] | None = None


class ChatChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ChatToolCall] | None = None
    reasoning_content: str | None = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str | None = None


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage | None = None


class ChatStreamDelta(BaseModel):
    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    reasoning_content: str | None = None


class ChatStreamChoice(BaseModel):
    index: int = 0
    delta: ChatStreamDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    model: str
    choices: list[ChatStreamChoice]
    usage: ChatUsage | None = None
