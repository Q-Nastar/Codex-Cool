from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


async def parse_sse_stream(response_stream: AsyncIterator[bytes]) -> AsyncIterator[dict[str, Any]]:
    buffer = ""
    async for chunk in response_stream:
        if isinstance(chunk, bytes):
            buffer += chunk.decode("utf-8", errors="replace")
        elif isinstance(chunk, str):
            buffer += chunk

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()

            if not line:
                continue

            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    return
                try:
                    parsed = json.loads(data)
                    yield parsed
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SSE data: %s", data[:200])
                    continue
            elif line.startswith("event:"):
                continue
            elif line.startswith("id:"):
                continue
            elif line.startswith("retry:"):
                continue


def format_sse_event(data: dict[str, Any] | str) -> str:
    if isinstance(data, str):
        if data == "[DONE]":
            return "data: [DONE]\n\n"
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def transform_anthropic_sse_to_chat(
    response_stream: AsyncIterator[bytes],
    model_override: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    import uuid

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    model = model_override or ""

    tool_calls_buffer: dict[int, dict[str, Any]] = {}
    current_tool_index = -1
    state: dict[str, Any] = {
        "reasoning_item_added": False,
        "reasoning_block_closed": False,
    }

    async for event in parse_sse_stream(response_stream):
        event_type = event.get("type", "")

        if event_type == "message_start":
            msg = event.get("message", {})
            if not model:
                model = msg.get("model", model)
            yield {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }
                ],
            }

        elif event_type == "content_block_start":
            content_block = event.get("content_block", {})
            block_type = content_block.get("type", "")

            if block_type == "text":
                pass
            elif block_type == "thinking":
                state["reasoning_item_added"] = True
            elif block_type == "tool_use":
                current_tool_index = len(tool_calls_buffer)
                tool_id = content_block.get("id", f"call_{uuid.uuid4().hex[:8]}")
                tool_name = content_block.get("name", "")
                tool_calls_buffer[current_tool_index] = {
                    "id": tool_id,
                    "name": tool_name,
                    "arguments": "",
                }
                yield {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": current_tool_index,
                                        "id": tool_id,
                                        "type": "function",
                                        "function": {"name": tool_name, "arguments": ""},
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }

        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                text = delta.get("text", "")
                yield {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": text},
                            "finish_reason": None,
                        }
                    ],
                }
            elif delta_type == "thinking_delta":
                thinking = delta.get("thinking", "")
                yield {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"reasoning_content": thinking},
                            "finish_reason": None,
                        }
                    ],
                }
            elif delta_type == "input_json_delta":
                partial_json = delta.get("partial_json", "")
                if current_tool_index in tool_calls_buffer:
                    tool_calls_buffer[current_tool_index]["arguments"] += partial_json
                    yield {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": current_tool_index,
                                            "function": {"arguments": partial_json},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }

        elif event_type == "content_block_stop":
            if state.get("reasoning_item_added") and not state.get("reasoning_block_closed"):
                state["reasoning_block_closed"] = True

        elif event_type == "message_delta":
            delta = event.get("delta", {})
            stop_reason = delta.get("stop_reason")
            finish_reason = None
            if stop_reason == "end_turn":
                finish_reason = "stop"
            elif stop_reason == "tool_use":
                finish_reason = "tool_calls"
            elif stop_reason == "max_tokens":
                finish_reason = "length"

            if finish_reason:
                yield {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": finish_reason,
                        }
                    ],
                }

        elif event_type == "message_stop":
            pass


