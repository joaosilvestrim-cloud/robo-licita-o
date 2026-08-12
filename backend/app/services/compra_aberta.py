"""Compra Aberta — plataforma compraaberta.com.br usada por municípios SP/Sul."""
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from app.db.models import BidStatus, BidSphere, BidModality
from app.services.base_portal import BasePortalScraper

logger = logging.getLogger(__name__)

API_BASE = "https://compraaberta.com.br/api"

MODALITY_MAP = {
    "Pregão Eletrônico": BidModality.pregao,
    "Pregão Presencial": BidModality.pregao,
    "Concorrência": BidModality.concorrencia,
    "Tomada de Preços": BidModality.tomada_preco,
    "Convite": BidModality.convite,
    "Dispensa": BidModality.dispensa,
    "Inexigibilidade": BidModality.inexigibilidade,
}

STATUS_MAP = {
    "Aberta": BidStatus.aberta,
    "Em Andamento": BidStatus.andamento,
    "Encerrada": BidStatus.encerrada,
    "Cancelada": BidStatus.cancelada,
}


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val.strip()[:19], fmt).date()
        except ValueError:
            continue
    return None


def _map_bid(item: dict, source_key: str) -> Optional[dict]:
    try:
        external_id = str(item.get("id") or item.get("numero") or "")
        if not external_id:
            return None

        title = (item.get("objeto") or item.get("descricao") or "").strip()
        if not title:
            return None

        closing = _parse_date(
            item.get("dataEncerramentoReceberPropostas") or
            item.get("dataEncerramento") or
            item.get("dataCierre")
        )
        if closing and closing < date.today():
            return None

        status_str = item.get("situacao") or item.get("status") or "Aberta"
        modality_str = item.get("modalidade") or item.get("tipoLicitacao") or ""
        organ = item.get("nomeOrgao") or item.get("entidade") or ""
        state = item.get("uf") or item.get("estado")
        city = item.get("municipio") or item.get("cidade")
        ibge = item.get("codigoIbge")

        try:
            value = float(item.get("valorEstimado") or item.get("valor") or 0) or None
        except (TypeError, ValueError):
            value = None

        detail = item.get("urlDetalhe") or item.get("link")

        return {
            "external_id": f"ca_{external_id}",
            "source": source_key,
            "title": title[:500],
            "description": title,
            "sphere": BidSphere.municipal,
            "state": (state or "")[:2].upper() or None,
            "city": city,
            "city_code": str(ibge)[:7] if ibge else None,
            "organ_name": organ[:255] if organ else None,
            "organ_cnpj": item.get("cnpj"),
            "publication_date": _parse_date(item.get("dataPublicacao")),
            "opening_date": _parse_date(item.get("dataAbertura")),
            "closing_date": closing,
            "status": STATUS_MAP.get(status_str, BidStatus.aberta),
            "estimated_value": value,
            "maximum_value": None,
            "modality": MODALITY_MAP.get(modality_str, BidModality.pregao),
            "edital_url": detail,
            "details_url": detail,
            "platform_url": "https://compraaberta.com.br",
            "last_scraped": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    except Exception:
        return None


class CompraAbertaScraper(BasePortalScraper):
    source_key = "compra_aberta"
    source_name = "Compra Aberta"

    async def fetch_bids(self, client: httpx.AsyncClient, days_back: int) -> list[dict]:
        bids: list[dict] = []
        date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        date_to = date.today().strftime("%Y-%m-%d")
        page = 1

        endpoints = [
            f"{API_BASE}/licitacoes",
            f"{API_BASE}/v1/licitacoes",
            f"{API_BASE}/processos",
        ]

        for endpoint in endpoints:
            try:
                resp = await client.get(endpoint, params={
                    "situacao": "ABERTA",
                    "dataAberturaDe": date_from,
                    "dataAberturaAte": date_to,
                    "page": page,
                    "size": 100,
                }, headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
                })
                if resp.status_code == 200:
                    data = resp.json()
                    items = data if isinstance(data, list) else (
                        data.get("licitacoes") or data.get("data") or []
                    )
                    for item in items:
                        mapped = _map_bid(item, self.source_key)
                        if mapped:
                            bids.append(mapped)
                    break
            except Exception as e:
                logger.warning(f"Compra Aberta endpoint {endpoint}: {e}")
                continue

        return bids


_scraper = CompraAbertaScraper()


async def sync_compra_aberta(days_back: int = 1):
    return await _scraper.sync(days_back=days_back)
