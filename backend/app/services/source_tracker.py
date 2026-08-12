"""Helper: atualiza DataSource após cada sync."""
from datetime import datetime
from app.database import AsyncSessionLocal
from app.db.models import DataSource
from sqlmodel import select


async def update_source_status(key: str, status: str, records: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DataSource).where(DataSource.key == key))
        source = result.scalar_one_or_none()
        if source:
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = status
            source.last_sync_records = records
            await session.commit()
