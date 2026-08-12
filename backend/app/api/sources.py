from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import DataSource, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Lista todas as fontes de coleta com status da última sincronização."""
    result = await session.execute(select(DataSource).order_by(DataSource.id))
    sources = result.scalars().all()
    return [
        {
            "key": s.key,
            "name": s.name,
            "description": s.description,
            "official_url": s.official_url,
            "active": s.active,
            "last_sync_at": s.last_sync_at,
            "last_sync_status": s.last_sync_status,
            "last_sync_records": s.last_sync_records,
        }
        for s in sources
    ]
