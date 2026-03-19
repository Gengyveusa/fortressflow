"""
Phase 7: Chat API — In-app AI assistant endpoint.

Routes:
  POST /chat/       — Streaming SSE chat endpoint
  POST /chat/sync   — Non-streaming chat (for testing)
  GET  /chat/history — Chat history for a session
"""

import logging
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.v1.leads import get_current_user  # reuse existing auth dependency
from app.schemas.chat import ChatHistoryResponse, ChatRequest, ChatResponse
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# ── Per-user in-memory rate limiting (sliding window) ────────────────────────
# Limit: 30 messages per user per minute

_CHAT_RATE_LIMIT = 30
_CHAT_RATE_WINDOW_SECONDS = 60

# user_id -> deque of timestamps
_chat_rate_buckets: dict[str, deque] = defaultdict(lambda: deque())


def _check_chat_rate_limit(user_id: str) -> None:
    """Raise 429 if user exceeds rate limit. Modifies bucket in place."""
    now = datetime.now(UTC).timestamp()
    bucket = _chat_rate_buckets[user_id]

    # Evict old timestamps outside the window
    while bucket and now - bucket[0] > _CHAT_RATE_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= _CHAT_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Chat rate limit exceeded. Max {_CHAT_RATE_LIMIT} messages per minute.",
        )

    bucket.append(now)


# ── Streaming endpoint ────────────────────────────────────────────────────────


@router.post("/", summary="Chat — streaming SSE")
async def chat_stream(
    request: Request,
    body: ChatRequest,
) -> StreamingResponse:
    """
    Stream a chat response as Server-Sent Events.

    Each chunk is prefixed with `data: ` and terminated with `\\n\\n`.
    A final `data: [DONE]\\n\\n` or `data: [ERROR]\\n\\n` signals completion.
    """
    # Try to get user_id from auth, fall back to anonymous
    user_id = "anonymous"
    try:
        # Attempt to extract auth from request headers
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # In production use proper JWT verification
            # For now use a placeholder
            user_id = "authenticated-user"
    except Exception:
        pass

    # Rate limiting
    _check_chat_rate_limit(user_id)

    # Determine session ID
    session_id = body.session_id or str(uuid.uuid4())
    svc = ChatService()

    async def event_stream():
        try:
            async for chunk in svc.handle_message(body.message, user_id, session_id):
                # Escape newlines in SSE data field
                safe_chunk = chunk.replace("\n", " ")
                yield f"data: {safe_chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("chat_stream: streaming error: %s", exc)
            yield "data: [ERROR]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Sync endpoint ─────────────────────────────────────────────────────────────


@router.post("/sync", response_model=ChatResponse, summary="Chat — synchronous")
async def chat_sync(
    body: ChatRequest,
) -> ChatResponse:
    """
    Non-streaming chat endpoint. Returns the full response at once.
    Useful for testing and slash commands.
    """
    session_id = body.session_id or str(uuid.uuid4())
    svc = ChatService()
    result = await svc.handle_message_sync(body.message, "anonymous", session_id)
    return ChatResponse(
        session_id=result["session_id"],
        message=result["message"],
        response=result["response"],
        ai_model=result["ai_model"],
        ai_sources=result["ai_sources"],
        created_at=datetime.now(UTC),
    )


# ── History endpoint ──────────────────────────────────────────────────────────


@router.get("/history", response_model=ChatHistoryResponse, summary="Chat history")
async def chat_history(
    session_id: str,
) -> ChatHistoryResponse:
    """
    Return chat history for a given session_id.
    """
    try:
        from app.database import AsyncSessionLocal
        from app.models.chat import ChatLog
        from app.schemas.chat import ChatHistoryItem
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ChatLog)
                .where(ChatLog.session_id == session_id)
                .order_by(ChatLog.created_at.desc())
                .limit(50)
            )
            logs = result.scalars().all()

            items = [
                ChatHistoryItem(
                    id=str(log.id),
                    message=log.message,
                    response=log.response,
                    ai_sources=log.ai_sources.get("sources", []) if log.ai_sources else [],
                    created_at=log.created_at,
                )
                for log in logs
            ]

            return ChatHistoryResponse(
                items=items,
                total=len(items),
                session_id=session_id,
            )

    except Exception as exc:
        logger.error("chat_history: DB error: %s", exc)
        # Return empty history instead of failing
        from app.schemas.chat import ChatHistoryItem
        return ChatHistoryResponse(items=[], total=0, session_id=session_id)
