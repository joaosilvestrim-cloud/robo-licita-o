"""Classe base para scrapers de portais municipais."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional
import httpx
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.source_tracker import update_source_status
from sqlmodel import select

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class BasePortalScraper(ABC):
    source_key: str = ""
    source_name: str = ""

    @abstractmethod
    async def fetch_bids(self, client: httpx.AsyncClient, days_back: int) -> list[dict]:
        """Retorna lista de dicts compatíveis com PublicBid."""
        ...

    async def sync(self, days_back: int = 1) -> ScrapeLog:
        start_time = datetime.utcnow()
        log = ScrapeLog(source=self.source_key, start_time=start_time)
        inserted = updated = found = 0

        try:
            async with httpx.AsyncClient(timeout=45, follow_redirects=True, verify=False) as client:
                bids_data = await self.fetch_bids(client, days_back)

            found = len(bids_data)

            async with AsyncSessionLocal() as session:
                for bid_data in bids_data:
                    result = await session.execute(
                        select(PublicBid).where(
                            PublicBid.source == self.source_key,
                            PublicBid.external_id == bid_data["external_id"],
                        )
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        for k, v in bid_data.items():
                            if k not in ("external_id", "source", "created_at"):
                                setattr(existing, k, v)
                        updated += 1
                    else:
                        session.add(PublicBid(**bid_data, created_at=datetime.utcnow()))
                        inserted += 1
                await session.commit()

            log.status = ScrapeStatus.sucesso

        except Exception as e:
            logger.exception(f"Erro ao sincronizar {self.source_name}")
            log.status = ScrapeStatus.erro
            log.error_message = str(e)[:500]

        log.end_time = datetime.utcnow()
        log.records_found = found
        log.records_inserted = inserted
        log.records_updated = updated

        async with AsyncSessionLocal() as session:
            session.add(log)
            await session.commit()

        await update_source_status(self.source_key, log.status, inserted + updated)
        logger.info(f"{self.source_name}: found={found} ins={inserted} upd={updated} status={log.status}")
        return log
