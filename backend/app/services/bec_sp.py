"""BEC/SP — Bolsa Eletrônica de Compras do Estado de São Paulo (SOAP Webservice)."""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from typing import Optional
import httpx
from sqlmodel import select
from app.db.models import PublicBid, ScrapeLog, BidStatus, BidSphere, BidModality, ScrapeStatus
from app.database import AsyncSessionLocal
from app.services.source_tracker import update_source_status

logger = logging.getLogger(__name__)

# ATENÇÃO: endpoint SOAP retorna 404 (descontinuado).
# A página pública requer sessão JavaScript — não é acessível via HTTP simples.
# BEC/SP está sendo descontinuado em favor do PNCP/Compras.gov.br desde 2024.
# Integração futura requer Playwright (headless browser).
WSDL_URL   = "https://www.bec.sp.gov.br/BECSP_ServicoIntegracao_OC/ListaOC.asmx"
SOAP_NS    = "http://schemas.xmlsoap.org/soap/envelope/"
BEC_NS     = "https://www.bec.sp.gov.br/webservices/"
SOAP_ACTION = "https://www.bec.sp.gov.br/webservices/ListaOC"

MODALITY_MAP = {
    "PREGÃO ELETRÔNICO": BidModality.pregao,
    "PREGÃO PRESENCIAL": BidModality.pregao,
    "CONCORRÊNCIA":      BidModality.concorrencia,
    "DISPENSA":          BidModality.dispensa,
    "INEXIGIBILIDADE":   BidModality.inexigibilidade,
    "CONVITE":           BidModality.convite,
    "TOMADA DE PREÇOS":  BidModality.tomada_preco,
    "LEILÃO":            BidModality.leilao,
}


def _soap_envelope(date_from: str, date_to: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:bec="{BEC_NS}">
  <soap:Header/>
  <soap:Body>
    <bec:ListaOC>
      <bec:strDataInicio>{date_from}</bec:strDataInicio>
      <bec:strDataFim>{date_to}</bec:strDataFim>
    </bec:ListaOC>
  </soap:Body>
</soap:Envelope>"""


def _parse_decimal(val) -> Optional[float]:
    if not val:
        return None
    try:
        return float(str(val).replace(",", ".").replace("R$", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_date_bec(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d%m%Y"):
        try:
            return datetime.strptime(val.strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


def _map_item(item_el: ET.Element) -> Optional[dict]:
    def txt(tag: str) -> Optional[str]:
        el = item_el.find(f".//{tag}") or item_el.find(tag)
        return (el.text or "").strip() if el is not None else None

    external_id = txt("NumOC") or txt("NrOC") or txt("OC")
    if not external_id:
        return None

    closing = _parse_date_bec(txt("DtEncerramentoProposta") or txt("DtEncerramento") or txt("DtFim"))
    today = date.today()
    if closing and closing < today:
        return None

    modality_raw = (txt("TpPregao") or txt("Modalidade") or "").upper()
    modality = next((v for k, v in MODALITY_MAP.items() if k in modality_raw), None)

    organ = txt("NomeOrgao") or txt("Orgao") or txt("Entidade")
    city  = txt("Municipio") or txt("Cidade")
    state = txt("UF") or "SP"

    title = txt("ObjetoResumido") or txt("Objeto") or txt("DescricaoObjeto") or ""

    return {
        "external_id": external_id,
        "source": "bec_sp",
        "title": title[:500],
        "description": txt("InformacoesComplementares") or title,
        "sphere": BidSphere.estadual,
        "state": state,
        "city": city,
        "city_code": None,
        "organ_name": organ,
        "organ_cnpj": None,
        "publication_date": _parse_date_bec(txt("DtPublicacao") or txt("DtAbertura")),
        "opening_date": _parse_date_bec(txt("DtAberturaProposta") or txt("DtAbertura")),
        "closing_date": closing,
        "status": BidStatus.aberta,
        "estimated_value": _parse_decimal(txt("VlEstimado") or txt("ValorEstimado")),
        "maximum_value": None,
        "modality": modality,
        "edital_url": txt("Link") or txt("UrlEdital"),
        "details_url": txt("Link") or None,
        "last_scraped": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def sync_bec_sp(days_back: int = 1):
    start_time = datetime.utcnow()
    log = ScrapeLog(source="bec_sp", start_time=start_time)
    inserted = updated = found = 0

    # BEC/SP endpoint descontinuado — retorna 404.
    # Requer headless browser para funcionar. Pulando silenciosamente.
    log.end_time = datetime.utcnow()
    log.status = ScrapeStatus.parcial
    log.error_message = "Endpoint SOAP descontinuado (404). Página pública requer JS/session. Aguardando integração via Playwright."
    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()
    await update_source_status("bec_sp", "parcial", 0)
    logger.warning("BEC/SP: pulando sync — endpoint descontinuado")
    return log

    # Código original preservado abaixo (para quando headless browser for implementado):
    try:
        date_from = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
        date_to   = date.today().strftime("%Y%m%d")
        envelope  = _soap_envelope(date_from, date_to)

        async with httpx.AsyncClient(timeout=60, verify=False) as client:
            resp = await client.post(
                WSDL_URL,
                content=envelope.encode("utf-8"),
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": SOAP_ACTION,
                },
            )
            resp.raise_for_status()
            xml_text = resp.text

        root = ET.fromstring(xml_text)
        # Remove namespaces para facilitar busca
        for el in root.iter():
            el.tag = re.sub(r"\{[^}]+\}", "", el.tag)

        items = root.findall(".//OC") or root.findall(".//Item") or root.findall(".//Licitacao")
        found = len(items)

        async with AsyncSessionLocal() as session:
            for item_el in items:
                bid_data = _map_item(item_el)
                if not bid_data:
                    continue

                result = await session.execute(
                    select(PublicBid).where(
                        PublicBid.source == "bec_sp",
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
        logger.exception("Erro ao sincronizar BEC/SP")
        log.status = ScrapeStatus.erro
        log.error_message = str(e)[:500]

    log.end_time = datetime.utcnow()
    log.records_found = found
    log.records_inserted = inserted
    log.records_updated = updated

    async with AsyncSessionLocal() as session:
        session.add(log)
        await session.commit()

    await update_source_status("bec_sp", log.status, inserted + updated)
    logger.info(f"BEC/SP sync: found={found} inserted={inserted} updated={updated} status={log.status}")
    return log
