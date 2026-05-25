from __future__ import annotations

import json
import uuid
from typing import Any

from codex_cool.models.anthropic import (
    AnthropicContentBlock,
    AnthropicMessage,
    AnthropicRequest,
    AnthropicResponse,
    AnthropicTextBlock,
    AnthropicThinkingBlock,
    AnthropicTool,
    AnthropicToolInputSchema,
    AnthropicToolResultBlock,
    AnthropicToolUseBlock,
    AnthropicUsage,
)
from codex_cool.models.chat import (
    ChatChoice,
    ChatChoiceMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatFunctionDefinition,
    ChatMessage,
    ChatTool,
    ChatToolCall,
    ChatToolCallFunction,
    ChatUsage,
)
from codex_cool.models.responses import (
    FunctionTool,
    InputItem,
    InputMessageItem,
    OutputFunctionCallItem,
    OutputItem,
    OutputMessageItem,
    OutputReasoningItem,
    OutputTextContent,
    ResponsesRequest,
    ResponsesResponse,
    ResponseStatus,
    Role,
)


def _generate_id(prefix: str = "msg") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def anthropic_request_to_chat_request(req: AnthropicRequest) -> ChatCompletionRequest:
    messages: list[ChatMessage] = []

    if req.system:
        if isinstance(req.system, str):
            messages.append(ChatMessage(role="system", content=req.system))
        elif isinstance(req.system, list):
            sys_text_parts = []
            for block in req.system:
                if isinstance(block, dict) and block.get("type") == "text":
                    sys_text_parts.append(block.get("text", ""))
            if sys_text_parts:
                messages.append(ChatMessage(role="system", content="\n".join(sys_text_parts)))

    for msg in req.messages:
        if isinstance(msg.content, str):
            messages.append(ChatMessage(role=msg.role, content=msg.content))
        elif isinstance(msg.content, list):
            content_parts: list[dict[str, Any]] = []
            tool_calls_list: list[ChatToolCall] = []
            tool_results: list[tuple[str, str]] = []
            reasoning_text: str | None = None

            for block in msg.content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                else:
                    block_type = block.type if hasattr(block, "type") else ""

                if block_type == "text":
                    text = block.text if hasattr(block, "text") else block.get("text", "")
                    content_parts.append({"type": "text", "text": text})
                elif block_type == "thinking":
                    thinking = block.thinking if hasattr(block, "thinking") else block.get("thinking", "")
                    if thinking:
                        reasoning_text = (reasoning_text or "") + thinking
                elif block_type == "tool_use":
                    tc_id = block.id if hasattr(block, "id") else block.get("id", _generate_id("tc"))
                    name = block.name if hasattr(block, "name") else block.get("name", "")
                    inp = block.input if hasattr(block, "input") else block.get("input", {})

                    tool_calls_list.append(
                        ChatToolCall(
                            id=tc_id,
                            type="function",
                            function=ChatToolCallFunction(name=name, arguments=json.dumps(inp)),
                        )
                    )
                elif block_type == "tool_result":
                    tool_use_id = (
                        block.tool_use_id if hasattr(block, "tool_use_id") else block.get("tool_use_id", "")
                    )
                    result_content = block.content if hasattr(block, "content") else block.get("content", "")
                    if isinstance(result_content, list):
                        result_text_parts = []
                        for rc in result_content:
                            if isinstance(rc, dict) and rc.get("type") == "text":
                                result_text_parts.append(rc.get("text", ""))
                            elif isinstance(rc, str):
                                result_text_parts.append(rc)
                        result_content = "\n".join(result_text_parts)
                    tool_results.append((tool_use_id, str(result_content or "")))

            if msg.role == "assistant" and tool_calls_list:
                text_content = None
                if content_parts:
                    text_parts = [p.get("text", "") for p in content_parts if p.get("type") == "text"]
                    if text_parts:
                        text_content = "\n".join(text_parts)
                messages.append(
                    ChatMessage(role="assistant", content=text_content, tool_calls=tool_calls_list, reasoning_content=reasoning_text)
                )
            elif msg.role == "user" and tool_results:
                if content_parts:
                    text_parts = [p.get("text", "") for p in content_parts if p.get("type") == "text"]
                    if text_parts:
                        messages.append(ChatMessage(role="user", content="\n".join(text_parts)))
                for tr_id, tr_content in tool_results:
                    messages.append(
                        ChatMessage(role="tool", content=tr_content, tool_call_id=tr_id)
                    )
            else:
                text_parts = [p.get("text", "") for p in content_parts if p.get("type") == "text"]
                text_content = "\n".join(text_parts) if text_parts else None
                messages.append(ChatMessage(role=msg.role, content=text_content, reasoning_content=reasoning_text if msg.role == "assistant" else None))

    tools = None
    if req.tools:
        chat_tools = []
        for tool in req.tools:
            schema = tool.input_schema
            chat_tools.append(
                ChatTool(
                    type="function",
                    function=ChatFunctionDefinition(
                        name=tool.name,
                        description=tool.description,
                        parameters=schema.model_dump(exclude_none=True) if schema else None,
                    ),
                )
            )
        if chat_tools:
            tools = chat_tools

    tool_choice = None
    if req.tool_choice is not None:
        if isinstance(req.tool_choice, str):
            if req.tool_choice == "auto":
                tool_choice = "auto"
            elif req.tool_choice == "any":
                tool_choice = "required"
            elif req.tool_choice == "none":
                tool_choice = "none"
        elif isinstance(req.tool_choice, dict):
            tool_choice = req.tool_choice

    max_tokens_val = req.max_tokens or 16384

    return ChatCompletionRequest(
        model=req.model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        stream=req.stream,
        temperature=req.temperature,
        top_p=req.top_p,
        max_completion_tokens=max_tokens_val,
    )


