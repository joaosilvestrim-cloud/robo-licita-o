"""Busca por palavra-chave no PNCP usando o endpoint /api/search.

O endpoint de busca do PNCP faz full-text search nos textos dos editais
publicados — ao contrário do sync por data, que só traz publicações recentes.
Isso permite encontrar licitações com termos específicos como "Google Ads",
"tráfego pago", "Meta Ads", etc., independente da data de publicação.
"""
import logging
import re
from datetime import datetime, date
from typing import Optional, List
import httpx
from sqlmodel import select
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, BidModality, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.pncp import _parse_date, _parse_decimal, MODALITY_MAP, STATUS_MAP, SPHERE_MAP
from app.services.portals import portal_from_url as _portal_from_url

logger = logging.getLogger(__name__)

PNCP_SEARCH_URL = "https://pncp.gov.br/api/search"
PNCP_DETAIL_URL = "https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}"

# O /api/search do PNCP DERRUBA a conexão sem User-Agent de browser. Sem isso a
# busca por palavra-chave falha em produção. Mantemos o UA em todas as chamadas.
_UA = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
}

# Termos de TI/dados que a DriveData quer caçar no PNCP inteiro (não só nas
# publicações recentes). A busca full-text acha por qualquer data.
TI_KEYWORDS = [
    "business intelligence", "power bi", "análise de dados", "ciência de dados",
    "dashboard", "data warehouse", "big data", "banco de dados",
    "inteligência artificial", "machine learning", "ETL", "governança de dados",
    "sistema de informação", "desenvolvimento de software", "fábrica de software",
    "geoprocessamento", "business analytics", "engenharia de dados",
    "sistema de gestão", "plataforma tecnológica", "sistema informatizado",
    "solução tecnológica", "gestão em saúde",
]

# id numérico de modalidade → enum  (mesma lógica do pncp.py)
MODALITY_ID_MAP = MODALITY_MAP

# esfera_id letra → enum
SPHERE_LETTER_MAP = SPHERE_MAP

# situacao_id numérico → enum
STATUS_ID_MAP = STATUS_MAP

# modalidade por nome (fallback)
MODALITY_NAME_MAP: dict[str, BidModality] = {
    "pregão": BidModality.pregao,
    "pregao": BidModality.pregao,
    "concorrência": BidModality.concorrencia,
    "concorrencia": BidModality.concorrencia,
    "tomada de preços": BidModality.tomada_preco,
    "convite": BidModality.convite,
    "dispensa": BidModality.dispensa,
    "inexigibilidade": BidModality.inexigibilidade,
    "leilão": BidModality.leilao,
    "leilao": BidModality.leilao,
    "diálogo competitivo": BidModality.dialogo_competitivo,
}


def _parse_item_url(item_url: str) -> Optional[tuple[str, str, str]]:
    """Extrai (cnpj, ano, seq) do item_url: /compras/{cnpj}/{ano}/{seq}"""
    m = re.match(r"/compras/(\d+)/(\d+)/(\d+)", item_url or "")
    if m:
        return m.group(1), m.group(2), str(int(m.group(3)))
    return None


async def _fetch_detail(client: httpx.AsyncClient, cnpj: str, ano: str, seq: str) -> Optional[dict]:
    """Busca detalhes completos de uma licitação pelo CNPJ/ano/sequencial."""
    try:
        url = PNCP_DETAIL_URL.format(cnpj=cnpj, ano=ano, seq=seq)
        resp = await client.get(url, headers=_UA)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Detail fetch failed {cnpj}/{ano}/{seq}: {e}")
    return None


