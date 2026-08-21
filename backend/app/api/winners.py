from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlalchemy import distinct
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import BidWinner, User
from app.auth import get_current_user
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/api/winners", tags=["winners"])


def _apply_filters(stmt, state, months, min_value, q):
    if state:
        stmt = stmt.where(BidWinner.state.ilike(state.strip()))
    if months:
        since = date.today() - timedelta(days=months * 31)
        stmt = stmt.where(BidWinner.homologated_at != None, BidWinner.homologated_at >= since)  # noqa: E711
    if min_value:
        stmt = stmt.where(BidWinner.valor_total >= min_value)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(BidWinner.supplier_name.ilike(like) | BidWinner.bid_title.ilike(like))
    return stmt


@router.get("")
async def winners(
    state: Optional[str] = None,
    months: int = Query(0, ge=0, le=60, description="homologadas nos últimos N meses (0 = tudo)"),
    min_value: Optional[float] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Vencedores das licitações de TI: lista (quem ganhou o quê) + ranking de
    concorrentes (quem mais ganha). Dados públicos do PNCP após homologação."""
    ck = f"winners:{user.tenant_id}:{state}:{months}:{min_value}:{q}:{page}:{limit}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    base = _apply_filters(select(BidWinner), state, months, min_value, q)

    # lista paginada (quem ganhou o quê) — maiores valores primeiro
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await session.execute(
        base.order_by(BidWinner.valor_total.desc().nullslast()).offset((page - 1) * limit).limit(limit)
    )).scalars().all()

    lista = [{
        "id": w.id,
        "external_id": w.external_id,
        "bid_id": w.bid_id,
        "bid_title": w.bid_title,
        "organ_name": w.organ_name,
        "state": w.state,
        "sphere": w.sphere,
        "homologated_at": w.homologated_at,
        "supplier_name": w.supplier_name,
        "supplier_document": w.supplier_document,
        "porte": w.porte,
        "valor_total": float(w.valor_total) if w.valor_total else 0.0,
        "items_won": w.items_won,
    } for w in rows]

    # ranking de concorrentes (agregado por fornecedor) — só na 1ª página
    ranking = []
    if page == 1:
        rk = _apply_filters(
            select(
                BidWinner.supplier_document,
                func.max(BidWinner.supplier_name).label("name"),
                func.max(BidWinner.porte).label("porte"),
                func.sum(BidWinner.valor_total).label("total"),
                func.count(distinct(BidWinner.external_id)).label("licitacoes"),
                func.sum(BidWinner.items_won).label("itens"),
            ),
            state, months, min_value, q,
        ).group_by(BidWinner.supplier_document).order_by(func.sum(BidWinner.valor_total).desc().nullslast()).limit(15)
        rres = (await session.execute(rk)).all()
        ranking = [{
            "supplier_document": r.supplier_document,
            "supplier_name": r.name,
            "porte": r.porte,
            "total_value": float(r.total) if r.total else 0.0,
            "licitacoes": int(r.licitacoes or 0),
            "items_won": int(r.itens or 0),
        } for r in rres]

    result = {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "lista": lista,
        "ranking": ranking,
    }
    cache_set(ck, result, ttl=300)
    return result
