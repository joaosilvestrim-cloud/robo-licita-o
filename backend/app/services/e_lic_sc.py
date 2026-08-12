"""e-lic SC — Portal de Licitações Eletrônicas de Santa Catarina (e-lic.sc.gov.br)."""
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from app.db.models import BidStatus, BidSphere, BidModality
from app.services.base_portal import BasePortalScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://e-lic.sc.gov.br"
SEARCH_URL = f"{BASE_URL}/index.php/licitacoes/pesquisar"


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
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_row(row) -> Optional[dict]:
    try:
        cells = row.find_all("td")
        if len(cells) < 4:
            return None

        external_id = cells[0].get_text(strip=True)
        if not external_id:
            return None

        organ = cells[1].get_text(strip=True) if len(cells) > 1 else None
        title = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        closing_raw = cells[3].get_text(strip=True) if len(cells) > 3 else None
        closing = _parse_date(closing_raw)

        if closing and closing < date.today():
            return None

        link = cells[0].find("a")
        detail_url = (BASE_URL + link["href"]) if link and link.get("href") else None

        return {
            "external_id": f"elic_{external_id}",
            "source": "e_lic_sc",
            "title": title[:500],
            "description": title,
            "sphere": BidSphere.estadual,
            "state": "SC",
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
            "modality": BidModality.pregao,
            "edital_url": detail_url,
            "details_url": detail_url,
            "platform_url": BASE_URL,
            "last_scraped": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    except Exception:
        return None


class ELicSCScraper(BasePortalScraper):
    source_key = "e_lic_sc"
    source_name = "e-lic SC"

    async def fetch_bids(self, client: httpx.AsyncClient, days_back: int) -> list[dict]:
        bids: list[dict] = []
        date_from = (date.today() - timedelta(days=days_back)).strftime("%d/%m/%Y")
        date_to = date.today().strftime("%d/%m/%Y")
        page = 1

        while True:
            try:
                resp = await client.post(SEARCH_URL, data={
                    "situacao": "A",
                    "dtAberturaInicio": date_from,
                    "dtAberturaFim": date_to,
                    "pagina": str(page),
                }, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Acrasystem/1.0)",
                    "Referer": BASE_URL,
                })
                resp.raise_for_status()
            except Exception as e:
                logger.warning(f"e-lic SC pág {page}: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table tbody tr")
            if not rows:
                break

            for row in rows:
                bid = _parse_row(row)
                if bid:
                    bids.append(bid)

            if not soup.select_one("a.proxima, a[title='Próxima']"):
                break
            page += 1

        return bids


_scraper = ELicSCScraper()


async def sync_e_lic_sc(days_back: int = 1):
    return await _scraper.sync(days_back=days_back)