def _map_search_item(item: dict, detail: Optional[dict] = None) -> dict:
    """Converte item do /api/search (+ detalhe opcional) para dict do PublicBid."""
    external_id = item.get("numero_controle_pncp", "")

    # Modalidade: preferir ID numérico (1-9), fallback por nome
    mod_id = item.get("modalidade_licitacao_id")
    try:
        mod_id_int = int(mod_id) if mod_id is not None else None
    except (TypeError, ValueError):
        mod_id_int = None
    modality = MODALITY_ID_MAP.get(mod_id_int)
    if not modality:
        mod_name = (item.get("modalidade_licitacao_nome") or "").lower()
        modality = MODALITY_NAME_MAP.get(mod_name)

    # Esfera
    sphere = SPHERE_LETTER_MAP.get(item.get("esfera_id", ""))

    # Status: do search temos situacao_id (int)
    sit_id = item.get("situacao_id")
    try:
        sit_int = int(sit_id) if sit_id is not None else None
    except (TypeError, ValueError):
        sit_int = None
    status = STATUS_ID_MAP.get(sit_int, BidStatus.aberta)

    # Título e descrição: o search devolve highlight; o detalhe tem objetoCompra
    title = ""
    description = None
    if detail:
        title = (detail.get("objetoCompra") or item.get("title") or "")[:500]
        description = detail.get("informacaoComplementar") or detail.get("objetoCompra")
    else:
        title = (item.get("title") or "")[:500]
        description = item.get("description")

    # Datas: preferencialmente do detalhe
    d = detail or {}
    opening_date  = _parse_date(d.get("dataAberturaProposta")   or item.get("data_inicio_vigencia"))
    closing_date  = _parse_date(d.get("dataEncerramentoProposta") or item.get("data_fim_vigencia"))
    pub_date      = _parse_date(
        d.get("dataPublicacaoPncp") or item.get("data_publicacao_pncp", "")
    )

    # Valor
    estimated_value = _parse_decimal(d.get("valorTotalEstimado") or item.get("valor_global"))

    # Estado e cidade
    state = item.get("uf")
    city  = item.get("municipio_nome")

    # Órgão
    organ_name = item.get("orgao_nome") or (
        d.get("orgaoEntidade", {}).get("razaoSocial") if isinstance(d.get("orgaoEntidade"), dict) else None
    )
    organ_cnpj = item.get("orgao_cnpj") or (
        d.get("orgaoEntidade", {}).get("cnpj") if isinstance(d.get("orgaoEntidade"), dict) else None
    )

    # URL do edital
    item_url   = item.get("item_url", "")
    edital_url = f"https://pncp.gov.br{item_url}" if item_url else None
    if detail:
        edital_url = detail.get("linkSistemaOrigem") or edital_url

    return {
        "external_id": external_id,
        "source": "pncp",
        "title": title,
        "description": description,
        "sphere": sphere,
        "state": state,
        "city": city,
        "organ_name": organ_name,
        "organ_cnpj": organ_cnpj,
        "publication_date": pub_date,
        "opening_date": opening_date,
        "closing_date": closing_date,
        "status": status,
        "estimated_value": estimated_value,
        "modality": modality,
        "source_portal": _portal_from_url(edital_url),
        "edital_url": edital_url,
        "details_url": edital_url,
        "last_scraped": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def sync_keyword(keyword: str, max_pages: int = 4) -> tuple[int, int, int]:
    """Busca licitações no PNCP pelo keyword e salva/atualiza no DB.

    Retorna (found, inserted, updated).
    """
    found = inserted = updated = 0

    async with httpx.AsyncClient(timeout=20) as client:
        for page in range(1, max_pages + 1):
            try:
                resp = await client.get(
                    PNCP_SEARCH_URL,
                    params={
                        "q": keyword,
                        "tipos_documento": "edital",
                        "pagina": page,
                        "tam_pagina": 20,
                    },
                    headers=_UA,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"pncp_search keyword='{keyword}' pág {page}: {e}")
                break

            items = data.get("items", [])
            if not items:
                break

            found += len(items)
            total = data.get("total", 0)

            for item in items:
                external_id = item.get("numero_controle_pncp", "")
                if not external_id:
                    continue

                # Verificar se já existe no DB
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(PublicBid).where(
                            PublicBid.source == "pncp",
                            PublicBid.external_id == external_id,
                        )
                    )
                    existing = result.scalar_one_or_none()

                # Buscar detalhe apenas se necessário (novo ou sem datas)
                detail = None
                needs_detail = (
                    not existing
                    or not existing.closing_date
                    or not existing.estimated_value
                )
                if needs_detail:
                    parsed = _parse_item_url(item.get("item_url", ""))
                    if parsed:
                        cnpj, ano, seq = parsed
                        detail = await _fetch_detail(client, cnpj, ano, seq)

                bid_data = _map_search_item(item, detail)

                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(PublicBid).where(
                            PublicBid.source == "pncp",
                            PublicBid.external_id == external_id,
                        )
                    )
                    existing = result.scalar_one_or_none()

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

            # Verificar se há mais páginas
            pages_total = (total + 19) // 20
            if page >= pages_total or page >= max_pages:
                break

    return found, inserted, updated


