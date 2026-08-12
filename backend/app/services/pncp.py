"""Sincronizador PNCP — Portal Nacional de Contratações Públicas."""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from sqlmodel import select
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, BidModality, ScrapeStatus
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"

# Modalidades disponíveis no PNCP (1–9)
PNCP_MODALITIES = [1, 2, 3, 4, 5, 6, 7, 8, 9]

MODALITY_MAP = {
    1: BidModality.pregao,           # Pregão Eletrônico
    2: BidModality.concorrencia,     # Concorrência Eletrônica
    3: BidModality.concorrencia,     # Concorrência Presencial
    4: BidModality.concorrencia,     # Concurso
    5: BidModality.leilao,           # Leilão Eletrônico
    6: BidModality.pregao,           # Pregão (antigo)
    7: BidModality.dialogo_competitivo,
    8: BidModality.dispensa,
    9: BidModality.inexigibilidade,
}

# esferaId no PNCP: "F"=federal, "E"=estadual, "M"=municipal
SPHERE_MAP = {
    "F": BidSphere.federal,
    "E": BidSphere.estadual,
    "M": BidSphere.municipal,
    "federal": BidSphere.federal,
    "estadual": BidSphere.estadual,
    "municipal": BidSphere.municipal,
}

# situacaoCompraId: 1=divulgada/aberta, 2=em andamento, 3=concluída, 4=cancelada, 5=suspenso
STATUS_MAP = {
    1: BidStatus.aberta,
    2: BidStatus.andamento,
    3: BidStatus.encerrada,
    4: BidStatus.cancelada,
    5: BidStatus.andamento,
}


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val[:10]).date()
    except Exception:
        return None


def _parse_decimal(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _map_bid(item: dict, source_key: str) -> dict:
    """Converte item da API PNCP para dict do modelo PublicBid."""
    external_id = str(item.get("numeroControlePNCP") or "")
    modality_id = item.get("modalidadeId")

    # Esfera: vem em orgaoEntidade.poderId (F/E/N) ou unidadeOrgao implícito
    # poderId: F=Federal, E=Estadual, N=Municipal/Não-federal
    poder_id = item.get("orgaoEntidade", {}).get("poderId", "") if isinstance(item.get("orgaoEntidade"), dict) else ""
    esfera_id = item.get("orgaoEntidade", {}).get("esferaId", "") if isinstance(item.get("orgaoEntidade"), dict) else ""

    if esfera_id:
        sphere = SPHERE_MAP.get(esfera_id)
    elif poder_id == "F":
        sphere = BidSphere.federal
    elif poder_id == "E":
        sphere = BidSphere.estadual
    else:
        sphere = BidSphere.municipal

    # Status pelo código numérico
    status_id = item.get("situacaoCompraId")
    status = STATUS_MAP.get(status_id, BidStatus.aberta)

    # Localização vem em unidadeOrgao
    unidade = item.get("unidadeOrgao") or {}
    state = unidade.get("ufSigla") or unidade.get("ufNome")
    city = unidade.get("municipioNome")
    city_code = str(unidade.get("codigoIbge") or "")[:7] or None

    # Órgão
    orgao = item.get("orgaoEntidade") or {}
    organ_name = orgao.get("razaoSocial") if isinstance(orgao, dict) else None
    organ_cnpj = orgao.get("cnpj") if isinstance(orgao, dict) else None

    return {
        "external_id": external_id,
        "source": source_key,
        "title": (item.get("objetoCompra") or "")[:500],
        "description": item.get("informacaoComplementar") or item.get("objetoCompra"),
        "sphere": sphere,
        "state": state,
        "city": city,
        "city_code": city_code,
        "organ_name": organ_name,
        "organ_cnpj": organ_cnpj,
        "publication_date": _parse_date(item.get("dataPublicacaoPncp") or item.get("dataInclusao")),
        "opening_date": _parse_date(item.get("dataAberturaProposta")),
        "closing_date": _parse_date(item.get("dataEncerramentoProposta")),
        "status": status,
        "estimated_value": _parse_decimal(item.get("valorTotalEstimado")),
        "maximum_value": _parse_decimal(item.get("valorTotalHomologado")),
        "modality": MODALITY_MAP.get(modality_id),
        "edital_url": item.get("linkSistemaOrigem") or item.get("linkProcessoEletronico"),
        "details_url": item.get("linkSistemaOrigem"),
        "last_scraped": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def _fetch_modality(client: httpx.AsyncClient, date_from: str, date_to: str,
                          modality_id: int, max_pages: int = 5) -> tuple[list, int, int]:
    """Busca licitações de uma modalidade específica."""
    items_all = []
    page = 1

    while page <= max_pages:
        try:
            resp = await client.get(
                f"{PNCP_BASE}/contratacoes/publicacao",
                params={
                    "dataInicial": date_from,
                    "dataFinal": date_to,
                    "codigoModalidadeContratacao": modality_id,
                    "pagina": page,
                    "tamanhoPagina": 50,
                },
                headers={"Accept": "application/json"},
            )
            if resp.status_code in (400, 404, 204):
                break
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break
            items_all.extend(items)
            total_pages = data.get("totalPaginas", 1)
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            logger.warning(f"Modalidade {modality_id} pág {page}: {e}")
            break

    return items_all


async def sync_pncp(days_back: int = 1):
    """Busca licitações publicadas nos últimos N dias na API PNCP."""
    start_time = datetime.utcnow()
    log = ScrapeLog(source="pncp", start_time=start_time)
    inserted = updated = found = 0

    try:
        date_from = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
        date_to = date.today().strftime("%Y%m%d")

        async with httpx.AsyncClient(timeout=30) as client:
            for modality_id in PNCP_MODALITIES:
                items = await _fetch_modality(client, date_from, date_to, modality_id)
                if not items:
                    continue

                found += len(items)

                async with AsyncSessionLocal() as session:
                    for item in items:
                        bid_data = _map_bid(item, "pncp")
                        external_id = bid_data["external_id"]
                        if not external_id:
                            continue

                        result = await session.execute(
                            select(PublicBid).where(
                                PublicBid.source == "pncp",
                                PublicBid.external_id == external_id,
                            )
                        )
                        existing = result.scalar_one_or_none()

                        # Só importa licitações com prazo ainda aberto
                        closing = bid_data.get("closing_date")
                        if closing and closing < date.today():
                            continue

                        if existing:
                            for k, v in bid_data.items():
                                if k not in ("external_id", "source", "created_at"):
                                    setattr(existing, k, v)
                            updated += 1
                        else:
                            bid = PublicBid(**bid_data, created_at=datetime.utcnow())
                            session.add(bid)
                            inserted += 1

                    await session.commit()

        log.status = ScrapeStatus.sucesso

    except Exception as e:
        logger.exception("Erro ao sincronizar PNCP")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated = updated

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    from app.services.source_tracker import update_source_status
    await update_source_status("pncp", log.status, inserted + updated)
    logger.info(f"PNCP sync: found={found} inserted={inserted} updated={updated} status={log.status}")
    return log
