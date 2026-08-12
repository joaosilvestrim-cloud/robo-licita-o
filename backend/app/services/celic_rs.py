"""CELIC RS — Central de Licitações do Estado do RS (celic.rs.gov.br)."""
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from app.db.models import BidStatus, BidSphere, BidModality
from app.services.base_portal import BasePortalScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.celic.rs.gov.br"
SEARCH_URL = f"{BASE_URL}/celic/consultarLicitacoes"

MODALITY_MAP = {
    "Pregão Eletrônico": BidModality.pregao,
    "Pregão Presencial": BidModality.pregao,
    "Concorrência": BidModality.concorrencia,
    "Tomada de Preços": BidModality.tomada_preco,
    "Convite": BidModality.convite,
    "Dispensa": BidModality.dispensa,
    "Inexigibilidade": BidModality.inexigibilidade,
}


def _parse_decimal(val: Optional[str]) -> Optional[float]:
    if not val:
        return None
    val = re.sub(r"[R$\s\.]", "", val).replace(",", ".")
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(val.strip()[:len(fmt)], fmt).date()
        except ValueError:
            continue
    return None


def _parse_row(row) -> Optional[dict]:
    try:
        cells = row.find_all("td")
        if len(cells) < 5:
            return None

        external_id = cells[0].get_text(strip=True)
        if not external_id:
            return None

        modality_str = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        organ = cells[2].get_text(strip=True) if len(cells) > 2 else None
        title = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        closing_raw = cells[4].get_text(strip=True) if len(cells) > 4 else None
        closing = _parse_date(closing_raw)

        if closing and closing < date.today():
            return None

        link = row.find("a")
        detail_url = None
        if link and link.get("href"):
            href = link["href"]
            detail_url = href if href.startswith("http") else BASE_URL + href

        return {
            "external_id": f"celic_{external_id}",
            "source": "celic_rs",
            "title": title[:500],
            "description": title,
            "sphere": BidSphere.estadual,
            "state": "RS",
            "city": None,
            "city_code": None,
            "organ_name": organ,
            "organ_cnpj": None,
            "publication_date": None,
            "opening_date": None,
            "closing_date": closing,
            "status": BidStatus.aberta,
            "estimated_value": None,
            "maximum_value": None,
            "modality": MODALITY_MAP.get(modality_str, BidModality.pregao),
            "edital_url": detail_url,
            "details_url": detail_url,
            "platform_url": BASE_URL,
            "last_scraped": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    except Exception:
        return None


class CelicRSScraper(BasePortalScraper):
    source_key = "celic_rs"
    source_name = "CELIC RS"

    async def fetch_bids(self, client: httpx.AsyncClient, days_back: int) -> list[dict]:
        bids: list[dict] = []
        date_from = (date.today() - timedelta(days=days_back)).strftime("%d/%m/%Y")
        date_to = date.today().strftime("%d/%m/%Y")
        page = 0

        while True:
            try:
                resp = await client.get(SEARCH_URL, params={
                    "situacao": "Aberta",
                    "dtAbertura": date_from,
                    "dtAbertura": date_to,
                    "page": str(page),
                    "size": "50",
                }, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
                    "Referer": BASE_URL,
                })
                resp.raise_for_status()
            except Exception as e:
                logger.warning(f"CELIC RS pág {page}: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table tbody tr, .licitacao-row")
            if not rows:
                break

            for row in rows:
                bid = _parse_row(row)
                if bid:
                    bids.append(bid)

            next_page = soup.select_one("a.next, a[aria-label='Next']")
            if not next_page:
                break
            page += 1

        return bids


_scraper = CelicRSScraper()


async def sync_celic_rs(days_back: int = 1):
    return await _scraper.sync(days_back=days_back)
