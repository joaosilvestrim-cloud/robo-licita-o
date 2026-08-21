"""Pré-cálculo de vencedores das licitações (tela Vencedores + ranking).

Percorre licitações de TI já encerradas que ainda não foram checadas, busca os
vencedores no PNCP (via competitors.get_competitors) e grava em bid_winners.
É limitado por execução para não sobrecarregar o PNCP nem a instância do Render.
O cron roda 2x ao dia e vai populando aos poucos.
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlmodel import select
from app.db.models import PublicBid, BidWinner, BidStatus, ScrapeLog, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.competitors import get_competitors

logger = logging.getLogger(__name__)

_MAX_BIDS = 12   # licitações processadas por execução (cada uma faz ~8 chamadas PNCP)
# janela de homologação: encerradas ha pelo menos alguns dias (ja pode ter
# resultado) e nao antigas demais. Fora disso nao vale gastar chamada.
_MIN_DAYS = 12
_MAX_DAYS = 180


async def sync_winners(max_bids: int = _MAX_BIDS):
    start = datetime.utcnow()
    log = ScrapeLog(source="winners", start_time=start)
    processed = inserted = with_result = 0
    today = date.today()
    try:
        async with AsyncSessionLocal() as session:
            # licitações de TI encerradas na janela de homologação, ainda não
            # checadas. Mais recentes dentro da janela primeiro.
            oldest = today - timedelta(days=_MAX_DAYS)
            newest = today - timedelta(days=_MIN_DAYS)
            stmt = (
                select(PublicBid)
                .where(
                    PublicBid.is_ti == True,  # noqa: E712
                    PublicBid.status == BidStatus.encerrada,
                    PublicBid.external_id != None,  # noqa: E711
                    PublicBid.source == "pncp",
                    PublicBid.winners_synced_at == None,  # noqa: E711
                    PublicBid.closing_date != None,  # noqa: E711
                    PublicBid.closing_date >= oldest,
                    PublicBid.closing_date <= newest,
                )
                .order_by(PublicBid.closing_date.desc())
                .limit(max_bids)
            )
            bids = (await session.execute(stmt)).scalars().all()

            for bid in bids:
                processed += 1
                data = await get_competitors(bid.external_id)
                winners = data.get("winners") or [] if data.get("has_result") else []

                if winners:
                    with_result += 1
                    for w in winners:
                        doc = str(w.get("document") or "").strip()
                        if not doc:
                            continue
                        existing = (await session.execute(
                            select(BidWinner).where(
                                BidWinner.external_id == bid.external_id,
                                BidWinner.supplier_document == doc,
                            )
                        )).scalar_one_or_none()
                        payload = dict(
                            external_id=bid.external_id,
                            bid_id=bid.id,
                            bid_title=(bid.title or "")[:500],
                            organ_name=bid.organ_name,
                            state=bid.state,
                            sphere=(bid.sphere.value if bid.sphere else None),
                            homologated_at=bid.closing_date,
                            supplier_name=w.get("name"),
                            supplier_document=doc,
                            porte=w.get("porte"),
                            valor_total=Decimal(str(w.get("total_value") or 0)),
                            items_won=int(w.get("items_won") or 0),
                            is_ti=bid.is_ti,
                            updated_at=datetime.utcnow(),
                        )
                        if existing:
                            for k, v in payload.items():
                                setattr(existing, k, v)
                        else:
                            session.add(BidWinner(**payload))
                            inserted += 1
                # sempre marca como checada para a fila avançar (com ou sem
                # resultado). Um recheck periódico das sem-vencedor fica p/ depois.
                bid.winners_synced_at = datetime.utcnow()

            await session.commit()
        log.status = ScrapeStatus.sucesso
    except Exception as e:
        logger.exception("Erro sync_winners")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = processed
    log.records_inserted = inserted
    log.records_updated = with_result
    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()
    logger.info(f"winners: processadas={processed} com_resultado={with_result} novos={inserted}")
    return log
