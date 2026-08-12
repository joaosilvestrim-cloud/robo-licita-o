from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import httpx

from app.database import get_session
from app.db.models import ChatMessage, User
from app.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    messages: List[dict] = []  # recent history for context


class ChatResponse(BaseModel):
    content: str


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Save user message
    user_msg = ChatMessage(
        tenant_id=user.tenant_id,
        user_id=user.id,
        role="user",
        content=body.message,
    )
    session.add(user_msg)
    await session.flush()

    # Call hermes-procurement
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.hermes_procurement_url}/chat",
                json={"message": body.message, "tenant_id": user.tenant_id},
            )
            resp.raise_for_status()
            result = resp.json()
            content = result.get("response", "Não consegui processar sua mensagem.")
    except Exception as e:
        content = "Estou com dificuldades técnicas no momento. Tente novamente em instantes."

    # Save assistant message
    asst_msg = ChatMessage(
        tenant_id=user.tenant_id,
        user_id=user.id,
        role="assistant",
        content=content,
    )
    session.add(asst_msg)
    await session.commit()

    return ChatResponse(content=content)


@router.get("/history")
async def chat_history(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    msgs = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]
