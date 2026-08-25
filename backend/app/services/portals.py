"""Identifica o portal de ORIGEM de uma licitação a partir da URL do sistema
de origem que o PNCP fornece (linkSistemaOrigem). Assim mostramos "de qual
portal veio" (Comprasnet, BLL, Licitações-e, Betha...) sem raspar cada portal —
a licitação já vem pra nós pelo PNCP, só falta a etiqueta."""
from urllib.parse import urlparse

# substring no domínio -> nome amigável do portal
_MAP = [
    ("portaldecompraspublicas", "Portal de Compras Públicas"),
    ("licitacoes-e", "Licitações-e (BB)"),
    ("licitanet", "Licitanet"),
    ("bllcompras", "BLL Compras"),
    ("bll.org", "BLL Compras"),
    ("bnc.org", "BNC"),
    ("bncompras", "BNC"),
    ("comprasnet.ba", "Compras Bahia"),
    ("e-lic", "e-Lic Santa Catarina"),
    ("celic.rs", "Compras RS (Celic)"),
    ("procergs", "Procergs (RS)"),
    ("compras.rs", "Compras RS"),
    ("compras.rj", "Compras RJ"),
    ("comprasgoias", "Compras Goiás"),
    ("goias.gov", "Compras Goiás"),
    ("e-compras.am", "Compras Amazonas"),
    ("amazonas.gov", "Compras Amazonas"),
    ("recife", "Compras Recife"),
    ("compras.mg", "Compras Minas Gerais"),
    ("mg.gov", "Compras Minas Gerais"),
    ("banrisul", "Banrisul"),
    ("banpara", "Banpará"),
    ("peintegrado", "PE Integrado"),
    ("pe.gov", "PE Integrado"),
    ("bec.sp", "BEC/SP"),
    ("caixa", "Licitações Caixa"),
    ("licitacoescaixa", "Licitações Caixa"),
    ("betha", "Betha Sistemas"),
    ("equiplano", "Equiplano"),
    ("publicnet", "PublicNet"),
    ("ammlicita", "AMM Licita"),
    ("amm licita", "AMM Licita"),
    ("cidadecompras", "Cidade Compras"),
    ("bnccompras", "BNC"),
    ("licitardigital", "Licitar Digital"),
    ("licitamaisbrasil", "Licita Mais Brasil"),
    ("comprasbr", "ComprasBR"),
    ("sigep", "SIGEP"),
    ("comprasgovernamentais", "Compras.gov.br (Comprasnet)"),
    ("comprasnet", "Compras.gov.br (Comprasnet)"),
    ("gov.br/compras", "Compras.gov.br (Comprasnet)"),
    ("compras.gov", "Compras.gov.br (Comprasnet)"),
    ("pncp.gov", "PNCP (direto)"),
]

# domínios que NÃO são portais de compra (só hospedam o PDF do edital) -> Outros
_GENERIC = ("google.", "drive.google", "dropbox", "onedrive", "sharepoint",
            "sei.", "transparencia", "tce.", "diario", "imprensaoficial",
            "precodereferencia", "m2atecnologia", "empro.", "srv.br",
            "s3.amazonaws", "blob.core", "storage.")


def portal_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        u = url.lower()
        host = urlparse(u).netloc or u
    except Exception:
        host = (url or "").lower()
    hay = f"{host} {url.lower()}"
    for needle, name in _MAP:
        if needle in hay:
            return name
    if any(g in hay for g in _GENERIC):
        return "Outros / PNCP"
    # desconhecido: usa o domínio “limpo” como rótulo
    host = host.replace("www.", "")
    return (host.split(":")[0] if host else None) or "Outros / PNCP"


async def backfill_portals(limit: int = 4000):
    """Preenche source_portal nas licitações que ainda não têm, a partir da URL
    de origem (edital_url/details_url). Roda em lote, seguro para reexecução."""
    import logging
    from datetime import datetime
    from sqlmodel import select, or_
    from app.db.models import PublicBid, ScrapeLog, ScrapeStatus
    from app.database import AsyncSessionLocal
    log = logging.getLogger(__name__)
    start = datetime.utcnow()
    updated = 0
    try:
        async with AsyncSessionLocal() as session:
            # pega sem etiqueta OU com etiqueta de dominio cru (contém ".") para
            # reaplicar o mapa melhorado
            rows = (await session.execute(
                select(PublicBid).where(
                    PublicBid.source == "pncp",
                    or_(PublicBid.source_portal == None,          # noqa: E711
                        PublicBid.source_portal.like("%.%")),
                ).limit(limit)
            )).scalars().all()
            for b in rows:
                p = portal_from_url(b.edital_url or b.details_url)
                if p and p != b.source_portal:
                    b.source_portal = p[:60]
                    updated += 1
            await session.commit()
        async with AsyncSessionLocal() as session:
            session.add(ScrapeLog(source="portals", start_time=start, end_time=datetime.utcnow(),
                        status=ScrapeStatus.sucesso, records_found=len(rows),
                        records_inserted=0, records_updated=updated))
            await session.commit()
    except Exception as e:
        log.warning(f"backfill_portals erro: {e}")
    return {"updated": updated}
