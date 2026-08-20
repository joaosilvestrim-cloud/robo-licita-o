from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import FundingOpportunity, User
from app.auth import get_current_user
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/api/funding", tags=["funding"])


def _fmt(f: FundingOpportunity, today: date) -> dict:
    dl = (f.deadline - today).days if f.deadline else None
    return {
        "id": f.id,
        "external_id": f.external_id,
        "source": f.source,
        "agency": f.agency,
        "title": f.title,
        "area": f.area,
        "modality": f.modality,
        "url": f.url,
        "deadline": f.deadline,
        "days_left": dl,
        "is_ti": f.is_ti,
        "ti_score": f.ti_score,
    }


@router.get("/open")
async def open_funding(
    only_ti: bool = Query(True, description="só chamadas com aderência a TI/dados"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Chamadas de fomento abertas (FAPESP). Prioriza prazo mais próximo primeiro."""
    today = date.today()
    ck = f"funding:{user.tenant_id}:{only_ti}:{page}:{limit}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    stmt = select(FundingOpportunity).where(FundingOpportunity.is_open == True)  # noqa: E712
    if only_ti:
        stmt = stmt.where(FundingOpportunity.is_ti == True)  # noqa: E712

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    # com prazo primeiro (asc), depois as sem prazo; empurra passadas pro fim
    stmt = stmt.order_by(
        FundingOpportunity.deadline.is_(None).asc(),
        FundingOpportunity.deadline.asc(),
    ).offset((page - 1) * limit).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    result = {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "data": [_fmt(f, today) for f in rows],
    }
    cache_set(ck, result, ttl=300)
    return result
