from typing import Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_session
from app.db.models import BidTracking, PublicBid, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


class TrackingBody(BaseModel):
    participated: bool = False
    proposal_submitted: bool = False
    proposal_date: Optional[date] = None
    proposal_value: Optional[float] = None
    won: Optional[bool] = None
    result_date: Optional[date] = None
    contract_value: Optional[float] = None
    contract_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/{bid_id}", status_code=201)
async def start_tracking(
    bid_id: int,
    body: TrackingBody = TrackingBody(),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    bid = await session.get(PublicBid, bid_id)
    if not bid:
        raise HTTPException(404, "Licitação não encontrada")

    existing = await session.execute(
        select(BidTracking).where(
            BidTracking.bid_id == bid_id,
            BidTracking.tenant_id == user.tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Licitação já está sendo acompanhada")

    tracking = BidTracking(
        tenant_id=user.tenant_id,
        bid_id=bid_id,
        **body.model_dump(),
    )
    session.add(tracking)
    await session.commit()
    await session.refresh(tracking)
    return tracking


@router.get("")
async def list_tracking(
    won: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    stmt = select(BidTracking).where(BidTracking.tenant_id == user.tenant_id)
    if won is not None:
        stmt = stmt.where(BidTracking.won == won)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(BidTracking.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    trackings = result.scalars().all()

    out = []
    for t in trackings:
        bid = await session.get(PublicBid, t.bid_id)
        out.append({
            "id": t.id,
            "bid_id": t.bid_id,
            "bid_title": bid.title if bid else None,
            "bid_state": bid.state if bid else None,
            "bid_closing_date": bid.closing_date if bid else None,
            "bid_estimated_value": float(bid.estimated_value) if bid and bid.estimated_value else None,
            "participated": t.participated,
            "proposal_submitted": t.proposal_submitted,
            "proposal_value": float(t.proposal_value) if t.proposal_value else None,
            "won": t.won,
            "contract_value": float(t.contract_value) if t.contract_value else None,
            "notes": t.notes,
            "created_at": t.created_at,
        })

    return {"total": total, "page": page, "data": out}


@router.patch("/{bid_id}")
async def update_tracking(
    bid_id: int,
    body: TrackingBody,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(BidTracking).where(
            BidTracking.bid_id == bid_id,
            BidTracking.tenant_id == user.tenant_id,
        )
    )
    tracking = result.scalar_one_or_none()
    if not tracking:
        raise HTTPException(404, "Tracking não encontrado")

    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(tracking, k, v)
    tracking.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(tracking)
    return tracking


@router.delete("/{bid_id}", status_code=204)
async def stop_tracking(
    bid_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(BidTracking).where(
            BidTracking.bid_id == bid_id,
            BidTracking.tenant_id == user.tenant_id,
        )
    )
    tracking = result.scalar_one_or_none()
    if not tracking:
        raise HTTPException(404, "Tracking não encontrado")
    await session.delete(tracking)
    await session.commit()
