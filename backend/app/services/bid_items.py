"""Itens de uma licitação (o que está sendo comprado, item a item).

Fonte: API principal do PNCP (/api/pncp/v1/.../itens). Busca sob demanda e
cacheia — cada licitação faz 1 chamada externa só.
"""
import re
import logging
import httpx

logger = logging.getLogger(__name__)

PNCP_API = "https://pncp.gov.br/api/pncp/v1"
_UA = {"Accept": "application/json"}


def _parse_external(external_id: str):
    m = re.match(r"^(\d+)-(\d+)-0*(\d+)/(\d+)$", external_id or "")
    if not m:
        return None
    cnpj, _tipo, seq, ano = m.groups()
    return {"cnpj": cnpj, "seq": seq, "ano": ano}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def get_items(external_id: str) -> dict:
    p = _parse_external(external_id)
    if not p:
        return {"has_items": False, "items": [], "reason": "id_invalido"}
    cnpj, ano, seq = p["cnpj"], p["ano"], p["seq"]
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                params={"pagina": 1, "tamanhoPagina": 100},
                headers=_UA,
            )
            raw = resp.json() if resp.status_code == 200 else []
            if not isinstance(raw, list):
                raw = []
    except Exception as e:
        logger.warning(f"get_items erro {external_id}: {e}")
        return {"has_items": False, "items": [], "reason": "erro_consulta"}

    items = []
    total = 0.0
    for it in raw:
        vt = _f(it.get("valorTotal")) or 0.0
        total += vt
        items.append({
            "numero": it.get("numeroItem"),
            "descricao": (it.get("descricao") or "").strip(),
            "tipo": it.get("materialOuServicoNome"),
            "quantidade": _f(it.get("quantidade")),
            "unidade": it.get("unidadeMedida"),
            "valor_unitario": _f(it.get("valorUnitarioEstimado")),
            "valor_total": vt or None,
            "criterio": it.get("criterioJulgamentoNome"),
            "situacao": it.get("situacaoCompraItemNome"),
            "beneficio": it.get("tipoBeneficioNome"),
        })
    items.sort(key=lambda x: (x["numero"] is None, x["numero"] or 0))
    return {
        "has_items": bool(items),
        "count": len(items),
        "estimated_total": round(total, 2) if total else None,
        "items": items,
    }


async def get_files(external_id: str) -> dict:
    """Arquivos/documentos do edital (PDF, termo de referência...) do PNCP."""
    p = _parse_external(external_id)
    if not p:
        return {"has_files": False, "files": [], "reason": "id_invalido"}
    cnpj, ano, seq = p["cnpj"], p["ano"], p["seq"]
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
                params={"pagina": 1, "tamanhoPagina": 50},
                headers=_UA,
            )
            raw = resp.json() if resp.status_code == 200 else []
            if not isinstance(raw, list):
                raw = []
    except Exception as e:
        logger.warning(f"get_files erro {external_id}: {e}")
        return {"has_files": False, "files": [], "reason": "erro_consulta"}

    files = [{
        "titulo": (it.get("titulo") or it.get("nomeArquivo") or f"Documento {i+1}"),
        "url": it.get("url") or it.get("uri"),
        "tipo": it.get("tipoDocumentoNome"),
        "data": (it.get("dataPublicacaoPncp") or "")[:10] or None,
    } for i, it in enumerate(raw) if (it.get("url") or it.get("uri"))]
    return {"has_files": bool(files), "count": len(files), "files": files}
