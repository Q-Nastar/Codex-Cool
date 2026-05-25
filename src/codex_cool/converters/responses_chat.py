from __future__ import annotations

import uuid
from typing import Any

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
    ReasoningInputItem,
    ResponsesRequest,
    ResponsesResponse,
    ResponseStatus,
    Role,
)


def _generate_id(prefix: str = "resp") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def responses_request_to_chat_request(req: ResponsesRequest) -> ChatCompletionRequest:
    messages: list[ChatMessage] = []
    pending_reasoning: str | None = None
    pending_tool_calls: list[ChatToolCall] = []

    if req.instructions:
        messages.append(ChatMessage(role="system", content=req.instructions))

    input_items: list[InputItem]
    if isinstance(req.input, str):
        input_items = [req.input]
    else:
        input_items = req.input

    def _flush_pending_tool_calls():
        nonlocal pending_reasoning, pending_tool_calls
        if not pending_tool_calls:
            return
        if messages and messages[-1].role == "assistant":
            last = messages[-1]
            last.tool_calls = (last.tool_calls or []) + pending_tool_calls
            if pending_reasoning and not last.reasoning_content:
                last.reasoning_content = pending_reasoning
                pending_reasoning = None
        else:
            rc = pending_reasoning
            if pending_reasoning:
                pending_reasoning = None
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=None,
                    reasoning_content=rc,
                    tool_calls=pending_tool_calls,
                )
            )
        pending_tool_calls = []

    for item in input_items:
        if isinstance(item, str):
            _flush_pending_tool_calls()
            messages.append(ChatMessage(role="user", content=item))
        elif isinstance(item, dict):
            item_type = item.get("type", "")
            if item_type == "message":
                _flush_pending_tool_calls()
                role = item.get("role", "user")
                raw_content = item.get("content", "")
                if isinstance(raw_content, list):
                    text_parts = []
                    for c in raw_content:
                        if isinstance(c, str):
                            text_parts.append(c)
                        elif isinstance(c, dict):
                            ct = c.get("type", "")
                            if ct in ("input_image", "image_url"):
                                text_parts.append("[image]")
                            elif ct in ("input_file", "file"):
                                text_parts.append("[file]")
                            elif "text" in c:
                                text_parts.append(c["text"])
                            else:
                                text_parts.append("")
                        elif hasattr(c, "text"):
                            text_parts.append(c.text)
                    raw_content = "\n".join(text_parts)
                rc = pending_reasoning if role == "assistant" else None
                if role == "assistant" and pending_reasoning:
                    pending_reasoning = None
                messages.append(ChatMessage(role=role, content=raw_content, reasoning_content=rc))
            elif item_type == "function_call_output":
                _flush_pending_tool_calls()
                messages.append(
                    ChatMessage(
                        role="tool",
                        content=item.get("output", ""),
                        tool_call_id=item.get("call_id", ""),
                    )
                )
            elif item_type == "function_call":
                pending_tool_calls.append(
                    ChatToolCall(
                        id=item.get("call_id", ""),
                        type="function",
                        function=ChatToolCallFunction(
                            name=item.get("name", ""),
                            arguments=item.get("arguments", ""),
                        ),
                    )
                )
            elif item_type == "reasoning":
                summary = item.get("summary", [])
                reasoning_text = ""
                for s in summary:
                    if isinstance(s, dict):
                        reasoning_text += s.get("text", "")
                    elif isinstance(s, str):
                        reasoning_text += s
                encrypted = item.get("encrypted_content")
                if encrypted and not reasoning_text:
                    reasoning_text = encrypted
                if reasoning_text:
                    pending_reasoning = reasoning_text
        elif isinstance(item, ReasoningInputItem):
            summary = item.summary or []
            reasoning_text = ""
            for s in summary:
                if isinstance(s, dict):
                    reasoning_text += s.get("text", "")
                elif isinstance(s, str):
                    reasoning_text += s
            encrypted = item.encrypted_content
            if encrypted and not reasoning_text:
                reasoning_text = encrypted
            if reasoning_text:
                pending_reasoning = reasoning_text
        elif isinstance(item, InputMessageItem):
            _flush_pending_tool_calls()
            content = item.content
            if isinstance(content, list):
                text_parts = []
                for c in content:
                    if isinstance(c, str):
                        text_parts.append(c)
                    elif isinstance(c, dict):
                        ct = c.get("type", "")
                        if ct in ("input_image", "image_url"):
                            text_parts.append("[image]")
                        elif ct in ("input_file", "file"):
                            text_parts.append("[file]")
                        elif "text" in c:
                            text_parts.append(c["text"])
                        else:
                            text_parts.append("")
                    elif hasattr(c, "text"):
                        text_parts.append(c.text)
                    else:
                        text_parts.append(str(c))
                content = "\n".join(text_parts)
            rc = pending_reasoning if item.role.value == "assistant" else None
            if item.role.value == "assistant" and pending_reasoning:
                pending_reasoning = None
            messages.append(ChatMessage(role=item.role.value, content=content, reasoning_content=rc))
        elif hasattr(item, "type") and item.type == "function_call_output":
            _flush_pending_tool_calls()
            messages.append(
                ChatMessage(
                    role="tool",
                    content=item.output,
                    tool_call_id=item.call_id,
                )
            )
        elif hasattr(item, "type") and item.type == "function_call":
            pending_tool_calls.append(
                ChatToolCall(
                    id=item.call_id,
                    type="function",
                    function=ChatToolCallFunction(name=item.name, arguments=item.arguments),
                )
            )

    _flush_pending_tool_calls()

    if pending_reasoning:
        messages.append(ChatMessage(role="assistant", content=None, reasoning_content=pending_reasoning))

    tools = None
    if req.tools:
        chat_tools = []
        for tool in req.tools:
            if isinstance(tool, FunctionTool):
                chat_tools.append(
                    ChatTool(
                        type="function",
                        function=ChatFunctionDefinition(
                            name=tool.name,
                            description=tool.description,
                            parameters=tool.parameters,
                            strict=tool.strict or None,
                        ),
                    )
                )
            elif isinstance(tool, dict) and tool.get("type") == "function":
                chat_tools.append(
                    ChatTool(
                        type="function",
                        function=ChatFunctionDefinition(
                            name=tool.get("name", ""),
                            description=tool.get("description"),
                            parameters=tool.get("parameters"),
                        ),
                    )
                )
        if chat_tools:
            tools = chat_tools

    tool_choice = None
    if req.tool_choice is not None:
        if isinstance(req.tool_choice, str):
            tool_choice = req.tool_choice
        elif hasattr(req.tool_choice, "type"):
            tc_type = req.tool_choice.type
            if tc_type == "function":
                tool_choice = {"type": "function", "function": {"name": req.tool_choice.name}}
            else:
                tool_choice = tc_type

    return ChatCompletionRequest(
        model=req.model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        stream=req.stream,
        temperature=req.temperature,
        top_p=req.top_p,
        max_completion_tokens=req.max_output_tokens,
    )


