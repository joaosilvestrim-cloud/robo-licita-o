from fastapi import APIRouter, Depends
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import DataSource, ScrapeLog, PublicBid, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/portals")
async def list_portals(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Portais de origem das licitações (de qual sistema cada uma veio, via PNCP),
    com a contagem real de licitações de cada um."""
    rows = (await session.execute(
        select(PublicBid.source_portal, func.count().label("n"))
        .where(PublicBid.source_portal != None)  # noqa: E711
        .group_by(PublicBid.source_portal)
        .order_by(func.count().desc())
    )).all()
    total = sum(r.n for r in rows)
    return {
        "total": total,
        "portals": [{"portal": r.source_portal, "count": r.n} for r in rows],
    }

# fontes que compartilham o mesmo status de scrape (todas vêm do PNCP)
_STATUS_KEY = {
    "pncp": "pncp",
    "ti_keywords": "ti_keywords",
    "pncp_contratos": "pncp_contratos",
    "dou": "dou",
    "fomento": "fomento",
}


@router.get("")
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Fontes de dados ativas, com o status real da última sincronização (ScrapeLog)."""
    sources = (await session.execute(
        select(DataSource).where(DataSource.active == True).order_by(DataSource.id)  # noqa: E712
    )).scalars().all()

    out = []
    for s in sources:
        log = (await session.execute(
            select(ScrapeLog).where(ScrapeLog.source == _STATUS_KEY.get(s.key, s.key))
            .order_by(ScrapeLog.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        out.append({
            "key": s.key,
            "name": s.name,
            "description": s.description,
            "official_url": s.official_url,
            "active": s.active,
            "last_sync_at": log.end_time if log else None,
            "last_sync_status": (log.status.value if log and log.status else None),
            "last_sync_found": log.records_found if log else None,
            "last_sync_records": (log.records_inserted + log.records_updated) if log else None,
        })
    return out
