"""BNC — Banco Nacional de Compras (bnc.org.br) usado por centenas de municípios SP/Sul."""
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from app.db.models import BidStatus, BidSphere, BidModality
from app.services.base_portal import BasePortalScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://bnc.org.br"
API_URL  = f"{BASE_URL}/api/licitacoes"

MODALITY_MAP = {
    "Pregão Eletrônico": BidModality.pregao,
    "Pregão Presencial": BidModality.pregao,
    "Concorrência": BidModality.concorrencia,
    "Tomada de Preços": BidModality.tomada_preco,
    "Convite": BidModality.convite,
    "Dispensa": BidModality.dispensa,
    "Inexigibilidade": BidModality.inexigibilidade,
    "Leilão": BidModality.leilao,
    "Diálogo Competitivo": BidModality.dialogo_competitivo,
}

STATUS_MAP = {
    "Aberta": BidStatus.aberta,
    "Em Andamento": BidStatus.andamento,
    "Encerrada": BidStatus.encerrada,
    "Cancelada": BidStatus.cancelada,
    "Suspensa": BidStatus.andamento,
    "Homologada": BidStatus.encerrada,
}


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(val.strip()[:19], fmt).date()
        except ValueError:
            continue
    return None


def _map_bid(item: dict) -> Optional[dict]:
    try:
        external_id = str(item.get("id") or item.get("numero") or item.get("codigoLicitacao") or "")
        if not external_id:
            return None

        title = (
            item.get("objeto") or item.get("descricao") or
            item.get("objetoLicitacao") or ""
        ).strip()
        if not title:
            return None

        closing = _parse_date(
            item.get("dataEncerramentoReceberPropostas") or
            item.get("dataEncerramento") or
            item.get("dataFimReceberProposta")
        )
        if closing and closing < date.today():
            return None

        status_str = item.get("situacao") or item.get("status") or "Aberta"
        modality_str = (
            item.get("modalidade") or item.get("tipoLicitacao") or
            item.get("modalidadeLicitacao") or ""
        )

        organ = (item.get("nomeOrgao") or item.get("entidade") or item.get("orgao") or "").strip()
        cnpj = item.get("cnpjOrgao") or item.get("cnpj")
        state = item.get("uf") or item.get("estado") or item.get("siglaUF")
        city = item.get("municipio") or item.get("cidade") or item.get("nomeMunicipio")
        ibge = item.get("codigoIbge") or item.get("ibge") or item.get("codigoMunicipio")

        try:
            value = float(item.get("valorEstimado") or item.get("valor") or item.get("valorTotal") or 0) or None
        except (TypeError, ValueError):
            value = None

        detail_url = item.get("urlDetalhe") or item.get("link") or item.get("url")
        if detail_url and not detail_url.startswith("http"):
            detail_url = BASE_URL + detail_url

        return {
            "external_id": f"bnc_{external_id}",
            "source": "bnc",
            "title": title[:500],
            "description": title,
            "sphere": BidSphere.municipal,
            "state": (state or "")[:2].upper() or None,
            "city": city,
            "city_code": str(ibge)[:7] if ibge else None,
            "organ_name": organ[:255] if organ else None,
            "organ_cnpj": cnpj,
            "publication_date": _parse_date(item.get("dataPublicacao")),
            "opening_date": _parse_date(item.get("dataAbertura") or item.get("dataInicioReceberProposta")),
            "closing_date": closing,
            "status": STATUS_MAP.get(status_str, BidStatus.aberta),
            "estimated_value": value,
            "maximum_value": None,
            "modality": MODALITY_MAP.get(modality_str, BidModality.pregao),
            "edital_url": detail_url,
            "details_url": detail_url,
            "platform_url": BASE_URL,
            "last_scraped": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    except Exception:
        logger.debug("Erro ao mapear item BNC", exc_info=True)
        return None


class BNCScraper(BasePortalScraper):
    source_key = "bnc"
    source_name = "BNC — Banco Nacional de Compras"

    async def fetch_bids(self, client: httpx.AsyncClient, days_back: int) -> list[dict]:
        bids: list[dict] = []
        date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        date_to = date.today().strftime("%Y-%m-%d")
        page = 1

        # Tenta endpoints conhecidos do BNC
        endpoints_params = [
            (f"{API_URL}", {
                "situacao": "ABERTA",
                "dataAberturaDe": date_from,
                "dataAberturaAte": date_to,
                "pagina": page,
                "itensPorPagina": 100,
            }),
            (f"{BASE_URL}/api/v1/licitacoes", {
                "status": "aberta",
                "inicio": date_from,
                "fim": date_to,
                "page": page,
                "size": 100,
            }),
            (f"{BASE_URL}/api/processos", {
                "situacao": "A",
                "dtInicio": date_from,
                "dtFim": date_to,
                "pagina": page,
            }),
        ]

        for endpoint, params in endpoints_params:
            try:
                resp = await client.get(endpoint, params=params, headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
                })
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data if isinstance(data, list) else (
                    data.get("licitacoes") or data.get("processos") or
                    data.get("data") or data.get("content") or []
                )

                while items:
                    for item in items:
                        mapped = _map_bid(item)
                        if mapped:
                            bids.append(mapped)

                    total = data.get("total") or data.get("totalRegistros") or data.get("totalElements") or 0
                    if not total or len(bids) >= int(total) or page >= 30:
                        break

                    page += 1
                    params_next = {**params}
                    for key in ("pagina", "page"):
                        if key in params_next:
                            params_next[key] = page
                    resp = await client.get(endpoint, params=params_next, headers={"Accept": "application/json"})
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    items = data if isinstance(data, list) else (
                        data.get("licitacoes") or data.get("processos") or
                        data.get("data") or data.get("content") or []
                    )

                if bids:
                    break  # encontrou dados, não tenta próximo endpoint

            except Exception as e:
                logger.warning(f"BNC endpoint {endpoint}: {e}")
                continue

        return bids


_scraper = BNCScraper()


async def sync_bnc(days_back: int = 1):
    return await _scraper.sync(days_back=days_back)