def chat_response_to_responses_response(
    chat_resp: ChatCompletionResponse,
    original_model: str,
) -> ResponsesResponse:
    output_items: list[OutputItem] = []

    for choice in chat_resp.choices:
        msg = choice.message

        if msg.reasoning_content:
            output_items.append(
                OutputReasoningItem(
                    id=_generate_id("rs"),
                    summary=[{"type": "summary_text", "text": msg.reasoning_content}],
                    status="completed",
                )
            )

        if msg.content:
            output_items.append(
                OutputMessageItem(
                    id=_generate_id("msg"),
                    role="assistant",
                    content=[OutputTextContent(type="output_text", text=msg.content)],
                    status="completed",
                )
            )

        if msg.tool_calls:
            for tc in msg.tool_calls:
                output_items.append(
                    OutputFunctionCallItem(
                        id=_generate_id("fc"),
                        call_id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                        status="completed",
                    )
                )

    if not output_items:
        output_items.append(
            OutputMessageItem(
                id=_generate_id("msg"),
                role="assistant",
                content=[OutputTextContent(type="output_text", text="")],
                status="completed",
            )
        )

    usage = None
    if chat_resp.usage:
        usage = {
            "input_tokens": chat_resp.usage.prompt_tokens,
            "output_tokens": chat_resp.usage.completion_tokens,
            "total_tokens": chat_resp.usage.total_tokens,
        }

    return ResponsesResponse(
        id=_generate_id("resp"),
        model=original_model,
        status=ResponseStatus.COMPLETED,
        output=output_items,
        usage=usage,
    )