async def transform_anthropic_sse_to_responses(
    response_stream: AsyncIterator[bytes],
    model: str,
) -> AsyncIterator[dict[str, Any]]:
    from codex_cool.converters.responses_chat import _generate_id

    resp_id = _generate_id("resp")
    msg_id = _generate_id("msg")
    state: dict[str, Any] = {
        "response_created": False,
        "message_created": False,
        "text_content_added": False,
        "reasoning_item_added": False,
        "accumulated_text": "",
        "accumulated_reasoning": "",
        "tool_calls": {},
        "current_tool_index": -1,
    }

    async for event in parse_sse_stream(response_stream):
        event_type = event.get("type", "")

        if event_type == "message_start":
            if not state["response_created"]:
                state["response_created"] = True
                yield {"type": "response.created", "response": {"id": resp_id, "object": "response", "model": model, "status": "in_progress", "output": []}}
                yield {"type": "response.in_progress", "response": {"id": resp_id, "object": "response", "model": model, "status": "in_progress", "output": []}}

        elif event_type == "content_block_start":
            content_block = event.get("content_block", {})
            block_type = content_block.get("type", "")
            index = event.get("index", 0)

            if block_type == "text":
                if not state["message_created"]:
                    state["message_created"] = True
                    yield {
                        "type": "response.output_item.added",
                        "output_index": 0,
                        "item": {"type": "message", "id": msg_id, "role": "assistant", "content": [], "status": "in_progress"},
                    }
                if not state["text_content_added"]:
                    state["text_content_added"] = True
                    yield {
                        "type": "response.content_part.added",
                        "output_index": 0,
                        "content_index": 0,
                        "part": {"type": "output_text", "text": ""},
                    }

            elif block_type == "thinking":
                if not state["message_created"]:
                    state["message_created"] = True
                    yield {
                        "type": "response.output_item.added",
                        "output_index": 0,
                        "item": {"type": "message", "id": msg_id, "role": "assistant", "content": [], "status": "in_progress"},
                    }
                if not state["reasoning_item_added"]:
                    state["reasoning_item_added"] = True
                    reasoning_id = _generate_id("rs")
                    state["reasoning_id"] = reasoning_id
                    yield {
                        "type": "response.output_item.added",
                        "output_index": 0,
                        "item": {
                            "type": "reasoning",
                            "id": reasoning_id,
                            "summary": [],
                            "status": "in_progress",
                        },
                    }

            elif block_type == "tool_use":
                tool_id = content_block.get("id", _generate_id("fc"))
                tool_name = content_block.get("name", "")
                state["current_tool_index"] = len(state["tool_calls"])
                state["tool_calls"][state["current_tool_index"]] = {
                    "id": tool_id,
                    "call_id": tool_id,
                    "name": tool_name,
                    "arguments": "",
                }
                output_index = 1 if state["message_created"] else 0
                yield {
                    "type": "response.output_item.added",
                    "output_index": output_index,
                    "item": {
                        "type": "function_call",
                        "id": tool_id,
                        "call_id": tool_id,
                        "name": tool_name,
                        "arguments": "",
                        "status": "in_progress",
                    },
                }

        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                text = delta.get("text", "")
                state["accumulated_text"] += text
                yield {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "content_index": 0,
                    "delta": text,
                }
            elif delta_type == "thinking_delta":
                thinking = delta.get("thinking", "")
                state["accumulated_reasoning"] += thinking
            elif delta_type == "input_json_delta":
                partial_json = delta.get("partial_json", "")
                tidx = state["current_tool_index"]
                if tidx in state["tool_calls"]:
                    state["tool_calls"][tidx]["arguments"] += partial_json
                    output_index = 1 if state["message_created"] else 0
                    yield {
                        "type": "response.function_call_arguments.delta",
                        "output_index": output_index,
                        "item_id": state["tool_calls"][tidx]["id"],
                        "delta": partial_json,
                    }

        elif event_type == "content_block_stop":
            pass

        elif event_type == "message_delta":
            delta = event.get("delta", {})
            stop_reason = delta.get("stop_reason")

            if stop_reason:
                output_items = []

                if state["reasoning_item_added"]:
                    reasoning_summary = []
                    if state["accumulated_reasoning"].strip():
                        reasoning_summary.append({"type": "summary_text", "text": state["accumulated_reasoning"].strip()})
                    reasoning_item = {
                        "type": "reasoning",
                        "id": state.get("reasoning_id", _generate_id("rs")),
                        "summary": reasoning_summary,
                        "status": "completed",
                    }
                    output_items.append(reasoning_item)
                    yield {
                        "type": "response.output_item.done",
                        "output_index": len(output_items) - 1,
                        "item": reasoning_item,
                    }

                if state["message_created"]:
                    yield {
                        "type": "response.content_part.done",
                        "output_index": 0,
                        "content_index": 0,
                        "part": {"type": "output_text", "text": state["accumulated_text"]},
                    }
                    output_items.append({
                        "type": "message",
                        "id": msg_id,
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": state["accumulated_text"]}],
                        "status": "completed",
                    })
                    yield {
                        "type": "response.output_item.done",
                        "output_index": 0,
                        "item": output_items[0],
                    }

                for tidx, tc in state["tool_calls"].items():
                    output_index = len(output_items)
                    fc_item = {
                        "type": "function_call",
                        "id": tc["id"],
                        "call_id": tc["call_id"],
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                        "status": "completed",
                    }
                    output_items.append(fc_item)
                    yield {
                        "type": "response.function_call_arguments.done",
                        "output_index": output_index,
                        "item_id": tc["id"],
                        "arguments": tc["arguments"],
                    }
                    yield {
                        "type": "response.output_item.done",
                        "output_index": output_index,
                        "item": fc_item,
                    }

                yield {
                    "type": "response.completed",
                    "response": {
                        "id": resp_id,
                        "object": "response",
                        "model": model,
                        "status": "completed",
                        "output": output_items,
                    },
                }

        elif event_type == "message_stop":
            pass
