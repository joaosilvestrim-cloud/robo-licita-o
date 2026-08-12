"""Portal de Compras Públicas — portaldecompraspublicas.com.br (API REST)."""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from app.db.models import BidStatus, BidSphere, BidModality
from app.services.base_portal import BasePortalScraper

logger = logging.getLogger(__name__)

API_BASE = "https://www.portaldecompraspublicas.com.br/api"

MODALITY_MAP = {
    "Pregão Eletrônico": BidModality.pregao,
    "Pregão Presencial": BidModality.pregao,
    "Concorrência": BidModality.concorrencia,
    "Tomada de Preços": BidModality.tomada_preco,
    "Convite": BidModality.convite,
    "Dispensa": BidModality.dispensa,
    "Inexigibilidade": BidModality.inexigibilidade,
    "Leilão": BidModality.leilao,
    "Concurso Público": BidModality.concorrencia,
    "Diálogo Competitivo": BidModality.dialogo_competitivo,
}

STATUS_MAP = {
    "Aberta": BidStatus.aberta,
    "Em Andamento": BidStatus.andamento,
    "Encerrada": BidStatus.encerrada,
    "Cancelada": BidStatus.cancelada,
    "Suspensa": BidStatus.andamento,
    "Revogada": BidStatus.cancelada,
    "Homologada": BidStatus.encerrada,
}


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val[:len(fmt)], fmt).date()
        except Exception:
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

        closing_raw = item.get("dataEncerramentoReceberPropostas") or item.get("dataEncerramento")
        closing = _parse_date(closing_raw)
        if closing and closing < date.today():
            return None

        status_str = item.get("situacao") or item.get("status") or "Aberta"
        modality_str = item.get("modalidade") or item.get("tipoLicitacao") or ""

        organ = item.get("nomeOrgao") or item.get("unidadeGestora") or ""
        organ_cnpj = item.get("cnpjOrgao") or item.get("cnpj")
        state = item.get("uf") or item.get("estado")
        city = item.get("municipio") or item.get("cidade")
        ibge = item.get("codigoIbge") or item.get("ibge")
        value = item.get("valorEstimado") or item.get("valor")
        detail_url = item.get("urlDetalhe") or item.get("link")

        try:
            value = float(value) if value else None
        except (TypeError, ValueError):
            value = None

        return {
            "external_id": f"pcp_{external_id}",
            "source": source_key,
            "title": title[:500],
            "description": title,
            "sphere": BidSphere.municipal,
            "state": (state or "")[:2].upper() or None,
            "city": city,
            "city_code": str(ibge)[:7] if ibge else None,
            "organ_name": organ[:255] if organ else None,
            "organ_cnpj": organ_cnpj,
            "publication_date": _parse_date(item.get("dataPublicacao")),
            "opening_date": _parse_date(item.get("dataAbertura") or item.get("dataInicioReceberPropostas")),
            "closing_date": closing,
            "status": STATUS_MAP.get(status_str, BidStatus.aberta),
            "estimated_value": value,
            "maximum_value": None,
            "modality": MODALITY_MAP.get(modality_str, BidModality.pregao),
            "edital_url": detail_url,
            "details_url": detail_url,
            "platform_url": "https://www.portaldecompraspublicas.com.br",
            "last_scraped": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    except Exception:
        logger.debug("Erro ao mapear item PCP", exc_info=True)
        return None


class PortalComprasPublicasScraper(BasePortalScraper):
    source_key = "portal_compras_publicas"
    source_name = "Portal de Compras Públicas"

    async def fetch_bids(self, client: httpx.AsyncClient, days_back: int) -> list[dict]:
        date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        date_to = date.today().strftime("%Y-%m-%d")
        bids: list[dict] = []
        page = 1

        endpoints = [
            f"{API_BASE}/v1/licitacoes",
            f"{API_BASE}/licitacoes",
            f"{API_BASE}/processos",
        ]

        for endpoint in endpoints:
            try:
                resp = await client.get(endpoint, params={
                    "situacao": "abertas",
                    "dtAberturaDe": date_from,
                    "dtAberturaAte": date_to,
                    "pagina": 1,
                    "itensPorPagina": 100,
                }, headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
                })
                if resp.status_code == 200:
                    data = resp.json()
                    items = data if isinstance(data, list) else (
                        data.get("licitacoes") or data.get("processos") or data.get("data") or []
                    )

                    while items:
                        for item in items:
                            mapped = _map_bid(item, self.source_key)
                            if mapped:
                                bids.append(mapped)

                        total = data.get("total") or data.get("totalRegistros") or 0
                        if len(bids) >= total or page >= 20:
                            break

                        page += 1
                        resp = await client.get(endpoint, params={
                            "situacao": "abertas",
                            "dtAberturaDe": date_from,
                            "dtAberturaAte": date_to,
                            "pagina": page,
                            "itensPorPagina": 100,
                        }, headers={"Accept": "application/json"})
                        if resp.status_code != 200:
                            break
                        data = resp.json()
                        items = data if isinstance(data, list) else (
                            data.get("licitacoes") or data.get("processos") or data.get("data") or []
                        )
                    break

            except Exception as e:
                logger.warning(f"Portal Compras Públicas endpoint {endpoint}: {e}")
                continue

        return bids


_scraper = PortalComprasPublicasScraper()


async def sync_portal_compras_publicas(days_back: int = 1):
    return await _scraper.sync(days_back=days_back)
