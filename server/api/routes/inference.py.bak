"""
Chat completions + embeddings — OpenAI-compatible.
Routes to the correct backend based on the model registry.
"""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from server.backends import llamaswap as ls_driver
from server.backends import vllm_driver, onnx_driver
from server.core.auth import require_auth
from server.core.lifecycle import lifecycle
from server.core.schemas import ChatCompletionRequest, EmbeddingRequest
from server.db import ApiKey, ModelRecord, get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["inference"])


def _get_model_or_404(model_id: str, db: Session) -> ModelRecord:
    m = db.query(ModelRecord).filter(ModelRecord.id == model_id).first()
    if m is None:
        raise HTTPException(404, f"Model {model_id!r} not registered")
    return m


# ── chat completions ──────────────────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_auth),
):
    m = _get_model_or_404(req.model, db)

    async with lifecycle.track_request(req.model):
        body = req.model_dump(exclude_none=True)

        if m.backend == "llamaswap":
            resp = await ls_driver.proxy_chat(body)
        elif m.backend == "vllm":
            resp = await vllm_driver.proxy_chat(req.model, body)
        elif m.backend == "onnxruntime":
            # ONNX text models: convert chat format to raw input
            text = " ".join(msg["content"] for msg in body.get("messages", []) if isinstance(msg.get("content"), str))
            resp = await onnx_driver.proxy_infer(req.model, {"inputs": {"input_text": [text]}})
        else:
            raise HTTPException(400, f"Backend {m.backend!r} does not support chat completions")

        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)

        if req.stream:
            return StreamingResponse(resp.aiter_bytes(), media_type="text/event-stream")

        return resp.json()


# ── embeddings ────────────────────────────────────────────────────────────────

@router.post("/v1/embeddings")
async def embeddings(
    req: EmbeddingRequest,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_auth),
):
    m = _get_model_or_404(req.model, db)

    async with lifecycle.track_request(req.model):
        body = req.model_dump(exclude_none=True)

        if m.backend == "llamaswap":
            resp = await ls_driver.proxy_embeddings(body)
        elif m.backend == "vllm":
            resp = await vllm_driver.proxy_embeddings(req.model, body)
        elif m.backend == "onnxruntime":
            inputs = req.input if isinstance(req.input, list) else [req.input]
            resp = await onnx_driver.proxy_infer(req.model, {"inputs": {"input_text": inputs}})
        else:
            raise HTTPException(400, f"Backend {m.backend!r} does not support embeddings")

        if resp.status_code != 200:
            raise HTTPException(resp.status_code, resp.text)

        return resp.json()
