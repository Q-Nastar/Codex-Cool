from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from codex_cool.api import api_router, FRONTEND_DIR
from codex_cool.config import ProxyConfig, load_config
from codex_cool.converters.anthropic_chat import (
    anthropic_request_to_chat_request,
    anthropic_request_to_responses_request,
    chat_response_to_anthropic_response,
    responses_response_to_anthropic_response,
)
from codex_cool.converters.responses_chat import (
    chat_response_to_responses_response,
    chat_stream_chunk_to_responses_events,
    responses_request_to_chat_request,
)
from codex_cool.converters.stream import (
    format_sse_event,
    parse_sse_stream,
    transform_anthropic_sse_to_chat,
    transform_anthropic_sse_to_responses,
)
from codex_cool.proxy.router import ProxyRouter

logger = logging.getLogger(__name__)

_response_store: dict[str, dict[str, Any]] = {}
_RESPONSE_STORE_MAX = 200


def _ensure_reasoning_content(messages: list[dict[str, Any]]) -> None:
    for msg in messages:
        if msg.get("role") == "assistant" and not msg.get("reasoning_content"):
            msg["reasoning_content"] = " "


def _sanitize_chat_messages(messages: list[dict[str, Any]]) -> None:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            sanitized = []
            for part in content:
                if isinstance(part, dict):
                    ptype = part.get("type", "")
                    if ptype == "text":
                        sanitized.append(part)
                    elif ptype == "image_url":
                        sanitized.append({"type": "text", "text": "[image]"})
                    elif ptype in ("input_image", "input_file", "file"):
                        sanitized.append({"type": "text", "text": "[" + ptype.replace("input_", "") + "]"})
                    else:
                        if "text" in part:
                            sanitized.append({"type": "text", "text": part["text"]})
                        else:
                            sanitized.append({"type": "text", "text": ""})
                elif isinstance(part, str):
                    sanitized.append({"type": "text", "text": part})
                else:
                    sanitized.append({"type": "text", "text": str(part) if part else ""})
            if all(p.get("type") == "text" for p in sanitized if isinstance(p, dict)):
                msg["content"] = "\n".join(p.get("text", "") for p in sanitized)
            else:
                msg["content"] = sanitized


def _store_response(resp_data: dict[str, Any], input_data: Any = None, instructions: str | None = None) -> None:
    resp_id = resp_data.get("id")
    if not resp_id:
        return
    store_entry = {**resp_data}
    if input_data is not None:
        store_entry["_input"] = input_data
    if instructions is not None:
        store_entry["_instructions"] = instructions
    _response_store[resp_id] = store_entry
    if len(_response_store) > _RESPONSE_STORE_MAX:
        oldest = list(_response_store.keys())[0]
        _response_store.pop(oldest, None)


def _get_previous_response(previous_response_id: str | None) -> dict[str, Any] | None:
    if not previous_response_id:
        return None
    return _response_store.get(previous_response_id)


def _input_already_has_history(input_data: Any) -> bool:
    if not isinstance(input_data, list) or len(input_data) <= 1:
        return False
    for item in input_data:
        if isinstance(item, dict):
            t = item.get("type", "")
            if t == "message" and item.get("role") == "assistant":
                return True
            if t == "function_call":
                return True
            if t == "reasoning":
                return True
    return False


def _merge_previous_response_into_input(
    body: dict[str, Any], prev: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    prev_output = prev.get("output", [])
    prev_input = prev.get("_input", prev.get("input", []))
    prev_instructions = prev.get("_instructions")

    current_input = body.get("input", [])

    if _input_already_has_history(current_input):
        logger.info("[_merge] Current input already contains history, skipping merge")
        body = {**body}
        body.pop("previous_response_id", None)
        if not body.get("instructions") and prev_instructions:
            body["instructions"] = prev_instructions
        return body, False

    merged_input: list[Any] = []
    if isinstance(prev_input, list):
        merged_input.extend(prev_input)
    elif isinstance(prev_input, str):
        merged_input.append(prev_input)

    for item in prev_output:
        if isinstance(item, dict):
            item_type = item.get("type", "")
            if item_type == "message":
                merged_input.append({
                    "type": "message",
                    "role": item.get("role", "assistant"),
                    "content": item.get("content", []),
                })
            elif item_type == "function_call":
                merged_input.append({
                    "type": "function_call",
                    "call_id": item.get("call_id", ""),
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments", ""),
                })
            elif item_type == "reasoning":
                merged_input.append({
                    "type": "reasoning",
                    "id": item.get("id"),
                    "summary": item.get("summary", []),
                    "encrypted_content": item.get("encrypted_content"),
                })

    if isinstance(current_input, list):
        merged_input.extend(current_input)
    elif isinstance(current_input, str):
        merged_input.append({"type": "message", "role": "user", "content": current_input})

    body = {**body, "input": merged_input}
    body.pop("previous_response_id", None)
    if not body.get("instructions") and prev_instructions:
        body["instructions"] = prev_instructions
    return body, True


def _anthropic_sse(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _anthropic_message_start(msg_id: str, model: str) -> str:
    return _anthropic_sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )


def _anthropic_content_block_start(index: int = 0) -> str:
    return _anthropic_sse(
        "content_block_start",
        {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}},
    )


