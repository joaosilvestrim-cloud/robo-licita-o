from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.database import get_session
from app.db.models import ChatMessage, User
from app.auth import get_current_user, oauth2_scheme
from app.services.hermes import run_agent

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
    token: str = Depends(oauth2_scheme),
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

    # Agente Sonar (Groq) rodando no próprio backend, com o JWT do usuário
    content = await run_agent(body.message, user_token=token)

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
