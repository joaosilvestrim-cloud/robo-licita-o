"""DOU via Querido Diário (OKBR) — avisos de licitação em diários oficiais municipais.

NOTA: O QD indexa gazettes com delay de semanas a meses. Não usamos filtro de data
na query — buscamos os N gazettes mais recentes por território e importamos tudo
que ainda tem prazo aberto (ou sem prazo explícito). O cleanup job cuida do resto.
"""
import hashlib
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from sqlmodel import select
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.source_tracker import update_source_status

logger = logging.getLogger(__name__)

API_BASE = "https://api.queridodiario.ok.org.br"

# Territórios cobertos pelo QD com boa cobertura (IBGE 7 dígitos)
# Foco: região Sorocaba/Campinas/Jundiaí raio 200km + SP capital
TERRITORY_IDS = [
    "3550308",  # São Paulo capital       ← melhor cobertura do QD
    "3509502",  # Campinas
    "3548708",  # São Bernardo do Campo
    "3549805",  # Santo André
    "3531902",  # Osasco
    "3529401",  # Mogi das Cruzes
    "3533809",  # Piracicaba
    "3543303",  # Ribeirão Preto
    "3552205",  # Sorocaba
    "3525904",  # Jundiaí
    "3520509",  # Indaiatuba
    "3523800",  # Itu
    "3522307",  # Itapetininga
    "3505708",  # Barueri
    "3543907",  # Rio Claro
    "3546801",  # Santos
    "3519055",  # Itatiba
]

KEYWORDS = [
    "aviso de licitação",
    "aviso de pregão",
    "edital de licitação",
    "dispensa de licitação",
]

# Regex para datas de encerramento/abertura no texto
DATE_RE  = re.compile(r"(?:encerramento|prazo[^:]*:|abertura)[^\d]*(\d{2}/\d{2}/\d{4})", re.I)
VALUE_RE = re.compile(r"R\$\s*([\d.,]+)", re.I)
PROC_RE  = re.compile(r"(?:processo|pregão|edital)[^\d]*n[º°.]?\s*[\d./\-]+", re.I)


def _extract_closing(text: str) -> Optional[date]:
    for m in DATE_RE.finditer(text):
        try:
            d = datetime.strptime(m.group(1), "%d/%m/%Y").date()
            if d >= date.today():          # só datas futuras são úteis
                return d
        except ValueError:
            continue
    return None


def _extract_value(text: str) -> Optional[float]:
    m = VALUE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return None


def _excerpt_id(gazette_url: str, idx: int) -> str:
    h = hashlib.md5(f"{gazette_url}:{idx}".encode()).hexdigest()[:16]
    return f"qd_{h}"


def _map_gazette(gazette: dict, excerpt_text: str, excerpt_idx: int) -> Optional[dict]:
    territory_id = gazette.get("territory_id", "")
    city         = gazette.get("territory_name") or "SP"
    gazette_url  = gazette.get("url") or gazette.get("txt_url") or ""

    pub_date: Optional[date] = None
    try:
        pub_date = datetime.fromisoformat((gazette.get("date") or "")[:10]).date()
    except Exception:
        pass

    # Se gazette muito antigo (mais de 180 dias) e sem data de encerramento futura, pula
    closing = _extract_closing(excerpt_text)
    if pub_date and not closing:
        age = (date.today() - pub_date).days
        if age > 180:
            return None

    external_id = _excerpt_id(gazette_url, excerpt_idx)
    value       = _extract_value(excerpt_text)

    # Título: primeira linha não-vazia do trecho
    lines = [l.strip() for l in excerpt_text.splitlines() if l.strip()]
    title = lines[0][:500] if lines else "Aviso de Licitação"

    return {
        "external_id": external_id,
        "source": "dou",
        "title": title,
        "description": excerpt_text[:2000],
        "sphere": BidSphere.municipal,
        "state": gazette.get("state_code") or "SP",
        "city": city,
        "city_code": territory_id[:7] if territory_id else None,
        "organ_name": None,
        "organ_cnpj": None,
        "publication_date": pub_date,
        "opening_date": None,
        "closing_date": closing,
        "status": BidStatus.aberta,
        "estimated_value": value,
        "maximum_value": None,
        "modality": None,
        "edital_url": gazette_url or None,
        "details_url": gazette_url or None,
        "last_scraped": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def sync_querido_diario(days_back: int = 1):
    """
    days_back: ignorado para a query QD (que não filtra por data de forma confiável).
    Busca os N gazettes mais recentes por território com as keywords de licitação.
    """
    start_time = datetime.utcnow()
    log = ScrapeLog(source="dou", start_time=start_time)
    inserted = updated = found = 0

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for keyword in KEYWORDS:
                for territory_id in TERRITORY_IDS:
                    try:
                        resp = await client.get(f"{API_BASE}/gazettes", params={
                            "territory_ids": territory_id,
                            "querystring": keyword,
                            "size": 5,              # 5 gazettes mais recentes por território×keyword
                            "excerpt_size": 800,
                            "number_of_excerpts": 2,
                        })
                        if resp.status_code != 200:
                            continue
                        data = resp.json()
                    except Exception as e:
                        logger.debug(f"QD {territory_id}/{keyword}: {e}")
                        continue

                    gazettes = data.get("gazettes") or []
                    found += len(gazettes)

                    async with AsyncSessionLocal() as session:
                        for gazette in gazettes:
                            excerpts = gazette.get("excerpts") or []
                            for idx, excerpt in enumerate(excerpts):
                                bid_data = _map_gazette(gazette, excerpt, idx)
                                if not bid_data:
                                    continue

                                result = await session.execute(
                                    select(PublicBid).where(
                                        PublicBid.source == "dou",
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

        log.status = ScrapeStatus.sucesso

    except Exception as e:
        logger.exception("Erro ao sincronizar Querido Diário")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time      = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated  = updated

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    await update_source_status("dou", log.status, inserted + updated)
    logger.info(f"DOU/QD sync: found={found} inserted={inserted} updated={updated} status={log.status}")
    return log
