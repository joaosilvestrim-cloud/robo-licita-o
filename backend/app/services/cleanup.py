"""Manutenção: encerra licitações com prazo vencido e limpa alertas obsoletos."""
import logging
from datetime import datetime, date
from sqlmodel import update, delete
from app.db.models import PublicBid, BidStatus, ProcurementAlert
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def close_expired_bids() -> int:
    """Marca como 'encerrada' toda licitação ainda aberta cuja data de
    encerramento já passou. Retorna o número de registros atualizados."""
    today = date.today()
    async with AsyncSessionLocal() as session:
        stmt = (
            update(PublicBid)
            .where(
                PublicBid.status == BidStatus.aberta,
                PublicBid.closing_date != None,  # noqa: E711
                PublicBid.closing_date < today,
            )
            .values(status=BidStatus.encerrada, status_date=datetime.utcnow())
        )
        result = await session.execute(stmt)
        await session.commit()
        n = result.rowcount or 0
        logger.info(f"close_expired_bids: {n} licitações encerradas por vencimento")
        return n


async def delete_expired_alerts() -> int:
    """Remove alertas cuja licitação já passou do prazo (closing_date < hoje).

    Mantém alertas favoritados (o usuário pode querer guardar referência)
    e alertas de licitações sem prazo (dispensa/inexigibilidade).
    """
    from app.db.models import AlertStatus
    today = date.today()

    async with AsyncSessionLocal() as session:
        # Identifica alerts com bid expirado que NÃO são favoritos
        subq = (
            ProcurementAlert.__table__.select().with_only_columns(ProcurementAlert.id)
            .select_from(ProcurementAlert.__table__.join(
                PublicBid.__table__, ProcurementAlert.bid_id == PublicBid.id
            ))
            .where(
                PublicBid.closing_date != None,  # noqa: E711
                PublicBid.closing_date < today,
                ProcurementAlert.status != AlertStatus.favorito,
            )
        )
        ids_result = await session.execute(subq)
        ids = [row[0] for row in ids_result.all()]

        if not ids:
            logger.info("delete_expired_alerts: nenhum alerta expirado")
            return 0

        result = await session.execute(
            delete(ProcurementAlert).where(ProcurementAlert.id.in_(ids))
        )
        await session.commit()
        n = result.rowcount or 0
        logger.info(f"delete_expired_alerts: {n} alertas expirados removidos")
        return n
