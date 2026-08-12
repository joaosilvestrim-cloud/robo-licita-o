"""Licitações-e v2 (Banco do Brasil) — interface estática do portal licitacoes-e2.bb.com.br."""
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from sqlmodel import select
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, BidModality, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.source_tracker import update_source_status

logger = logging.getLogger(__name__)

BASE_URL   = "https://licitacoes-e2.bb.com.br"
SEARCH_URL = f"{BASE_URL}/aop-inter-estatico/pesquisar-licitacao.aop"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": f"{BASE_URL}/aop-inter-estatico/",
}


def _parse_decimal(val: Optional[str]) -> Optional[float]:
    if not val:
        return None
    val = re.sub(r"[R$\s]", "", val).replace(".", "").replace(",", ".")
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    val = val.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_row(cells) -> Optional[dict]:
    try:
        texts = [c.get_text(strip=True) for c in cells]
        if len(texts) < 5:
            return None

        external_id = texts[0].strip()
        if not external_id:
            return None

        closing = _parse_date(texts[4] if len(texts) > 4 else None)
        if closing and closing < date.today():
            return None

        organ = texts[1] if len(texts) > 1 else None
        title = texts[2] if len(texts) > 2 else ""
        value = _parse_decimal(texts[5]) if len(texts) > 5 else None

        link_el = cells[0].find("a") if cells else None
        detail_url = (BASE_URL + link_el["href"]) if link_el and link_el.get("href") else None

        return {
            "external_id": f"e2_{external_id}",
            "source": "licitacoes_e2_bb",
            "title": title[:500],
            "description": title,
            "sphere": BidSphere.municipal,
            "state": None,
            "city": None,
            "city_code": None,
            "organ_name": organ,
            "organ_cnpj": None,
            "publication_date": None,
            "opening_date": _parse_date(texts[3] if len(texts) > 3 else None),
            "closing_date": closing,
            "status": BidStatus.aberta,
            "estimated_value": value,
            "maximum_value": None,
            "modality": BidModality.pregao,
            "edital_url": detail_url,
            "details_url": detail_url,
            "last_scraped": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    except Exception:
        return None


async def sync_licitacoes_e2_bb(days_back: int = 1):
    start_time = datetime.utcnow()
    log = ScrapeLog(source="licitacoes_e2_bb", start_time=start_time)
    inserted = updated = found = 0

    try:
        date_from = (date.today() - timedelta(days=days_back)).strftime("%d/%m/%Y")
        date_to   = date.today().strftime("%d/%m/%Y")

        async with httpx.AsyncClient(timeout=45, follow_redirects=True, verify=False) as client:
            page = 1
            while True:
                try:
                    resp = await client.post(SEARCH_URL, data={
                        "opcao": "preencherPesquisar",
                        "dataAberturaDe": date_from,
                        "dataAberturaAte": date_to,
                        "situacaoLicitacao": "A",
                        "pagina": str(page),
                        "itensPorPagina": "100",
                    }, headers=HEADERS)
                    resp.raise_for_status()
                except Exception as e:
                    logger.warning(f"Licitações-e2 BB pág {page}: {e}")
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                rows = soup.select("table.tabelaResultados tbody tr, table#tblLicitacoes tbody tr")
                if not rows:
                    break

                found += len(rows)
                bids = [_parse_row(r.find_all("td")) for r in rows]
                bids = [b for b in bids if b]

                async with AsyncSessionLocal() as session:
                    for bid_data in bids:
                        result = await session.execute(
                            select(PublicBid).where(
                                PublicBid.source == "licitacoes_e2_bb",
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

                next_btn = soup.select_one("a.proximaPagina, a[title='Próxima Página']")
                if not next_btn:
                    break
                page += 1

        log.status = ScrapeStatus.sucesso

    except Exception as e:
        logger.exception("Erro ao sincronizar Licitações-e2 BB")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated = updated

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    await update_source_status("licitacoes_e2_bb", log.status, inserted + updated)
    logger.info(f"Licitações-e2 BB sync: found={found} inserted={inserted} updated={updated} status={log.status}")
    return log