def _anthropic_text_delta(text: str, index: int = 0) -> str:
    return _anthropic_sse(
        "content_block_delta",
        {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": text}},
    )


def _anthropic_content_block_stop(index: int = 0) -> str:
    return _anthropic_sse("content_block_stop", {"type": "content_block_stop", "index": index})


def _anthropic_message_delta(stop_reason: str) -> str:
    return _anthropic_sse(
        "message_delta",
        {"type": "message_delta", "delta": {"stop_reason": stop_reason}, "usage": {"output_tokens": 0}},
    )


def _anthropic_message_stop() -> str:
    return _anthropic_sse("message_stop", {"type": "message_stop"})


def create_app(config: ProxyConfig | None = None) -> FastAPI:
    if config is None:
        config = load_config()

    app = FastAPI(
        title="Codex-Cool Proxy",
        description="Forwarding proxy for Claude Code and Codex CLI with protocol conversion",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    router = ProxyRouter(config)

    app.state.config = config
    app.state.router = router
    app.state.start_time = time.time()

    app.include_router(api_router)

    @app.on_event("shutdown")
    async def shutdown():
        await router.close()

    @app.get("/health")
    async def health():
        return {"status": "ok", "providers": list(router.providers.keys())}

    @app.get("/v1/models")
    async def list_models(request: Request):
        from codex_cool.injector import CLAUDE_MODEL_ALIASES
        ua = request.headers.get("user-agent", "")
        is_claude_desktop = "claude" in ua.lower() or "anthropic" in ua.lower()
        models = []
        if is_claude_desktop:
            for alias in CLAUDE_MODEL_ALIASES:
                models.append({"id": alias, "object": "model", "owned_by": "anthropic"})
        else:
            for p in router.providers.values():
                if p.models:
                    for alias, real in p.models.items():
                        models.append({"id": alias, "object": "model", "owned_by": p.name})
                else:
                    models.append({"id": "default", "object": "model", "owned_by": p.name})
        return {"object": "list", "data": models}

    @app.post("/v1/responses")
    async def responses_endpoint(request: Request):
        try:
            return await _responses_endpoint_inner(request)
        except Exception as e:
            logger.exception("[/v1/responses] Unhandled error: %s", e)
            return JSONResponse(content={"error": str(e)}, status_code=502)

    async def _responses_endpoint_inner(request: Request):
        body = await request.json()
        is_stream = body.get("stream", False)
        model = body.get("model", "")
        original_headers = dict(request.headers)

        body_json_size = len(json.dumps(body, ensure_ascii=False))
        logger.info("[/v1/responses] INCOMING REQUEST: model=%s stream=%s body_size=%d bytes prev_response_id=%s", model, is_stream, body_json_size, body.get("previous_response_id"))

        prev_id = body.get("previous_response_id")
        original_input = body.get("input")
        original_instructions = body.get("instructions")
        original_input_count = len(original_input) if isinstance(original_input, list) else 1
        did_merge = False
        if prev_id:
            prev = _get_previous_response(prev_id)
            if prev:
                logger.info("[/v1/responses] Merging previous_response_id=%s (prev_input_count=%d)", prev_id, len(prev.get("_input", prev.get("input", []))) if isinstance(prev.get("_input", prev.get("input", [])), list) else 1)
                body, did_merge = _merge_previous_response_into_input(body, prev)
                logger.info("[/v1/responses] Merge result: did_merge=%s, original_input_count=%d, merged_input_count=%d", did_merge, original_input_count, len(body.get("input", [])) if isinstance(body.get("input"), list) else 1)
            else:
                logger.warning("[/v1/responses] previous_response_id=%s not found in store", prev_id)

        store_input = body.get("input") if did_merge else original_input
        store_instructions = body.get("instructions") if did_merge else original_instructions

        logger.info("[/v1/responses] model=%s stream=%s body_keys=%s prev_id=%s input_items=%d", model, is_stream, list(body.keys()), prev_id, len(body.get("input", [])) if isinstance(body.get("input"), list) else 1)
        logger.debug("[/v1/responses] full body: %s", json.dumps(body, ensure_ascii=False)[:5000])

        providers = router.resolve_provider("responses", model)
        if not providers:
            return JSONResponse(content={"error": "No available provider"}, status_code=503)

        provider = providers[0]
        real_model = _resolve_model(provider, model)

        if provider.api_format == "responses":
            body = {**body, "model": real_model}
            url = router.get_upstream_url(provider, "responses")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, body, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err
            if is_stream:
                return StreamingResponse(
                    _passthrough_stream(resp, real_model, input_data=store_input, instructions=store_instructions),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                resp_content = _patch_model_in_response(resp.content, real_model)
                try:
                    _store_response(json.loads(resp_content), input_data=store_input, instructions=store_instructions)
                except Exception:
                    pass
                return Response(content=resp_content, status_code=resp.status_code, media_type="application/json")

        elif provider.api_format == "chat":
            from codex_cool.models.responses import ResponsesRequest

            try:
                req = ResponsesRequest(**body)
                chat_req = responses_request_to_chat_request(req)
                chat_payload = chat_req.model_dump(exclude_none=True, mode="json")
            except Exception as e:
                logger.warning("[/v1/responses] ResponsesRequest parse failed: %s, falling back", e)
                chat_payload = _responses_body_to_chat_body(body)

            if chat_payload.get("messages"):
                for msg in chat_payload["messages"]:
                    if msg.get("role") == "developer":
                        msg["role"] = "system"

            chat_payload["model"] = real_model

            _ensure_reasoning_content(chat_payload.get("messages", []))

            _sanitize_chat_messages(chat_payload.get("messages", []))

            fwd_size = len(json.dumps(chat_payload, ensure_ascii=False))
            logger.info("[/v1/responses→chat] FORWARDING: model=%s msgs=%d payload_size=%d bytes", real_model, len(chat_payload.get("messages", [])), fwd_size)

            url = router.get_upstream_url(provider, "responses")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, chat_payload, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err

            if is_stream:
                return StreamingResponse(
                    _chat_to_responses_stream(resp, real_model, input_data=store_input, instructions=store_instructions),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                from codex_cool.models.chat import ChatCompletionResponse

                chat_resp = ChatCompletionResponse(**resp.json())
                responses_resp = chat_response_to_responses_response(chat_resp, real_model)
                resp_data = responses_resp.model_dump(exclude_none=True, mode="json")
                _store_response(resp_data, input_data=store_input, instructions=store_instructions)
                return JSONResponse(content=resp_data)

        elif provider.api_format == "anthropic":
            anthropic_payload = _responses_body_to_anthropic_body(body)
            anthropic_payload["model"] = real_model

            if body.get("reasoning") is not None:
                if "anthropic-beta" not in original_headers:
                    original_headers["anthropic-beta"] = "thinking-2025-04-15"

            url = router.get_upstream_url(provider, "responses")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, anthropic_payload, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err

            if is_stream:
                return StreamingResponse(
                    _anthropic_to_responses_stream(resp, real_model, input_data=store_input, instructions=store_instructions),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                from codex_cool.models.anthropic import AnthropicResponse
                from codex_cool.converters.anthropic_chat import anthropic_response_to_responses_response

                anthropic_resp = AnthropicResponse(**resp.json())
                responses_resp = anthropic_response_to_responses_response(anthropic_resp, real_model)
                resp_data = responses_resp.model_dump(exclude_none=True, mode="json")
                _store_response(resp_data, input_data=store_input, instructions=store_instructions)
                return JSONResponse(content=resp_data)

        return JSONResponse(content={"error": "Unsupported provider format"}, status_code=500)

    @app.post("/v1/chat/completions")
    async def chat_completions_endpoint(request: Request):
        body = await request.json()
        is_stream = body.get("stream", False)
        model = body.get("model", "")
        original_headers = dict(request.headers)

        providers = router.resolve_provider("chat", model)
        if not providers:
            return JSONResponse(content={"error": "No available provider"}, status_code=503)

        provider = providers[0]
        real_model = _resolve_model(provider, model)

        if provider.api_format == "chat":
            body = {**body, "model": real_model}
            url = router.get_upstream_url(provider, "chat")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, body, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err
            if is_stream:
                return StreamingResponse(
                    _passthrough_stream(resp, real_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                return Response(content=_patch_model_in_response(resp.content, real_model), status_code=resp.status_code, media_type="application/json")

        elif provider.api_format == "responses":
            from codex_cool.models.chat import ChatCompletionRequest

            try:
                chat_req = ChatCompletionRequest(**body)
            except Exception as e:
                return JSONResponse(content={"error": f"Invalid Chat request: {e}"}, status_code=400)

            resp_payload = _chat_request_to_responses_request_simple(chat_req, provider, real_model)

            url = router.get_upstream_url(provider, "chat")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, resp_payload, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err

            if is_stream:
                return StreamingResponse(
                    _responses_to_chat_stream(resp, real_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                from codex_cool.models.responses import ResponsesResponse

                responses_resp = ResponsesResponse(**resp.json())
                chat_resp = chat_response_to_responses_response(responses_resp, real_model)
                return JSONResponse(content=chat_resp.model_dump(exclude_none=True, mode="json"))

        elif provider.api_format == "anthropic":
            from codex_cool.models.chat import ChatCompletionRequest

            try:
                chat_req = ChatCompletionRequest(**body)
            except Exception as e:
                return JSONResponse(content={"error": f"Invalid Chat request: {e}"}, status_code=400)

            anthropic_req = _chat_request_to_anthropic_request(chat_req)
            anthropic_payload = anthropic_req.model_dump(exclude_none=True, mode="json")

            anthropic_payload["model"] = real_model

            url = router.get_upstream_url(provider, "chat")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, anthropic_payload, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err

            if is_stream:
                return StreamingResponse(
                    _anthropic_to_chat_stream(resp, real_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                from codex_cool.models.anthropic import AnthropicResponse

                anthropic_resp = AnthropicResponse(**resp.json())
                chat_resp = chat_response_to_anthropic_response(anthropic_resp, real_model)
                return JSONResponse(content=chat_resp.model_dump(exclude_none=True, mode="json"))

        return JSONResponse(content={"error": "Unsupported provider format"}, status_code=500)

    @app.post("/v1/messages")
    async def anthropic_messages_endpoint(request: Request):
        body = await request.json()
        is_stream = body.get("stream", False)
        model = body.get("model", "")
        original_headers = dict(request.headers)

        logger.info("[/v1/messages] model=%s stream=%s max_tokens=%s thinking=%s tools=%d body_keys=%s",
                     model, is_stream, body.get("max_tokens"), body.get("thinking"),
                     len(body.get("tools", [])), list(body.keys()))
        logger.debug("[/v1/messages] full body: %s", json.dumps(body, ensure_ascii=False)[:5000])

        providers = router.resolve_provider("anthropic", model)
        if not providers:
            return JSONResponse(content={"error": "No available provider"}, status_code=503)

        provider = providers[0]
        real_model = _resolve_model(provider, model)

        if provider.api_format == "anthropic":
            body = {**body, "model": real_model}
            url = router.get_upstream_url(provider, "anthropic")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, body, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err
            if is_stream:
                return StreamingResponse(
                    _passthrough_stream(resp, real_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                return Response(content=_patch_model_in_response(resp.content, real_model), status_code=resp.status_code, media_type="application/json")

        elif provider.api_format == "chat":
            from codex_cool.models.anthropic import AnthropicRequest

            try:
                anthropic_req = AnthropicRequest(**body)
            except Exception as e:
                return JSONResponse(content={"error": f"Invalid Anthropic request: {e}"}, status_code=400)

            chat_req = anthropic_request_to_chat_request(anthropic_req)
            chat_payload = chat_req.model_dump(exclude_none=True, mode="json")

            chat_payload["model"] = real_model

            _ensure_reasoning_content(chat_payload.get("messages", []))

            logger.info("[/v1/messages→chat] model=%s msgs=%d max_completion_tokens=%s stream=%s",
                         real_model, len(chat_payload.get("messages", [])),
                         chat_payload.get("max_completion_tokens"), is_stream)

            url = router.get_upstream_url(provider, "anthropic")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, chat_payload, is_stream)
            except Exception as e:
                logger.error("[/v1/messages→chat] forward_request failed: %s", e)
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                logger.warning("[/v1/messages→chat] upstream error: status=%s", resp.status_code)
                return err

            if is_stream:
                return StreamingResponse(
                    _chat_to_anthropic_stream(resp, real_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                from codex_cool.models.chat import ChatCompletionResponse

                chat_resp = ChatCompletionResponse(**resp.json())
                anthropic_resp = chat_response_to_anthropic_response(chat_resp, real_model)
                return JSONResponse(content=anthropic_resp.model_dump(exclude_none=True, mode="json"))

        elif provider.api_format == "responses":
            from codex_cool.models.anthropic import AnthropicRequest

            try:
                anthropic_req = AnthropicRequest(**body)
            except Exception as e:
                return JSONResponse(content={"error": f"Invalid Anthropic request: {e}"}, status_code=400)

            responses_req = anthropic_request_to_responses_request(anthropic_req)
            resp_payload = responses_req.model_dump(exclude_none=True, mode="json")

            resp_payload["model"] = real_model

            url = router.get_upstream_url(provider, "anthropic")
            headers = router.get_upstream_headers(provider, original_headers)
            try:
                resp = await router.forward_request(provider, url, headers, resp_payload, is_stream)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=502)
            err = await _handle_upstream_error(resp, is_stream)
            if err:
                return err

            if is_stream:
                return StreamingResponse(
                    _responses_to_anthropic_stream(resp, real_model),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                from codex_cool.models.responses import ResponsesResponse

                responses_resp = ResponsesResponse(**resp.json())
                anthropic_resp = responses_response_to_anthropic_response(responses_resp, real_model)
                return JSONResponse(content=anthropic_resp.model_dump(exclude_none=True, mode="json"))

        return JSONResponse(content={"error": "Unsupported provider format"}, status_code=500)

    @app.get("/")
    async def index():
        from fastapi.responses import FileResponse

        return FileResponse(FRONTEND_DIR / "index.html")

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    return app


async def _passthrough_stream(resp: httpx.Response, real_model: str | None = None, input_data: Any = None, instructions: str | None = None):
    if not real_model:
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
        return
    buffer = ""
    try:
        async for chunk in resp.aiter_bytes():
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buffer:
                event_str, buffer = buffer.split("\n\n", 1)
                if input_data is not None or instructions is not None:
                    _try_store_from_sse_event(event_str, input_data, instructions)
                yield (_replace_model_in_sse_event(event_str, real_model) + "\n\n").encode("utf-8")
        if buffer.strip():
            if input_data is not None or instructions is not None:
                _try_store_from_sse_event(buffer, input_data, instructions)
            yield _replace_model_in_sse_event(buffer, real_model).encode("utf-8")
    finally:
        await resp.aclose()


def _try_store_from_sse_event(event_str: str, input_data: Any, instructions: str | None) -> None:
    for line in event_str.split("\n"):
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            try:
                data = json.loads(line[6:])
                if isinstance(data, dict) and data.get("type") == "response.completed":
                    _store_response(data.get("response", {}), input_data=input_data, instructions=instructions)
                    return
            except (json.JSONDecodeError, KeyError):
                pass


def _replace_model_in_sse_event(event_str: str, real_model: str) -> str:
    lines = event_str.split("\n")
    new_lines = []
    for line in lines:
        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
            try:
                data = json.loads(line[6:])
                if isinstance(data, dict):
                    changed = False
                    if "model" in data:
                        data["model"] = real_model
                        changed = True
                    if "response" in data and isinstance(data["response"], dict) and "model" in data["response"]:
                        data["response"]["model"] = real_model
                        changed = True
                    if "message" in data and isinstance(data["message"], dict) and "model" in data["message"]:
                        data["message"]["model"] = real_model
                        changed = True
                    if changed:
                        line = "data: " + json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, KeyError):
                pass
        new_lines.append(line)
    return "\n".join(new_lines)


async def _chat_to_responses_stream(resp: httpx.Response, model: str, input_data: Any = None, instructions: str | None = None):
    state: dict[str, Any] = {"model": model}
    try:
        async for chunk in resp.aiter_bytes():
            text = chunk.decode("utf-8", errors="replace")
            for line in text.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    parsed = json.loads(data)
                    events = chat_stream_chunk_to_responses_events(parsed, state)
                    for event in events:
                        if isinstance(event, dict) and event.get("type") == "response.completed":
                            _store_response(event.get("response", {}), input_data=input_data, instructions=instructions)
                        yield format_sse_event(event)
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error("[_chat_to_responses_stream] Error processing chunk: %s", e)
                    continue
    except Exception as e:
        logger.error("[_chat_to_responses_stream] Stream error: %s", e)
    finally:
        await resp.aclose()


async def _anthropic_to_responses_stream(resp: httpx.Response, model: str, input_data: Any = None, instructions: str | None = None):
    try:
        async for event in transform_anthropic_sse_to_responses(resp.aiter_bytes(), model):
            if isinstance(event, dict) and event.get("type") == "response.completed":
                _store_response(event.get("response", {}), input_data=input_data, instructions=instructions)
            yield format_sse_event(event)
    finally:
        await resp.aclose()


async def _anthropic_to_chat_stream(resp: httpx.Response, model: str):
    try:
        async for chunk in transform_anthropic_sse_to_chat(resp.aiter_bytes(), model):
            yield format_sse_event(chunk)
        yield format_sse_event("[DONE]")
    finally:
        await resp.aclose()


async def _chat_to_anthropic_stream(resp: httpx.Response, model: str):
    import uuid

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    current_block_index = 0
    thinking_started = False
    thinking_ended = False
    text_started = False
    any_content_emitted = False
    stream_ended = False
    text_buffer = ""
    MIN_BUFFER_SIZE = 8

    def _flush_text():
        nonlocal text_buffer
        if not text_buffer:
            return
        buf = text_buffer
        text_buffer = ""
        return _anthropic_text_delta(buf, current_block_index)

    def _close_open_blocks_events():
        nonlocal thinking_started, thinking_ended, text_started, current_block_index
        events = []
        if thinking_started and not thinking_ended:
            thinking_ended = True
            events.append(_anthropic_content_block_stop(current_block_index))
            current_block_index += 1
        if text_started:
            flushed = _flush_text()
            if flushed:
                events.append(flushed)
            events.append(_anthropic_content_block_stop(current_block_index))
            current_block_index += 1
            text_started = False
        return events

    yield _anthropic_message_start(msg_id, model)

    try:
        async for chunk in resp.aiter_bytes():
            text = chunk.decode("utf-8", errors="replace")
            for line in text.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    parsed = json.loads(data)
                    choices = parsed.get("choices", [])
                    for choice in choices:
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        reasoning = delta.get("reasoning_content")
                        if reasoning:
                            if not thinking_started:
                                thinking_started = True
                                any_content_emitted = True
                                yield _anthropic_sse(
                                    "content_block_start",
                                    {
                                        "type": "content_block_start",
                                        "index": current_block_index,
                                        "content_block": {"type": "thinking", "thinking": ""},
                                    },
                                )
                            yield _anthropic_sse(
                                "content_block_delta",
                                {
                                    "type": "content_block_delta",
                                    "index": current_block_index,
                                    "delta": {"type": "thinking_delta", "thinking": reasoning},
                                },
                            )

                        content = delta.get("content")
                        if content:
                            if not text_started:
                                for evt in _close_open_blocks_events():
                                    yield evt
                                text_started = True
                                any_content_emitted = True
                                yield _anthropic_sse(
                                    "content_block_start",
                                    {
                                        "type": "content_block_start",
                                        "index": current_block_index,
                                        "content_block": {"type": "text", "text": ""},
                                    },
                                )
                            text_buffer += content
                            if len(text_buffer) >= MIN_BUFFER_SIZE:
                                flushed = _flush_text()
                                if flushed:
                                    yield flushed

                        tool_calls = delta.get("tool_calls")
                        if tool_calls:
                            for evt in _close_open_blocks_events():
                                yield evt
                            for tc in tool_calls:
                                tc_id = tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}")
                                tc_function = tc.get("function", {})
                                tc_name = tc_function.get("name", "")
                                tc_args = tc_function.get("arguments", "")
                                any_content_emitted = True
                                yield _anthropic_sse(
                                    "content_block_start",
                                    {
                                        "type": "content_block_start",
                                        "index": current_block_index,
                                        "content_block": {
                                            "type": "tool_use",
                                            "id": tc_id,
                                            "name": tc_name,
                                            "input": {},
                                        },
                                    },
                                )
                                if tc_args:
                                    yield _anthropic_sse(
                                        "content_block_delta",
                                        {
                                            "type": "content_block_delta",
                                            "index": current_block_index,
                                            "delta": {
                                                "type": "input_json_delta",
                                                "partial_json": tc_args,
                                            },
                                        },
                                    )
                                yield _anthropic_content_block_stop(current_block_index)
                                current_block_index += 1

                        if finish_reason:
                            for evt in _close_open_blocks_events():
                                yield evt
                            if not any_content_emitted:
                                yield _anthropic_content_block_start(current_block_index)
                                yield _anthropic_content_block_stop(current_block_index)
                            stop_reason = "end_turn"
                            if finish_reason == "tool_calls":
                                stop_reason = "tool_use"
                            elif finish_reason == "length":
                                stop_reason = "max_tokens"
                            yield _anthropic_message_delta(stop_reason)
                            yield _anthropic_message_stop()
                            stream_ended = True

                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error("[_chat_to_anthropic_stream] Stream error: %s", e)
    finally:
        if not stream_ended:
            for evt in _close_open_blocks_events():
                yield evt
            if not any_content_emitted:
                yield _anthropic_content_block_start(current_block_index)
                yield _anthropic_content_block_stop(current_block_index)
            yield _anthropic_message_delta("end_turn")
            yield _anthropic_message_stop()
        await resp.aclose()


async def _responses_to_chat_stream(resp: httpx.Response, model: str):
    import uuid

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    msg_started = False

    try:
        async for event in parse_sse_stream(resp.aiter_bytes()):
            event_type = event.get("type", "")

            if event_type == "response.output_text.delta":
                if not msg_started:
                    msg_started = True
                    yield format_sse_event(
                        {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "model": model,
                            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                        }
                    )
                delta = event.get("delta", "")
                yield format_sse_event(
                    {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                    }
                )

            elif event_type == "response.function_call_arguments.delta":
                if not msg_started:
                    msg_started = True
                    yield format_sse_event(
                        {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "model": model,
                            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                        }
                    )
                delta = event.get("delta", "")
                item_id = event.get("item_id", "")
                yield format_sse_event(
                    {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": item_id,
                                            "type": "function",
                                            "function": {"name": "", "arguments": delta},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                )

            elif event_type == "response.completed":
                finish_reason = "stop"
                response_data = event.get("response", {})
                for item in response_data.get("output", []):
                    if item.get("type") == "function_call":
                        finish_reason = "tool_calls"
                        break
                yield format_sse_event(
                    {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
                    }
                )
                yield format_sse_event("[DONE]")

    finally:
        await resp.aclose()


async def _responses_to_anthropic_stream(resp: httpx.Response, model: str):
    import uuid

    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    current_block_index = 0
    thinking_started = False
    thinking_ended = False
    text_started = False

    yield _anthropic_message_start(msg_id, model)

    try:
        async for event in parse_sse_stream(resp.aiter_bytes()):
            event_type = event.get("type", "")

            if event_type == "response.output_item.added":
                item = event.get("item", {})
                if item.get("type") == "reasoning":
                    thinking_started = True
                    yield _anthropic_sse(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": current_block_index,
                            "content_block": {"type": "thinking", "thinking": ""},
                        },
                    )
                    summary = item.get("summary", [])
                    for s in summary:
                        thinking_text = ""
                        if isinstance(s, dict):
                            thinking_text = s.get("text", "")
                        elif isinstance(s, str):
                            thinking_text = s
                        if thinking_text:
                            yield _anthropic_sse(
                                "content_block_delta",
                                {
                                    "type": "content_block_delta",
                                    "index": current_block_index,
                                    "delta": {"type": "thinking_delta", "thinking": thinking_text},
                                },
                            )

            elif event_type == "response.reasoning_summary_text.delta":
                if thinking_started and not thinking_ended:
                    delta = event.get("delta", "")
                    if delta:
                        yield _anthropic_sse(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": current_block_index,
                                "delta": {"type": "thinking_delta", "thinking": delta},
                            },
                        )

            elif event_type == "response.output_text.delta":
                if thinking_started and not thinking_ended:
                    thinking_ended = True
                    yield _anthropic_content_block_stop(current_block_index)
                    current_block_index += 1
                if not text_started:
                    text_started = True
                    yield _anthropic_sse(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": current_block_index,
                            "content_block": {"type": "text", "text": ""},
                        },
                    )
                delta = event.get("delta", "")
                yield _anthropic_text_delta(delta, current_block_index)

            elif event_type == "response.completed":
                if thinking_started and not thinking_ended:
                    yield _anthropic_content_block_stop(current_block_index)
                    current_block_index += 1
                if text_started:
                    yield _anthropic_content_block_stop(current_block_index)
                response_data = event.get("response", {})
                stop_reason = "end_turn"
                for item in response_data.get("output", []):
                    if item.get("type") == "function_call":
                        stop_reason = "tool_use"
                        break
                yield _anthropic_message_delta(stop_reason)
                yield _anthropic_message_stop()

    finally:
        await resp.aclose()


def _resolve_model(provider, model: str) -> str:
    if provider.models and model in provider.models:
        real = provider.models[model]
        if real != model:
            logger.info("Model resolved: %s -> %s (provider: %s)", model, real, provider.name)
        return real
    if provider.models:
        real = list(provider.models.values())[0]
        logger.info("Model fallback: %s -> %s (provider: %s, first available)", model, real, provider.name)
        return real
    return model


async def _handle_upstream_error(resp: httpx.Response, is_stream: bool = False):
    if resp.status_code < 400:
        return None

    if is_stream:
        try:
            body = await resp.aread()
            try:
                error_body = json.loads(body)
            except Exception:
                error_body = {"error": body.decode("utf-8", errors="replace")[:500]}
        except Exception:
            error_body = {"error": f"Upstream HTTP {resp.status_code} (stream read failed)"}
        finally:
            await resp.aclose()
    else:
        if resp.status_code >= 500:
            return JSONResponse(content={"error": f"Upstream server error: HTTP {resp.status_code}"}, status_code=502)
        try:
            error_body = resp.json()
        except Exception:
            error_body = {"error": resp.text[:500]}

    if resp.status_code >= 500:
        return JSONResponse(content=error_body, status_code=502)
    return JSONResponse(content=error_body, status_code=resp.status_code)


def _patch_model_in_response(content: bytes, real_model: str) -> bytes:
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "model" in data:
            data["model"] = real_model
            return json.dumps(data, ensure_ascii=False).encode("utf-8")
    except Exception:
        pass
    return content


def _extract_text_from_content(raw_content: Any) -> str:
    if isinstance(raw_content, str):
        return raw_content
    if isinstance(raw_content, list):
        parts = []
        for c in raw_content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                t = c.get("type", "")
                if t == "input_image" or t == "image_url":
                    parts.append("[image]")
                elif t == "input_file" or t == "file":
                    parts.append("[file]")
                elif "text" in c:
                    parts.append(c["text"])
                else:
                    parts.append("")
            elif hasattr(c, "text"):
                parts.append(c.text)
        return "\n".join(parts)
    return str(raw_content) if raw_content is not None else ""


def _responses_body_to_chat_body(body: dict[str, Any]) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []

    instructions = body.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    raw_input = body.get("input", "")
    if isinstance(raw_input, str):
        messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        pending_reasoning = ""
        pending_tool_calls: list[dict[str, Any]] = []

        def _flush_tc():
            nonlocal pending_reasoning, pending_tool_calls
            if not pending_tool_calls:
                return
            if messages and messages[-1].get("role") == "assistant":
                last = messages[-1]
                last["tool_calls"] = (last.get("tool_calls") or []) + pending_tool_calls
                if pending_reasoning and not last.get("reasoning_content"):
                    last["reasoning_content"] = pending_reasoning
                    pending_reasoning = ""
            else:
                msg: dict[str, Any] = {"role": "assistant", "content": None, "tool_calls": pending_tool_calls}
                if pending_reasoning:
                    msg["reasoning_content"] = pending_reasoning
                    pending_reasoning = ""
                messages.append(msg)
            pending_tool_calls = []

        for item in raw_input:
            if isinstance(item, str):
                _flush_tc()
                messages.append({"role": "user", "content": item})
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "message":
                    _flush_tc()
                    role = item.get("role", "user")
                    content = _extract_text_from_content(item.get("content", ""))
                    if role == "assistant":
                        msg = {"role": "assistant"}
                        if pending_reasoning:
                            msg["reasoning_content"] = pending_reasoning
                            pending_reasoning = ""
                        if item.get("content") is not None:
                            msg["content"] = content
                        else:
                            msg["content"] = None
                        messages.append(msg)
                    else:
                        messages.append({"role": role, "content": content})
                elif item_type == "function_call_output":
                    _flush_tc()
                    messages.append(
                        {"role": "tool", "content": item.get("output", ""), "tool_call_id": item.get("call_id", "")}
                    )
                elif item_type == "function_call":
                    pending_tool_calls.append(
                        {
                            "id": item.get("call_id", ""),
                            "type": "function",
                            "function": {
                                "name": item.get("name", ""),
                                "arguments": item.get("arguments", ""),
                            },
                        }
                    )
                elif item_type == "reasoning":
                    summary = item.get("summary", [])
                    reasoning_text = ""
                    for s in summary:
                        if isinstance(s, dict):
                            reasoning_text += s.get("text", "") + "\n"
                        elif isinstance(s, str):
                            reasoning_text += s + "\n"
                    if reasoning_text.strip():
                        pending_reasoning += reasoning_text.strip()

        _flush_tc()

    tools = None
    raw_tools = body.get("tools")
    if raw_tools:
        chat_tools = []
        for tool in raw_tools:
            if isinstance(tool, dict) and tool.get("type") == "function":
                chat_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name", ""),
                            "description": tool.get("description"),
                            "parameters": tool.get("parameters"),
                            "strict": tool.get("strict"),
                        },
                    }
                )
        if chat_tools:
            tools = chat_tools

    payload: dict[str, Any] = {
        "model": body.get("model", ""),
        "messages": messages,
        "stream": body.get("stream", False),
    }
    if tools:
        payload["tools"] = tools
    tool_choice = body.get("tool_choice")
    if tool_choice is not None:
        if isinstance(tool_choice, str):
            payload["tool_choice"] = tool_choice
        elif isinstance(tool_choice, dict):
            tc_type = tool_choice.get("type", "")
            if tc_type == "function":
                payload["tool_choice"] = {"type": "function", "function": {"name": tool_choice.get("name", "")}}
            else:
                payload["tool_choice"] = tc_type
    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        payload["top_p"] = body["top_p"]
    if body.get("max_output_tokens") is not None:
        payload["max_completion_tokens"] = body["max_output_tokens"]

    return payload


def _responses_body_to_anthropic_body(body: dict[str, Any]) -> dict[str, Any]:
    anthropic_messages: list[dict[str, Any]] = []
    system = None

    instructions = body.get("instructions")
    if instructions:
        system = instructions

    raw_input = body.get("input", "")
    if isinstance(raw_input, str):
        anthropic_messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        for item in raw_input:
            if isinstance(item, str):
                anthropic_messages.append({"role": "user", "content": item})
            elif isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "message":
                    role = item.get("role", "user")
                    content = _extract_text_from_content(item.get("content", ""))
                    anthropic_messages.append({"role": role, "content": content})
                elif item_type == "function_call_output":
                    anthropic_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": item.get("call_id", ""),
                                    "content": item.get("output", ""),
                                }
                            ],
                        }
                    )
                elif item_type == "function_call":
                    try:
                        inp = json.loads(item.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        inp = {"raw_arguments": item.get("arguments", "")}
                    anthropic_messages.append(
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": item.get("call_id", ""),
                                    "name": item.get("name", ""),
                                    "input": inp,
                                }
                            ],
                        }
                    )
                elif item_type == "reasoning":
                    summary = item.get("summary", [])
                    reasoning_text = ""
                    for s in summary:
                        if isinstance(s, dict):
                            reasoning_text += s.get("text", "") + "\n"
                        elif isinstance(s, str):
                            reasoning_text += s + "\n"
                    if reasoning_text.strip():
                        if anthropic_messages and anthropic_messages[-1].get("role") == "assistant":
                            last_content = anthropic_messages[-1].get("content", [])
                            if isinstance(last_content, list):
                                last_content.insert(0, {"type": "thinking", "thinking": reasoning_text.strip()})

    tools = None
    raw_tools = body.get("tools")
    if raw_tools:
        a_tools = []
        for tool in raw_tools:
            if isinstance(tool, dict) and tool.get("type") == "function":
                a_tools.append(
                    {
                        "name": tool.get("name", ""),
                        "description": tool.get("description"),
                        "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
        if a_tools:
            tools = a_tools

    payload: dict[str, Any] = {
        "model": body.get("model", ""),
        "messages": anthropic_messages,
        "max_tokens": body.get("max_output_tokens", 4096),
        "stream": body.get("stream", False),
    }
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = tools
    tool_choice = body.get("tool_choice")
    if tool_choice is not None:
        if isinstance(tool_choice, str):
            payload["tool_choice"] = tool_choice
        elif isinstance(tool_choice, dict):
            tc_type = tool_choice.get("type", "")
            if tc_type == "function":
                payload["tool_choice"] = {"type": "tool", "name": tool_choice.get("name", "")}
            else:
                payload["tool_choice"] = tc_type
    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        payload["top_p"] = body["top_p"]

    reasoning = body.get("reasoning")
    if reasoning is not None:
        if isinstance(reasoning, dict):
            effort = reasoning.get("effort", "high")
            budget_map = {"low": 5000, "medium": 10000, "high": 32000}
            budget = reasoning.get("budget_tokens", budget_map.get(effort, 10000))
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        elif isinstance(reasoning, str):
            budget_map = {"low": 5000, "medium": 10000, "high": 32000}
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget_map.get(reasoning, 10000)}

    return payload


def _chat_request_to_responses_request_simple(
    chat_req, provider, model
) -> dict[str, Any]:
    messages = chat_req.messages
    instructions = None
    input_items = []

    for msg in messages:
        if msg.role == "system" or msg.role == "developer":
            if instructions is None:
                instructions = ""
            if isinstance(msg.content, str):
                instructions += msg.content + "\n"
            continue

        if isinstance(msg.content, str):
            input_items.append({"type": "message", "role": msg.role, "content": msg.content})
        elif msg.tool_calls:
            for tc in msg.tool_calls:
                input_items.append(
                    {
                        "type": "function_call",
                        "call_id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )
        elif msg.tool_call_id:
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": msg.tool_call_id,
                    "output": msg.content or "",
                }
            )

    tools = []
    if chat_req.tools:
        for tool in chat_req.tools:
            tools.append(
                {
                    "type": "function",
                    "name": tool.function.name,
                    "description": tool.function.description,
                    "parameters": tool.function.parameters,
                }
            )

    payload: dict[str, Any] = {
        "model": model,
        "input": input_items,
    }
    if instructions:
        payload["instructions"] = instructions.strip()
    if tools:
        payload["tools"] = tools
    if chat_req.stream:
        payload["stream"] = True
    if chat_req.temperature is not None:
        payload["temperature"] = chat_req.temperature
    if chat_req.top_p is not None:
        payload["top_p"] = chat_req.top_p
    if chat_req.max_completion_tokens is not None:
        payload["max_output_tokens"] = chat_req.max_completion_tokens
    elif chat_req.max_tokens is not None:
        payload["max_output_tokens"] = chat_req.max_tokens

    return payload


def _chat_request_to_anthropic_request(chat_req):
    from codex_cool.models.anthropic import (
        AnthropicMessage,
        AnthropicRequest,
        AnthropicTextBlock,
        AnthropicTool,
        AnthropicToolInputSchema,
        AnthropicToolResultBlock,
        AnthropicToolUseBlock,
    )

    system = None
    messages = []

    for msg in chat_req.messages:
        if msg.role in ("system", "developer"):
            if system is None:
                system = ""
            if isinstance(msg.content, str):
                system += msg.content + "\n"
            continue

        if msg.role == "assistant":
            content = []
            if msg.content:
                content.append(AnthropicTextBlock(type="text", text=msg.content))
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        inp = json.loads(tc.function.arguments)
                    except (json.JSONDecodeError, TypeError):
                        inp = {"raw_arguments": tc.function.arguments}
                    content.append(
                        AnthropicToolUseBlock(type="tool_use", id=tc.id, name=tc.function.name, input=inp)
                    )
            messages.append(AnthropicMessage(role="assistant", content=content))
        elif msg.role == "tool":
            messages.append(
                AnthropicMessage(
                    role="user",
                    content=[
                        AnthropicToolResultBlock(
                            type="tool_result",
                            tool_use_id=msg.tool_call_id or "",
                            content=msg.content or "",
                        )
                    ],
                )
            )
        elif msg.role == "user":
            if isinstance(msg.content, str):
                messages.append(AnthropicMessage(role="user", content=msg.content))

    tools = None
    if chat_req.tools:
        tools = []
        for tool in chat_req.tools:
            schema = tool.function.parameters or {}
            tools.append(
                AnthropicTool(
                    name=tool.function.name,
                    description=tool.function.description,
                    input_schema=AnthropicToolInputSchema(**schema) if schema else AnthropicToolInputSchema(),
                )
            )

    return AnthropicRequest(
        model=chat_req.model,
        messages=messages,
        system=system.strip() if system else None,
        tools=tools,
        stream=chat_req.stream,
        temperature=chat_req.temperature,
        top_p=chat_req.top_p,
        max_tokens=chat_req.max_completion_tokens or chat_req.max_tokens or 4096,
    )
