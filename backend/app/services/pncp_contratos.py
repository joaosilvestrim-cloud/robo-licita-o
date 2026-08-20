"""Canal 'recontratação de TI' — contratos públicos de TI/dados que vão vencer.

Fonte: PNCP /contratos (por data de publicação). Guardamos apenas contratos de
TI ainda vigentes (vigência no futuro) — é onde mora a oportunidade: quando o
contrato vence, o órgão recontrata, e o Sonar avisa antes do concorrente.
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
import httpx
from sqlmodel import select
from app.db.models import PublicContract, ScrapeLog, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.ti_classifier import classify as classify_ti

logger = logging.getLogger(__name__)
PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"


def _pdate(v: Optional[str]) -> Optional[date]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v[:10]).date()
    except Exception:
        return None


def _pdec(v) -> Optional[Decimal]:
    try:
        return Decimal(str(v)) if v is not None else None
    except Exception:
        return None


def _map(item: dict) -> Optional[dict]:
    objeto = (item.get("objetoContrato") or "").strip()
    if not objeto:
        return None
    compra = item.get("numeroControlePncpCompra") or ""
    num = item.get("numeroContratoEmpenho") or item.get("numeroContrato") or item.get("sequencialContrato") or "0"
    external_id = f"{compra}::{num}"

    org = item.get("orgaoEntidade") or {}
    uni = item.get("unidadeOrgao") or {}
    sphere = {"F": "federal", "E": "estadual", "M": "municipal"}.get(org.get("esferaId") or "")

    is_ti, ti_score = classify_ti(objeto)

    return {
        "external_id": external_id,
        "source": "pncp",
        "objeto": objeto[:1000],
        "valor": _pdec(item.get("valorGlobal") or item.get("valorInicial")),
        "organ_name": (org.get("razaoSocial") or None),
        "organ_cnpj": (org.get("cnpj") or None),
        "sphere": sphere,
        "state": uni.get("ufSigla"),
        "city": uni.get("municipioNome"),
        "supplier_name": item.get("nomeRazaoSocialFornecedor"),
        "supplier_document": item.get("niFornecedor"),
        "vigencia_inicio": _pdate(item.get("dataVigenciaInicio")),
        "vigencia_fim": _pdate(item.get("dataVigenciaFim")),
        "is_ti": is_ti,
        "ti_score": ti_score,
        "updated_at": datetime.utcnow(),
    }


async def sync_contratos(days_back: int = 120, max_pages: int = 15):
    """Sincroniza contratos de TI publicados nos últimos N dias e ainda vigentes."""
    start = datetime.utcnow()
    log = ScrapeLog(source="pncp_contratos", start_time=start)
    found = inserted = updated = 0
    today = date.today()
    try:
        d_from = (today - timedelta(days=days_back)).strftime("%Y%m%d")
        d_to = today.strftime("%Y%m%d")
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            page = 1
            while page <= max_pages:
                try:
                    resp = await client.get(
                        f"{PNCP_BASE}/contratos",
                        params={"dataInicial": d_from, "dataFinal": d_to, "pagina": page, "tamanhoPagina": 50},
                        headers={"Accept": "application/json"},
                    )
                    if resp.status_code in (400, 404, 204, 422):
                        break
                    data = resp.json()
                except Exception as e:
                    logger.warning(f"contratos pág {page}: {e}")
                    break

                items = data.get("data", []) if isinstance(data, dict) else []
                if not items:
                    break
                found += len(items)

                async with AsyncSessionLocal() as session:
                    for it in items:
                        m = _map(it)
                        if not m or not m["is_ti"]:
                            continue  # só interessa TI/dados
                        vf = m["vigencia_fim"]
                        if vf and vf < today:
                            continue  # já venceu, não é oportunidade
                        ext = m["external_id"]
                        existing = (await session.execute(
                            select(PublicContract).where(PublicContract.external_id == ext)
                        )).scalar_one_or_none()
                        if existing:
                            for k, v in m.items():
                                if k not in ("external_id", "source"):
                                    setattr(existing, k, v)
                            updated += 1
                        else:
                            session.add(PublicContract(**m, created_at=datetime.utcnow()))
                            inserted += 1
                    await session.commit()

                total_pages = (data.get("totalPaginas") if isinstance(data, dict) else None) or max_pages
                if page >= min(total_pages, max_pages):
                    break
                page += 1
        log.status = ScrapeStatus.sucesso
    except Exception as e:
        logger.exception("Erro sync_contratos")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated = updated
    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()
    logger.info(f"contratos TI: found={found} ins={inserted} upd={updated}")
    return log