async def sync_all_profile_keywords() -> dict:
    """Coleta keywords de todos os perfis ativos e busca no PNCP."""
    from app.db.models import ProcurementProfile

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ProcurementProfile).where(ProcurementProfile.active == True)  # noqa: E712
        )
        profiles = result.scalars().all()

    # Coletar keywords únicas (excluindo * e vazios)
    all_keywords: set[str] = set()
    for p in profiles:
        for kw in (p.keywords or "").split(","):
            kw = kw.strip()
            if kw and kw != "*":
                all_keywords.add(kw)
        for br in (p.preferred_branches or "").split(","):
            br = br.strip()
            if br and br != "*":
                all_keywords.add(br)

    if not all_keywords:
        logger.info("sync_all_profile_keywords: nenhuma keyword para buscar")
        return {}

    results: dict[str, tuple] = {}
    start = datetime.utcnow()

    for kw in all_keywords:
        logger.info(f"Buscando keyword: '{kw}'")
        found, ins, upd = await sync_keyword(kw)
        results[kw] = (found, ins, upd)
        logger.info(f"  '{kw}': found={found} inserted={ins} updated={upd}")

    # Salvar log agregado
    total_found    = sum(r[0] for r in results.values())
    total_inserted = sum(r[1] for r in results.values())
    total_updated  = sum(r[2] for r in results.values())

    async with AsyncSessionLocal() as session:
        log = ScrapeLog(
            source="pncp_search",
            start_time=start,
            end_time=datetime.utcnow(),
            status=ScrapeStatus.sucesso,
            records_found=total_found,
            records_inserted=total_inserted,
            records_updated=total_updated,
        )
        session.add(log)
        await session.commit()

    return results


async def sync_ti_keywords(max_pages: int = 3) -> dict:
    """Varre o PNCP inteiro pelos termos de TI/dados da DriveData (TI_KEYWORDS).
    Independe dos perfis e da data — acha licitações de qualquer portal de origem
    (Betha, Comprasnet, BLL...) porque todas publicam no PNCP por lei."""
    start = datetime.utcnow()
    results: dict[str, tuple] = {}
    for kw in TI_KEYWORDS:
        try:
            found, ins, upd = await sync_keyword(kw, max_pages=max_pages)
            results[kw] = (found, ins, upd)
            logger.info(f"ti_keyword '{kw}': found={found} ins={ins} upd={upd}")
        except Exception as e:
            logger.warning(f"ti_keyword '{kw}' erro: {e}")
            results[kw] = (0, 0, 0)

    tf = sum(r[0] for r in results.values())
    ti = sum(r[1] for r in results.values())
    tu = sum(r[2] for r in results.values())
    async with AsyncSessionLocal() as session:
        session.add(ScrapeLog(
            source="ti_keywords", start_time=start, end_time=datetime.utcnow(),
            status=ScrapeStatus.sucesso, records_found=tf,
            records_inserted=ti, records_updated=tu,
        ))
        await session.commit()
    logger.info(f"ti_keywords total: found={tf} ins={ti} upd={tu}")
    return results
