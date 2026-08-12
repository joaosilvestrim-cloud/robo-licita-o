"""ComprasNet/SIASG — Portal de Compras do Governo Federal (Lei 8.666 legado)."""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from sqlmodel import select
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, BidModality, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.source_tracker import update_source_status

logger = logging.getLogger(__name__)

BASE = "http://compras.dados.gov.br/licitacoes/v1/licitacoes.json"

MODALITY_MAP = {
    "Pregão Eletrônico": BidModality.pregao,
    "Pregão Presencial": BidModality.pregao,
    "Concorrência": BidModality.concorrencia,
    "Tomada de Preços": BidModality.tomada_preco,
    "Convite": BidModality.convite,
    "Leilão": BidModality.leilao,
    "Dispensa": BidModality.dispensa,
    "Inexigibilidade": BidModality.inexigibilidade,
    "Concurso": BidModality.concorrencia,
    "RDC": BidModality.concorrencia,
}

STATUS_MAP = {
    "Aberta": BidStatus.aberta,
    "Em Andamento": BidStatus.andamento,
    "Encerrada": BidStatus.encerrada,
    "Anulada": BidStatus.cancelada,
    "Cancelada": BidStatus.cancelada,
    "Suspensa": BidStatus.andamento,
    "Revogada": BidStatus.cancelada,
}


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val[:10]).date()
    except Exception:
        return None


def _map_bid(item: dict) -> Optional[dict]:
    obj = (item.get("objeto_licitacao") or "").strip()
    if not obj:
        return None

    # Descarta licitações já encerradas
    closing = _parse_date(item.get("data_resultado_compra") or item.get("data_abertura_proposta"))
    today = date.today()
    if closing and closing < today:
        return None

    modality_raw = item.get("modalidade_licitacao", {})
    modality_name = modality_raw.get("descricao", "") if isinstance(modality_raw, dict) else str(modality_raw)

    status_raw = item.get("situacao_licitacao", {})
    status_name = status_raw.get("descricao", "Aberta") if isinstance(status_raw, dict) else str(status_raw)

    ug = item.get("unidade_gestora") or {}
    organ_name = ug.get("nome_unidade_gestora") or ug.get("nome") or None
    organ_cnpj = ug.get("cnpj") or None

    # ComprasNet normalmente só cobre federal
    external_id = str(item.get("identificador") or item.get("id_licitacao") or "")
    if not external_id:
        return None

    link = item.get("_links", {}).get("self", {}).get("href", "") or item.get("link") or ""

    return {
        "external_id": external_id,
        "source": "comprasnet",
        "title": obj[:500],
        "description": item.get("informacao_complementar"),
        "sphere": BidSphere.federal,
        "state": None,
        "city": None,
        "city_code": None,
        "organ_name": organ_name,
        "organ_cnpj": organ_cnpj,
        "publication_date": _parse_date(item.get("data_publicacao")),
        "opening_date": _parse_date(item.get("data_abertura_proposta")),
        "closing_date": closing,
        "status": STATUS_MAP.get(status_name, BidStatus.aberta),
        "estimated_value": float(item["valor_estimado"]) if item.get("valor_estimado") else None,
        "maximum_value": None,
        "modality": MODALITY_MAP.get(modality_name),
        "edital_url": link or None,
        "details_url": link or None,
        "last_scraped": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def sync_comprasnet(days_back: int = 1):
    start_time = datetime.utcnow()
    log = ScrapeLog(source="comprasnet", start_time=start_time)
    inserted = updated = found = 0

    try:
        date_from = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
        date_to = date.today().strftime("%Y%m%d")

        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while True:
                try:
                    resp = await client.get(BASE, params={
                        "dataPublicacaoApartirDe": date_from,
                        "dataPublicacaoAte": date_to,
                        "pagina": page,
                        "quantidade": 500,
                    }, headers={"Accept": "application/json"})

                    if resp.status_code in (400, 404, 204):
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning(f"ComprasNet pág {page}: {e}")
                    break

                items = (data.get("_embedded") or {}).get("licitacoes") or []
                if not items:
                    break

                found += len(items)

                async with AsyncSessionLocal() as session:
                    for item in items:
                        bid_data = _map_bid(item)
                        if not bid_data:
                            continue

                        result = await session.execute(
                            select(PublicBid).where(
                                PublicBid.source == "comprasnet",
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

                page_info = data.get("page") or {}
                total_pages = page_info.get("totalPages") or 1
                if page >= total_pages:
                    break
                page += 1

        log.status = ScrapeStatus.sucesso

    except Exception as e:
        logger.exception("Erro ao sincronizar ComprasNet")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated = updated

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    await update_source_status("comprasnet", log.status, inserted + updated)
    logger.info(f"ComprasNet sync: found={found} inserted={inserted} updated={updated} status={log.status}")
    return log
