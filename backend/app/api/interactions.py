from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_session
from app.db.models import BidInteraction, PublicBid, User, UserRole
from app.auth import get_current_user, require_full_or_admin

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


class InteractionBody(BaseModel):
    is_favorite: Optional[bool] = None
    is_viewed: Optional[bool] = None
    is_discarded: Optional[bool] = None
    notes: Optional[str] = None


def _fmt(i: BidInteraction) -> dict:
    return {
        "id": i.id,
        "bid_id": i.bid_id,
        "user_id": i.user_id,
        "is_favorite": i.is_favorite,
        "is_viewed": i.is_viewed,
        "is_discarded": i.is_discarded,
        "notes": i.notes,
        "viewed_at": i.viewed_at,
        "favorited_at": i.favorited_at,
        "updated_at": i.updated_at,
    }


@router.get("/{bid_id}")
async def get_interaction(
    bid_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Retorna a interação do usuário atual com uma licitação."""
    result = await session.execute(
        select(BidInteraction).where(
            BidInteraction.bid_id == bid_id,
            BidInteraction.user_id == user.id,
        )
    )
    interaction = result.scalar_one_or_none()
    if not interaction:
        return {"bid_id": bid_id, "is_favorite": False, "is_viewed": False, "is_discarded": False, "notes": None}
    return _fmt(interaction)


@router.put("/{bid_id}")
async def upsert_interaction(
    bid_id: int,
    body: InteractionBody,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Cria ou atualiza a interação do usuário com uma licitação."""
    if not await session.get(PublicBid, bid_id):
        raise HTTPException(404, "Licitação não encontrada")

    result = await session.execute(
        select(BidInteraction).where(
            BidInteraction.bid_id == bid_id,
            BidInteraction.user_id == user.id,
        )
    )
    interaction = result.scalar_one_or_none()
    now = datetime.utcnow()

    if not interaction:
        interaction = BidInteraction(
            user_id=user.id,
            tenant_id=user.tenant_id,
            bid_id=bid_id,
        )
        session.add(interaction)

    if body.is_favorite is not None:
        if body.is_favorite and not interaction.is_favorite:
            interaction.favorited_at = now
        interaction.is_favorite = body.is_favorite

    if body.is_viewed is not None:
        if body.is_viewed and not interaction.is_viewed:
            interaction.viewed_at = now
        interaction.is_viewed = body.is_viewed

    if body.is_discarded is not None:
        interaction.is_discarded = body.is_discarded

    if body.notes is not None:
        interaction.notes = body.notes

    interaction.updated_at = now
    await session.commit()
    await session.refresh(interaction)
    return _fmt(interaction)


@router.get("")
async def list_my_interactions(
    only_favorites: bool = Query(False),
    only_viewed: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Lista as interações do usuário atual (seus favoritos, vistos, etc.)."""
    stmt = select(BidInteraction).where(BidInteraction.user_id == user.id)
    if only_favorites:
        stmt = stmt.where(BidInteraction.is_favorite == True)  # noqa: E712
    if only_viewed:
        stmt = stmt.where(BidInteraction.is_viewed == True)  # noqa: E712

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(BidInteraction.updated_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    out = []
    for i in rows:
        bid = await session.get(PublicBid, i.bid_id)
        out.append({
            **_fmt(i),
            "bid_title": bid.title if bid else None,
            "bid_closing_date": bid.closing_date if bid else None,
            "bid_state": bid.state if bid else None,
            "bid_estimated_value": float(bid.estimated_value) if bid and bid.estimated_value else None,
        })

    return {"total": total, "page": page, "data": out}


@router.get("/company/all")
async def list_company_interactions(
    only_favorites: bool = Query(False),
    user_id: Optional[int] = Query(None, description="Filtrar por usuário específico"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_full_or_admin),
):
    """Lista interações de todos os usuários da empresa (Full/Admin)."""
    stmt = select(BidInteraction).where(BidInteraction.tenant_id == user.tenant_id)
    if only_favorites:
        stmt = stmt.where(BidInteraction.is_favorite == True)  # noqa: E712
    if user_id:
        stmt = stmt.where(BidInteraction.user_id == user_id)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(BidInteraction.updated_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    out = []
    for i in rows:
        bid = await session.get(PublicBid, i.bid_id)
        member = await session.get(type(user), i.user_id)
        out.append({
            **_fmt(i),
            "user_name": member.name if member else None,
            "bid_title": bid.title if bid else None,
            "bid_closing_date": bid.closing_date if bid else None,
            "bid_state": bid.state if bid else None,
            "bid_estimated_value": float(bid.estimated_value) if bid and bid.estimated_value else None,
        })

    return {"total": total, "page": page, "data": out}
