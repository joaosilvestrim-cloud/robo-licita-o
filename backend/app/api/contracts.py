from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import PublicContract, User
from app.auth import get_current_user
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _fmt(c: PublicContract, today: date) -> dict:
    dl = (c.vigencia_fim - today).days if c.vigencia_fim else None
    return {
        "id": c.id,
        "external_id": c.external_id,
        "objeto": c.objeto,
        "valor": float(c.valor) if c.valor else None,
        "organ_name": c.organ_name,
        "organ_cnpj": c.organ_cnpj,
        "sphere": c.sphere,
        "state": c.state,
        "city": c.city,
        "supplier_name": c.supplier_name,
        "supplier_document": c.supplier_document,
        "vigencia_inicio": c.vigencia_inicio,
        "vigencia_fim": c.vigencia_fim,
        "days_left": dl,
        "ti_score": c.ti_score,
    }


@router.get("/expiring")
async def expiring_contracts(
    months: int = Query(12, ge=1, le=36, description="janela de vencimento em meses"),
    state: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Contratos de TI/dados que vencem na janela — oportunidade de recontratação."""
    today = date.today()
    horizon = today + timedelta(days=months * 31)
    ck = f"contracts:{user.tenant_id}:{months}:{state}:{page}:{limit}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    stmt = select(PublicContract).where(
        PublicContract.is_ti == True,  # noqa: E712
        PublicContract.vigencia_fim != None,  # noqa: E711
        PublicContract.vigencia_fim >= today,
        PublicContract.vigencia_fim <= horizon,
    )
    if state:
        stmt = stmt.where(PublicContract.state.ilike(state.strip()))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(PublicContract.vigencia_fim.asc()).offset((page - 1) * limit).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()

    result = {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "months": months,
        "data": [_fmt(c, today) for c in rows],
    }
    cache_set(ck, result, ttl=180)
    return result
