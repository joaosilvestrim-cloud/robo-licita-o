from typing import Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import ProcurementAlert, AlertStatus, User, PublicBid, ProcurementProfile
from app.auth import get_current_user
import json

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    profile_id: Optional[int] = None,
    status: Optional[AlertStatus] = None,
    include_expired: bool = Query(False, description="Inclui alertas de licitações com prazo vencido"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # JOIN com PublicBid para conseguir filtrar por closing_date
    today = date.today()
    stmt = (
        select(ProcurementAlert)
        .join(PublicBid, PublicBid.id == ProcurementAlert.bid_id)
        .where(ProcurementAlert.tenant_id == user.tenant_id)
    )
    if profile_id:
        stmt = stmt.where(ProcurementAlert.profile_id == profile_id)
    if status:
        stmt = stmt.where(ProcurementAlert.status == status)

    # Por padrão oculta alertas cuja licitação já venceu
    if not include_expired:
        stmt = stmt.where(
            or_(
                PublicBid.closing_date == None,  # noqa: E711
                PublicBid.closing_date >= today,
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(ProcurementAlert.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    alerts = result.scalars().all()

    out = []
    for a in alerts:
        bid = await session.get(PublicBid, a.bid_id)
        reasons = json.loads(a.match_reasons) if a.match_reasons else []
        out.append({
            "id": a.id,
            "bid_id": a.bid_id,
            "bid_title": bid.title if bid else None,
            "bid_state": bid.state if bid else None,
            "bid_city": bid.city if bid else None,
            "bid_closing_date": bid.closing_date if bid else None,
            "bid_estimated_value": float(bid.estimated_value) if bid and bid.estimated_value else None,
            "bid_source": bid.source if bid else None,
            "profile_id": a.profile_id,
            "match_score": float(a.match_score) if a.match_score else None,
            "match_reasons": reasons,
            "status": a.status,
            "created_at": a.created_at,
            "viewed_at": a.viewed_at,
        })

    return {"total": total, "page": page, "data": out}


@router.patch("/{alert_id}/mark-viewed")
async def mark_viewed(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    alert = await session.get(ProcurementAlert, alert_id)
    if not alert or alert.tenant_id != user.tenant_id:
        raise HTTPException(404, "Alerta não encontrado")
    if alert.status == AlertStatus.novo:
        alert.status = AlertStatus.visto
    alert.viewed_at = datetime.utcnow()
    await session.commit()
    return {"ok": True}


@router.patch("/{alert_id}/favorite")
async def toggle_favorite(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    alert = await session.get(ProcurementAlert, alert_id)
    if not alert or alert.tenant_id != user.tenant_id:
        raise HTTPException(404, "Alerta não encontrado")
    alert.status = AlertStatus.visto if alert.status == AlertStatus.favorito else AlertStatus.favorito
    await session.commit()
    return {"status": alert.status}


@router.patch("/{alert_id}/discard")
async def discard(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    alert = await session.get(ProcurementAlert, alert_id)
    if not alert or alert.tenant_id != user.tenant_id:
        raise HTTPException(404, "Alerta não encontrado")
    alert.status = AlertStatus.descartado
    await session.commit()
    return {"ok": True}


@router.post("/bulk/mark-all-viewed")
async def bulk_mark_all_viewed(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Marca todos os alertas 'novos' do tenant como vistos."""
    stmt = (
        update(ProcurementAlert)
        .where(
            ProcurementAlert.tenant_id == user.tenant_id,
            ProcurementAlert.status == AlertStatus.novo,
        )
        .values(status=AlertStatus.visto, viewed_at=datetime.utcnow())
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"updated": result.rowcount or 0}


@router.post("/bulk/discard-all")
async def bulk_discard_all(
    status: Optional[AlertStatus] = Query(None, description="Se informado, descarta só desse status"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Descarta todos os alertas do tenant (ou filtrados por status)."""
    filters = [
        ProcurementAlert.tenant_id == user.tenant_id,
        ProcurementAlert.status != AlertStatus.favorito,  # preserva favoritos
        ProcurementAlert.status != AlertStatus.descartado,
    ]
    if status:
        filters.append(ProcurementAlert.status == status)

    stmt = update(ProcurementAlert).where(*filters).values(status=AlertStatus.descartado)
    result = await session.execute(stmt)
    await session.commit()
    return {"discarded": result.rowcount or 0}


@router.delete("/bulk/discarded")
async def bulk_delete_discarded(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Remove permanentemente todos os alertas já descartados."""
    stmt = delete(ProcurementAlert).where(
        ProcurementAlert.tenant_id == user.tenant_id,
        ProcurementAlert.status == AlertStatus.descartado,
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"deleted": result.rowcount or 0}


@router.delete("/bulk/all")
async def bulk_delete_all(
    keep_favorites: bool = Query(True, description="Se true, preserva favoritos"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Remove permanentemente todos os alertas (opcionalmente preserva favoritos)."""
    filters = [ProcurementAlert.tenant_id == user.tenant_id]
    if keep_favorites:
        filters.append(ProcurementAlert.status != AlertStatus.favorito)

    stmt = delete(ProcurementAlert).where(*filters)
    result = await session.execute(stmt)
    await session.commit()
    return {"deleted": result.rowcount or 0}


@router.get("/summary")
async def alerts_summary(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    # Conta apenas alertas de licitações ainda válidas (prazo em aberto ou sem prazo)
    valid_filter = [
        ProcurementAlert.tenant_id == user.tenant_id,
        or_(
            PublicBid.closing_date == None,  # noqa: E711
            PublicBid.closing_date >= today,
        ),
    ]

    base = (
        select(func.count())
        .select_from(ProcurementAlert)
        .join(PublicBid, PublicBid.id == ProcurementAlert.bid_id)
    )
    total = (await session.execute(base.where(*valid_filter))).scalar_one()
    novos = (await session.execute(
        base.where(*valid_filter, ProcurementAlert.status == AlertStatus.novo)
    )).scalar_one()
    favoritos = (await session.execute(
        base.where(*valid_filter, ProcurementAlert.status == AlertStatus.favorito)
    )).scalar_one()
    return {"total": total, "novos": novos, "favoritos": favoritos}
