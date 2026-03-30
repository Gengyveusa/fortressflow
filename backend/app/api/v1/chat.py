"""
Phase 7+8: Chat API — In-app AI assistant with command engine.

Routes:
  POST /chat/          — Streaming SSE chat endpoint
  POST /chat/sync      — Synchronous chat (returns structured CommandResponse)
  GET  /chat/history   — Chat history for a session
  GET  /chat/sessions  — List chat sessions
  GET  /chat/sessions/{session_id} — Get messages for a session
  POST /chat/sessions  — Create a new session
"""

import logging
import time
import uuid
from datetime import UTC, datetime
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.chat import ChatLog
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    CommandResponse,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# ── Redis-backed per-user chat rate limiting (sliding window) ────────────────
_CHAT_RATE_LIMIT = 20  # messages per minute per user
_CHAT_RATE_WINDOW_SECONDS = 60

_chat_redis: aioredis.Redis | None = None


async def _get_chat_redis() -> aioredis.Redis | None:
    """Lazy singleton Redis client for chat rate limiting."""
    global _chat_redis
    if _chat_redis is not None:
        try:
            await _chat_redis.ping()
            return _chat_redis
        except Exception:
            _chat_redis = None

    try:
        _chat_redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=0.5,
        )
        await _chat_redis.ping()
        return _chat_redis
    except Exception as exc:
        logger.warning("Redis unavailable for chat rate limiting: %s", exc)
        _chat_redis = None
        return None


async def _check_chat_rate_limit(user_id: str) -> None:
    """Raise 429 if user exceeds chat rate limit. Uses Redis sliding window."""
    r = await _get_chat_redis()
    if r is None:
        # Fail open if Redis is unavailable
        return

    key = f"chat_rate:{user_id}"
    now = time.time()
    window_start = now - _CHAT_RATE_WINDOW_SECONDS
    member = f"{now:.6f}"

    try:
        async with r.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zcard(key)
            pipe.zadd(key, {member: now})
            pipe.expire(key, _CHAT_RATE_WINDOW_SECONDS + 10)
            results = await pipe.execute()

        count = results[1]
        if count >= _CHAT_RATE_LIMIT:
            await r.zrem(key, member)
            raise HTTPException(
                status_code=429,
                detail=f"Chat rate limit exceeded. Max {_CHAT_RATE_LIMIT} messages per minute.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Chat rate limit check failed, allowing request: %s", exc)


# ── Streaming endpoint ────────────────────────────────────────────────────────


@router.post("/", summary="Chat — streaming SSE")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream a chat response as Server-Sent Events.

    Each chunk is prefixed with `data: ` and terminated with `\\n\\n`.
    Command engine responses are prefixed with `data: [CMD]` followed by JSON.
    A final `data: [DONE]\\n\\n` or `data: [ERROR]\\n\\n` signals completion.
    """
    user_id = str(current_user.id)

    # Rate limiting
    await _check_chat_rate_limit(user_id)

    # Determine session ID
    session_id = body.session_id or str(uuid.uuid4())
    svc = ChatService()

    async def event_stream():
        try:
            async for chunk in svc.handle_message(body.message, user_id, session_id):
                if chunk.startswith("[CMD]"):
                    # Structured command engine response — pass through as-is
                    yield f"data: {chunk}\n\n"
                else:
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


@router.post("/sync", response_model=CommandResponse, summary="Chat — synchronous")
async def chat_sync(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> CommandResponse:
    """
    Non-streaming chat endpoint. Returns the full response at once.

    Returns a CommandResponse which supports all response types:
    text, question, action_preview, progress, metrics.
    """
    session_id = body.session_id or str(uuid.uuid4())
    svc = ChatService()
    result = await svc.handle_message_sync(body.message, str(current_user.id), session_id)
    return CommandResponse(
        session_id=result.get("session_id", session_id),
        type=result.get("type", "text"),
        content=result.get("response", ""),
        options=result.get("options", []),
        data=result.get("data", {}),
        campaign_params=result.get("campaign_params", {}),
        ai_model=result.get("ai_model", "groq"),
        ai_sources=result.get("ai_sources", []),
        created_at=datetime.now(UTC),
    )


# ── History endpoint ──────────────────────────────────────────────────────────


@router.get("/history", response_model=ChatHistoryResponse, summary="Chat history")
async def chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
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
                .where(
                    ChatLog.session_id == session_id,
                    ChatLog.user_id == str(current_user.id),
                )
                .order_by(ChatLog.created_at.desc())
                .limit(50)
            )
            logs = result.scalars().all()

            items = [
                ChatHistoryItem(
                    id=str(log.id),
                    message=log.message,
                    response=log.response,
                    response_type=log.response_type or "text",
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


# ── Session management endpoints ─────────────────────────────────────────────


@router.get("/sessions", summary="List chat sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all distinct chat sessions with their latest message timestamp."""
    result = await db.execute(
        select(
            ChatLog.session_id,
            func.min(ChatLog.created_at).label("started_at"),
            func.max(ChatLog.created_at).label("last_message_at"),
            func.count(ChatLog.id).label("message_count"),
        )
        .where(ChatLog.user_id == str(current_user.id))
        .group_by(ChatLog.session_id)
        .order_by(func.max(ChatLog.created_at).desc())
        .limit(50)
    )
    rows = result.all()

    sessions = [
        {
            "session_id": row.session_id,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
            "message_count": row.message_count,
        }
        for row in rows
    ]
    return {"sessions": sessions}


@router.get("/sessions/{session_id}", summary="Get session messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get all messages for a specific chat session."""
    result = await db.execute(
        select(ChatLog)
        .where(
            ChatLog.session_id == session_id,
            ChatLog.user_id == str(current_user.id),
        )
        .order_by(ChatLog.created_at.asc())
        .limit(200)
    )
    logs = result.scalars().all()

    if not logs:
        # Check if session exists but belongs to another user
        exists_result = await db.execute(
            select(ChatLog.id).where(ChatLog.session_id == session_id).limit(1)
        )
        if exists_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=404, detail="Session not found")

    messages = []
    for log in logs:
        messages.append({
            "id": str(log.id),
            "role": "user",
            "content": log.message,
            "timestamp": log.created_at.isoformat(),
        })
        response_entry = {
            "id": f"{log.id}-response",
            "role": "assistant",
            "content": log.response,
            "timestamp": log.created_at.isoformat(),
            "sources": log.ai_sources.get("sources", []) if log.ai_sources else [],
            "type": log.response_type or "text",
        }
        if log.response_metadata:
            response_entry["data"] = log.response_metadata
        messages.append(response_entry)

    return {"session_id": session_id, "messages": messages}


@router.post("/sessions", summary="Create a new session")
async def create_session(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}
