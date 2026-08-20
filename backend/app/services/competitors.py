"""Inteligência de concorrência — quem venceu uma licitação e por quanto.

Fonte: endpoint de resultados por item do PNCP
(/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{numeroItem}/resultados).
As propostas são sigilosas até a sessão; o vencedor só é público após a
homologação. Por isso só há dados para licitações já encerradas/homologadas.
"""
import re
import logging
import httpx

logger = logging.getLogger(__name__)

PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"
_MAX_ITEMS = 15  # limita chamadas externas por licitação


def _parse_external(external_id: str):
    m = re.match(r"^(\d+)-(\d+)-0*(\d+)/(\d+)$", external_id or "")
    if not m:
        return None
    cnpj, tipo, seq, ano = m.groups()
    return {"cnpj": cnpj, "seq": seq, "ano": ano}


async def get_competitors(external_id: str) -> dict:
    """Agrega os vencedores de uma licitação a partir dos resultados por item."""
    p = _parse_external(external_id)
    if not p:
        return {"has_result": False, "winners": [], "reason": "id_invalido"}

    cnpj, ano, seq = p["cnpj"], p["ano"], p["seq"]
    winners: dict[str, dict] = {}
    items_checked = 0

    try:
        async with httpx.AsyncClient(timeout=20, verify=False) as client:
            resp = await client.get(
                f"{PNCP_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                params={"pagina": 1, "tamanhoPagina": 50},
                headers={"Accept": "application/json"},
            )
            items = resp.json() if resp.status_code == 200 else []
            if not isinstance(items, list):
                items = []

            for item in items[:_MAX_ITEMS]:
                ni = item.get("numeroItem")
                if ni is None:
                    continue
                items_checked += 1
                try:
                    r2 = await client.get(
                        f"{PNCP_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{ni}/resultados",
                        headers={"Accept": "application/json"},
                    )
                    results = r2.json() if r2.status_code == 200 else []
                except Exception:
                    results = []
                if not isinstance(results, list):
                    continue
                for r in results:
                    doc = str(r.get("niFornecedor") or "").strip()
                    if not doc:
                        continue
                    val = r.get("valorTotalHomologado") or r.get("valorUnitarioHomologado") or 0
                    try:
                        val = float(val)
                    except (TypeError, ValueError):
                        val = 0.0
                    w = winners.setdefault(doc, {
                        "document": doc,
                        "name": r.get("nomeRazaoSocialFornecedor") or "—",
                        "total_value": 0.0,
                        "items_won": 0,
                        "porte": r.get("porteFornecedorNome"),
                    })
                    w["total_value"] += val
                    w["items_won"] += 1
    except Exception as e:
        logger.warning(f"get_competitors erro {external_id}: {e}")
        return {"has_result": False, "winners": [], "reason": "erro_consulta"}

    ordered = sorted(winners.values(), key=lambda x: x["total_value"], reverse=True)
    for w in ordered:
        w["total_value"] = round(w["total_value"], 2)

    return {
        "has_result": bool(ordered),
        "items_checked": items_checked,
        "winners": ordered,
    }