def chat_response_to_anthropic_response(
    chat_resp: ChatCompletionResponse,
    original_model: str,
) -> AnthropicResponse:
    content: list[AnthropicContentBlock] = []
    stop_reason = "end_turn"

    for choice in chat_resp.choices:
        msg = choice.message

        if msg.reasoning_content:
            content.append(AnthropicThinkingBlock(type="thinking", thinking=msg.reasoning_content))

        if msg.content:
            content.append(AnthropicTextBlock(type="text", text=msg.content))

        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    inp = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    inp = {"raw_arguments": tc.function.arguments}
                content.append(
                    AnthropicToolUseBlock(
                        type="tool_use",
                        id=tc.id,
                        name=tc.function.name,
                        input=inp,
                    )
                )
                stop_reason = "tool_use"

    if not content:
        content.append(AnthropicTextBlock(type="text", text=""))

    usage = AnthropicUsage()
    if chat_resp.usage:
        usage = AnthropicUsage(
            input_tokens=chat_resp.usage.prompt_tokens,
            output_tokens=chat_resp.usage.completion_tokens,
        )

    return AnthropicResponse(
        id=_generate_id("msg"),
        type="message",
        role="assistant",
        model=original_model,
        content=content,
        stop_reason=stop_reason,
        usage=usage,
    )


def anthropic_request_to_responses_request(req: AnthropicRequest) -> ResponsesRequest:
    input_items: list[InputItem] = []

    for msg in req.messages:
        if isinstance(msg.content, str):
            input_items.append(InputMessageItem(type="message", role=Role(msg.role), content=msg.content))
        elif isinstance(msg.content, list):
            text_parts = []
            has_tool_use = False
            tool_results: list[tuple[str, str]] = []

            for block in msg.content:
                if isinstance(block, dict):
                    block_type = block.get("type", "")
                else:
                    block_type = block.type if hasattr(block, "type") else ""

                if block_type == "text":
                    text = block.text if hasattr(block, "text") else block.get("text", "")
                    text_parts.append(text)
                elif block_type == "thinking":
                    thinking_text = block.thinking if hasattr(block, "thinking") else block.get("thinking", "")
                    if thinking_text:
                        from codex_cool.models.responses import OutputReasoningItem
                        input_items.append(
                            OutputReasoningItem(
                                type="reasoning",
                                summary=[{"type": "summary_text", "text": thinking_text}],
                            )
                        )
                elif block_type == "tool_use":
                    has_tool_use = True
                elif block_type == "tool_result":
                    tool_use_id = (
                        block.tool_use_id if hasattr(block, "tool_use_id") else block.get("tool_use_id", "")
                    )
                    result_content = block.content if hasattr(block, "content") else block.get("content", "")
                    if isinstance(result_content, list):
                        rp = []
                        for rc in result_content:
                            if isinstance(rc, dict) and rc.get("type") == "text":
                                rp.append(rc.get("text", ""))
                            elif isinstance(rc, str):
                                rp.append(rc)
                        result_content = "\n".join(rp)
                    tool_results.append((tool_use_id, str(result_content or "")))

            if tool_results:
                from codex_cool.models.responses import FunctionCallOutputItem

                for tr_call_id, tr_output in tool_results:
                    input_items.append(
                        FunctionCallOutputItem(
                            type="function_call_output",
                            call_id=tr_call_id,
                            output=tr_output,
                        )
                    )
            elif text_parts:
                input_items.append(
                    InputMessageItem(type="message", role=Role(msg.role), content="\n".join(text_parts))
                )

    tools = []
    if req.tools:
        for tool in req.tools:
            schema = tool.input_schema
            tools.append(
                FunctionTool(
                    type="function",
                    name=tool.name,
                    description=tool.description,
                    parameters=schema.model_dump(exclude_none=True) if schema else None,
                )
            )

    tool_choice = None
    if req.tool_choice is not None:
        if isinstance(req.tool_choice, str):
            if req.tool_choice == "auto":
                from codex_cool.models.responses import ToolChoiceAuto

                tool_choice = ToolChoiceAuto()
            elif req.tool_choice == "any":
                from codex_cool.models.responses import ToolChoiceRequired

                tool_choice = ToolChoiceRequired()
            elif req.tool_choice == "none":
                from codex_cool.models.responses import ToolChoiceNone

                tool_choice = ToolChoiceNone()

    instructions = None
    if req.system:
        if isinstance(req.system, str):
            instructions = req.system
        elif isinstance(req.system, list):
            parts = []
            for block in req.system:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            if parts:
                instructions = "\n".join(parts)

    return ResponsesRequest(
        model=req.model,
        input=input_items,
        instructions=instructions,
        tools=tools,
        tool_choice=tool_choice,
        stream=req.stream,
        temperature=req.temperature,
        top_p=req.top_p,
        max_output_tokens=req.max_tokens,
    )


