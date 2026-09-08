"""
Chat completions + embeddings — OpenAI-compatible.

Routes requests to the correct backend based on the model registry.
"""
from __future__ import annotations

import logging

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
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id!r} not registered",
        )

    return m


# ── chat completions ──────────────────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_auth),
):
    log.info("Chat request received: model=%s stream=%s", req.model, req.stream)

    m = _get_model_or_404(req.model, db)

    log.info(
        "Model resolved: id=%s backend=%s status=%s",
        m.id,
        m.backend,
        m.status,
    )

    # Ensure model is loaded and mark this request as active.
    async with lifecycle.track_request(req.model):
        log.info("Lifecycle acquired: model=%s", req.model)

        body = req.model_dump(exclude_none=True)

        log.info(
            "Forwarding request: backend=%s model=%s",
            m.backend,
            req.model,
        )

        try:
            if m.backend == "llamaswap":
                resp = await ls_driver.proxy_chat(body)

            elif m.backend == "vllm":
                resp = await vllm_driver.proxy_chat(req.model, body)

            elif m.backend == "onnxruntime":
                text = " ".join(
                    msg["content"]
                    for msg in body.get("messages", [])
                    if isinstance(msg.get("content"), str)
                )

                resp = await onnx_driver.proxy_infer(
                    req.model,
                    {
                        "inputs": {
                            "input_text": [text],
                        }
                    },
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Backend {m.backend!r} does not support "
                        "chat completions"
                    ),
                )

        except HTTPException:
            raise

        except Exception as exc:
            log.exception(
                "Backend request failed: model=%s backend=%s",
                req.model,
                m.backend,
            )

            raise HTTPException(
                status_code=502,
                detail=f"Backend request failed: {exc}",
            ) from exc

        log.info(
            "Backend response received: status=%s model=%s",
            resp.status_code,
            req.model,
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.text,
            )

        if req.stream:
            log.info("Returning streaming response: model=%s", req.model)

            return StreamingResponse(
                resp.aiter_bytes(),
                media_type="text/event-stream",
            )

        log.info("Returning JSON response: model=%s", req.model)

        return resp.json()


# ── embeddings ────────────────────────────────────────────────────────────────

@router.post("/v1/embeddings")
async def embeddings(
    req: EmbeddingRequest,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_auth),
):
    log.info("Embedding request received: model=%s", req.model)

    m = _get_model_or_404(req.model, db)

    log.info(
        "Model resolved: id=%s backend=%s status=%s",
        m.id,
        m.backend,
        m.status,
    )

    async with lifecycle.track_request(req.model):
        log.info("Lifecycle acquired: model=%s", req.model)

        body = req.model_dump(exclude_none=True)

        try:
            if m.backend == "llamaswap":
                resp = await ls_driver.proxy_embeddings(body)

            elif m.backend == "vllm":
                resp = await vllm_driver.proxy_embeddings(
                    req.model,
                    body,
                )

            elif m.backend == "onnxruntime":
                inputs = (
                    req.input
                    if isinstance(req.input, list)
                    else [req.input]
                )

                resp = await onnx_driver.proxy_infer(
                    req.model,
                    {
                        "inputs": {
                            "input_text": inputs,
                        }
                    },
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Backend {m.backend!r} does not support "
                        "embeddings"
                    ),
                )

        except HTTPException:
            raise

        except Exception as exc:
            log.exception(
                "Embedding backend request failed: model=%s backend=%s",
                req.model,
                m.backend,
            )

            raise HTTPException(
                status_code=502,
                detail=f"Backend request failed: {exc}",
            ) from exc

        log.info(
            "Embedding backend response received: status=%s model=%s",
            resp.status_code,
            req.model,
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.text,
            )

        return resp.json()