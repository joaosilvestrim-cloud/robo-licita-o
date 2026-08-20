"""Canal 'Fomento' — chamadas/editais de agências de fomento à pesquisa e inovação.

Fonte v1: FAPESP (https://fapesp.br/chamadas). A página lista as chamadas abertas
em HTML estático (h3 + link + data-limite), o que dá pra ler de forma barata.
Para uma consultoria de dados/TI a joia aqui é o PIPE (Pesquisa Inovativa em
Pequenas Empresas) — fomento direto pra empresa de tecnologia.

FINEP/BNDES carregam a lista por JavaScript (sem HTML pronto), então ficam de fora
do v1 — a estrutura abaixo já aceita novas fontes quando/se der pra raspar.
"""
import logging
import re
from datetime import datetime, date
from typing import Optional
import httpx
from sqlmodel import select
from app.db.models import FundingOpportunity, ScrapeLog, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.ti_classifier import classify as classify_ti

logger = logging.getLogger(__name__)

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def _strip(s: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", s).replace("&nbsp;", " ").split())


def _pdate(br: Optional[str]) -> Optional[date]:
    if not br:
        return None
    try:
        d, m, y = br.split("/")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


# Cada chamada: <h3> <a href="https://fapesp.br/NNNNN">Título</a></h3> seguido de
# "Data-limite ...: dd/mm/aaaa", "Áreas: ...", "Modalidade: ...".
_FAPESP_RE = re.compile(
    r'<h3>\s*<a href="(https?://(?:www\.)?fapesp\.br/(\d{4,6}))">(.*?)</a>\s*</h3>(.*?)(?=<h3|<hr|</div>|\Z)',
    re.DOTALL | re.IGNORECASE,
)


def _parse_fapesp(html: str) -> list[dict]:
    out, seen = [], set()
    for m in _FAPESP_RE.finditer(html):
        url, cid, title, tail = m.group(1), m.group(2), _strip(m.group(3)), m.group(4)
        if not title or cid in seen:
            continue
        seen.add(cid)
        dl = re.search(r"[Dd]ata.?limite[^:]*:\s*(\d{2}/\d{2}/\d{4})", tail)
        area_m = re.search(r"[ÁA]reas?\s*:\s*(.*?)<br", tail, re.IGNORECASE | re.DOTALL)
        mod_m = re.search(r"[Mm]odalidade\s*:\s*(.*?)(?:<br|<p|<hr|\Z)", tail, re.DOTALL)
        area = _strip(area_m.group(1)) if area_m else None
        modality = _strip(mod_m.group(1)) if mod_m else None
        is_ti, ti_score = classify_ti(title, area, modality)
        out.append({
            "external_id": f"fapesp::{cid}",
            "source": "fapesp",
            "agency": "FAPESP",
            "title": title[:600],
            "area": (area or None),
            "modality": (modality[:300] if modality else None),
            "url": url,
            "deadline": _pdate(dl.group(1) if dl else None),
            "is_ti": is_ti,
            "ti_score": ti_score,
            "updated_at": datetime.utcnow(),
        })
    return out


async def _fetch_fapesp() -> list[dict]:
    async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
        resp = await client.get("https://fapesp.br/chamadas", headers=_UA)
        if resp.status_code != 200:
            logger.warning(f"FAPESP status {resp.status_code}")
            return []
        raw = resp.content
        try:
            html = raw.decode("utf-8")
        except Exception:
            html = raw.decode("latin-1", errors="replace")
    return _parse_fapesp(html)


async def sync_fomento():
    """Sincroniza chamadas de fomento abertas. Marca is_open=False nas que sumiram
    da lista (encerraram) sem apagar histórico."""
    start = datetime.utcnow()
    log = ScrapeLog(source="fomento", start_time=start)
    found = inserted = updated = 0
    today = date.today()
    try:
        items = await _fetch_fapesp()
        found = len(items)
        current_ids = {it["external_id"] for it in items}

        async with AsyncSessionLocal() as session:
            for m in items:
                # se a chamada tem prazo e já passou, ainda registra mas fechada
                if m["deadline"] and m["deadline"] < today:
                    m["is_open"] = False
                else:
                    m["is_open"] = True
                ext = m["external_id"]
                existing = (await session.execute(
                    select(FundingOpportunity).where(FundingOpportunity.external_id == ext)
                )).scalar_one_or_none()
                if existing:
                    for k, v in m.items():
                        if k not in ("external_id", "source"):
                            setattr(existing, k, v)
                    updated += 1
                else:
                    session.add(FundingOpportunity(**m, created_at=datetime.utcnow()))
                    inserted += 1

            # fecha as que saíram da lista da FAPESP (não estão mais abertas)
            if current_ids:
                stale = (await session.execute(
                    select(FundingOpportunity).where(
                        FundingOpportunity.source == "fapesp",
                        FundingOpportunity.is_open == True,  # noqa: E712
                        FundingOpportunity.external_id.notin_(current_ids),
                    )
                )).scalars().all()
                for s in stale:
                    s.is_open = False
                    s.updated_at = datetime.utcnow()
            await session.commit()
        log.status = ScrapeStatus.sucesso
    except Exception as e:
        logger.exception("Erro sync_fomento")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated = updated
    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()
    logger.info(f"fomento: found={found} ins={inserted} upd={updated}")
    return log