def responses_response_to_anthropic_response(resp: ResponsesResponse, real_model: str | None = None) -> AnthropicResponse:
    content: list[AnthropicContentBlock] = []
    stop_reason = "end_turn"

    for item in resp.output:
        if isinstance(item, OutputMessageItem):
            for c in item.content:
                if isinstance(c, OutputTextContent):
                    content.append(AnthropicTextBlock(type="text", text=c.text))
        elif isinstance(item, OutputFunctionCallItem):
            try:
                inp = json.loads(item.arguments)
            except (json.JSONDecodeError, TypeError):
                inp = {"raw_arguments": item.arguments}
            content.append(
                AnthropicToolUseBlock(
                    type="tool_use",
                    id=item.call_id,
                    name=item.name,
                    input=inp,
                )
            )
            stop_reason = "tool_use"
        elif isinstance(item, OutputReasoningItem):
            if item.summary:
                summary_text = ""
                for s in item.summary:
                    if isinstance(s, dict):
                        summary_text += s.get("text", "") + "\n"
                    elif isinstance(s, str):
                        summary_text += s + "\n"
                if summary_text.strip():
                    content.append(
                        AnthropicThinkingBlock(type="thinking", thinking=summary_text.strip())
                    )

    if not content:
        content.append(AnthropicTextBlock(type="text", text=""))

    usage = AnthropicUsage()
    if resp.usage:
        usage = AnthropicUsage(
            input_tokens=resp.usage.get("input_tokens", 0),
            output_tokens=resp.usage.get("output_tokens", 0),
        )

    return AnthropicResponse(
        id=resp.id,
        type="message",
        role="assistant",
        model=real_model or resp.model,
        content=content,
        stop_reason=stop_reason,
        usage=usage,
    )


def anthropic_response_to_responses_response(
    resp: AnthropicResponse, real_model: str | None = None
) -> ResponsesResponse:
    output_items: list[OutputItem] = []

    for block in resp.content:
        if isinstance(block, dict):
            block_type = block.get("type", "")
        else:
            block_type = block.type if hasattr(block, "type") else ""

        if block_type == "text":
            text = block.text if hasattr(block, "text") else block.get("text", "")
            output_items.append(
                OutputMessageItem(
                    type="message",
                    id=_generate_id("msg"),
                    role="assistant",
                    content=[OutputTextContent(type="output_text", text=text)],
                    status="completed",
                )
            )
        elif block_type == "thinking":
            thinking = block.thinking if hasattr(block, "thinking") else block.get("thinking", "")
            output_items.append(
                OutputReasoningItem(
                    type="reasoning",
                    id=_generate_id("rs"),
                    summary=[{"type": "summary_text", "text": thinking}],
                    status="completed",
                )
            )
        elif block_type == "tool_use":
            tc_id = block.id if hasattr(block, "id") else block.get("id", _generate_id("fc"))
            name = block.name if hasattr(block, "name") else block.get("name", "")
            inp = block.input if hasattr(block, "input") else block.get("input", {})

            output_items.append(
                OutputFunctionCallItem(
                    type="function_call",
                    id=tc_id,
                    call_id=tc_id,
                    name=name,
                    arguments=json.dumps(inp) if not isinstance(inp, str) else inp,
                    status="completed",
                )
            )

    if not output_items:
        output_items.append(
            OutputMessageItem(
                type="message",
                id=_generate_id("msg"),
                role="assistant",
                content=[OutputTextContent(type="output_text", text="")],
                status="completed",
            )
        )

    usage = None
    if resp.usage:
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
        }

    return ResponsesResponse(
        id=resp.id or _generate_id("resp"),
        object="response",
        model=real_model or resp.model,
        status="completed",
        output=output_items,
        usage=usage,
    )