def chat_stream_chunk_to_responses_events(
    chunk_data: dict[str, Any],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if state.get("response_created") is None:
        resp_id = _generate_id("resp")
        state["response_created"] = resp_id
        state["output_items"] = []
        state["current_item_index"] = -1
        events.append(
            {
                "type": "response.created",
                "response": {
                    "id": resp_id,
                    "object": "response",
                    "model": state.get("model", ""),
                    "status": "in_progress",
                    "output": [],
                },
            }
        )
        events.append(
            {
                "type": "response.in_progress",
                "response": {
                    "id": resp_id,
                    "object": "response",
                    "model": state.get("model", ""),
                    "status": "in_progress",
                    "output": [],
                },
            }
        )

    resp_id = state["response_created"]
    choices = chunk_data.get("choices", [])

    for choice in choices:
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        content = delta.get("content")
        reasoning_content = delta.get("reasoning_content")
        tool_calls = delta.get("tool_calls")
        role = delta.get("role")

        if reasoning_content:
            if state.get("reasoning_item_created") is None:
                reasoning_id = _generate_id("rs")
                state["reasoning_item_created"] = reasoning_id
                reasoning_output_index = len(state["output_items"])
                state["reasoning_output_index"] = reasoning_output_index
                state["output_items"].append({"type": "reasoning", "id": reasoning_id})
                state["accumulated_reasoning"] = ""
                events.append(
                    {
                        "type": "response.output_item.added",
                        "output_index": reasoning_output_index,
                        "item": {
                            "type": "reasoning",
                            "id": reasoning_id,
                            "summary": [],
                            "status": "in_progress",
                        },
                    }
                )
            state["accumulated_reasoning"] = state.get("accumulated_reasoning", "") + reasoning_content

        if role == "assistant" and state.get("message_item_created") is None:
            msg_id = _generate_id("msg")
            state["message_item_created"] = msg_id
            state["current_item_index"] = len(state["output_items"])
            state["output_items"].append({"type": "message", "id": msg_id})
            events.append(
                {
                    "type": "response.output_item.added",
                    "output_index": state["current_item_index"],
                    "item": {
                        "type": "message",
                        "id": msg_id,
                        "role": "assistant",
                        "content": [],
                        "status": "in_progress",
                    },
                }
            )
            content_id = _generate_id("cnt")
            state["text_content_id"] = content_id
            state["text_content_index"] = 0
            events.append(
                {
                    "type": "response.content_part.added",
                    "output_index": state["current_item_index"],
                    "content_index": 0,
                    "part": {"type": "output_text", "text": ""},
                }
            )

        if content:
            events.append(
                {
                    "type": "response.output_text.delta",
                    "output_index": state.get("current_item_index", 0),
                    "content_index": state.get("text_content_index", 0),
                    "delta": content,
                }
            )

        if tool_calls:
            for tc_delta in tool_calls:
                tc_index = tc_delta.get("index", 0)
                tc_id = tc_delta.get("id")
                func = tc_delta.get("function", {})

                fc_key = f"fc_{tc_index}"
                if state.get(fc_key) is None and tc_id:
                    fc_item_id = _generate_id("fc")
                    state[fc_key] = {
                        "item_id": fc_item_id,
                        "call_id": tc_id,
                        "name": func.get("name", ""),
                        "arguments": "",
                    }
                    fc_output_index = len(state["output_items"])
                    state["output_items"].append({"type": "function_call", "id": fc_item_id})
                    events.append(
                        {
                            "type": "response.output_item.added",
                            "output_index": fc_output_index,
                            "item": {
                                "type": "function_call",
                                "id": fc_item_id,
                                "call_id": tc_id,
                                "name": func.get("name", ""),
                                "arguments": "",
                                "status": "in_progress",
                            },
                        }
                    )
                elif state.get(fc_key):
                    if func.get("name"):
                        state[fc_key]["name"] = func["name"]
                    if func.get("arguments"):
                        state[fc_key]["arguments"] += func["arguments"]
                        events.append(
                            {
                                "type": "response.function_call_arguments.delta",
                                "output_index": state["output_items"].index(
                                    {"type": "function_call", "id": state[fc_key]["item_id"]}
                                )
                                if {"type": "function_call", "id": state[fc_key]["item_id"]}
                                in state["output_items"]
                                else len(state["output_items"]) - 1,
                                "item_id": state[fc_key]["item_id"],
                                "delta": func["arguments"],
                            }
                        )

        if finish_reason:
            if state.get("reasoning_item_created"):
                reasoning_summary = []
                if state.get("accumulated_reasoning", "").strip():
                    reasoning_summary.append({"type": "summary_text", "text": state["accumulated_reasoning"].strip()})
                reasoning_item = {
                    "type": "reasoning",
                    "id": state["reasoning_item_created"],
                    "summary": reasoning_summary,
                    "status": "completed",
                }
                events.append(
                    {
                        "type": "response.output_item.done",
                        "output_index": state.get("reasoning_output_index", 0),
                        "item": reasoning_item,
                    }
                )

            if state.get("message_item_created"):
                events.append(
                    {
                        "type": "response.content_part.done",
                        "output_index": state.get("current_item_index", 0),
                        "content_index": state.get("text_content_index", 0),
                        "part": {"type": "output_text", "text": state.get("accumulated_text", "")},
                    }
                )
                events.append(
                    {
                        "type": "response.output_item.done",
                        "output_index": state.get("current_item_index", 0),
                        "item": {
                            "type": "message",
                            "id": state["message_item_created"],
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": state.get("accumulated_text", ""),
                                }
                            ],
                            "status": "completed",
                        },
                    }
                )

            for key in list(state.keys()):
                if key.startswith("fc_") and isinstance(state[key], dict):
                    fc = state[key]
                    events.append(
                        {
                            "type": "response.function_call_arguments.done",
                            "output_index": len(state["output_items"]) - 1,
                            "item_id": fc["item_id"],
                            "arguments": fc["arguments"],
                        }
                    )
                    events.append(
                        {
                            "type": "response.output_item.done",
                            "output_index": len(state["output_items"]) - 1,
                            "item": {
                                "type": "function_call",
                                "id": fc["item_id"],
                                "call_id": fc["call_id"],
                                "name": fc["name"],
                                "arguments": fc["arguments"],
                                "status": "completed",
                            },
                        }
                    )

            output_items_final = []
            if state.get("reasoning_item_created"):
                reasoning_summary = []
                if state.get("accumulated_reasoning", "").strip():
                    reasoning_summary.append({"type": "summary_text", "text": state["accumulated_reasoning"].strip()})
                output_items_final.append(
                    {
                        "type": "reasoning",
                        "id": state["reasoning_item_created"],
                        "summary": reasoning_summary,
                        "status": "completed",
                    }
                )
            for oi in state.get("output_items", []):
                if oi["type"] == "message":
                    output_items_final.append(
                        {
                            "type": "message",
                            "id": oi["id"],
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": state.get("accumulated_text", ""),
                                }
                            ],
                            "status": "completed",
                        }
                    )
                elif oi["type"] == "function_call":
                    fc_key = None
                    for k, v in state.items():
                        if k.startswith("fc_") and isinstance(v, dict) and v.get("item_id") == oi["id"]:
                            fc_key = k
                            break
                    if fc_key:
                        fc = state[fc_key]
                        output_items_final.append(
                            {
                                "type": "function_call",
                                "id": fc["item_id"],
                                "call_id": fc["call_id"],
                                "name": fc["name"],
                                "arguments": fc["arguments"],
                                "status": "completed",
                            }
                        )

            events.append(
                {
                    "type": "response.completed",
                    "response": {
                        "id": resp_id,
                        "object": "response",
                        "model": state.get("model", ""),
                        "status": "completed",
                        "output": output_items_final,
                    },
                }
            )

    if content and state.get("accumulated_text") is not None:
        state["accumulated_text"] = state.get("accumulated_text", "") + content
    elif content:
        state["accumulated_text"] = content

    return events
