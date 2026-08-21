"""Inteligência de concorrência — quem disputou e quem venceu uma licitação.

Fonte: API do PNCP (itens + resultados por item).
IMPORTANTE: itens/resultados ficam na API principal (/api/pncp/v1), NÃO na de
consulta (/api/consulta/v1). Cada resultado traz a ordem de classificação, a
situação (vencedor/desclassificado/informado) e o valor homologado — é o que
permite montar a "análise dos licitantes" (1º, 2º, 3º lugar) por item.

As propostas são sigilosas até a sessão; o resultado só é público após a
homologação. Por isso só há dados para licitações já encerradas/homologadas.
"""
import re
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

PNCP_API = "https://pncp.gov.br/api/pncp/v1"   # itens e resultados
_MAX_ITEMS = 8  # limita chamadas externas por licitação (protege a instância)


def _parse_external(external_id: str):
    # formato: CNPJ-tipo-000SEQ/ANO  (ex.: 18400945000166-1-000039/2024)
    m = re.match(r"^(\d+)-(\d+)-0*(\d+)/(\d+)$", external_id or "")
    if not m:
        return None
    cnpj, _tipo, seq, ano = m.groups()
    return {"cnpj": cnpj, "seq": seq, "ano": ano}


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


async def get_competitors(external_id: str) -> dict:
    """Monta a análise dos licitantes de uma licitação a partir dos resultados
    por item do PNCP. Retorna o ranking por item + agregado por fornecedor."""
    p = _parse_external(external_id)
    if not p:
        return {"has_result": False, "winners": [], "items": [], "reason": "id_invalido"}

    cnpj, ano, seq = p["cnpj"], p["ano"], p["seq"]
    winners: dict[str, dict] = {}
    items_out: list[dict] = []
    estimated_total = 0.0
    homologated_total = 0.0

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
                params={"pagina": 1, "tamanhoPagina": 100},
                headers={"Accept": "application/json"},
            )
            items = resp.json() if resp.status_code == 200 else []
            if not isinstance(items, list):
                items = []

            # prioriza itens que já têm resultado; limita p/ proteger a instância
            with_res = [it for it in items if it.get("numeroItem") is not None and it.get("temResultado")]
            sample = (with_res or [it for it in items if it.get("numeroItem") is not None])[:_MAX_ITEMS]

            async def _fetch_res(ni):
                try:
                    r2 = await client.get(
                        f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{ni}/resultados",
                        headers={"Accept": "application/json"},
                    )
                    return r2.json() if r2.status_code == 200 else []
                except Exception:
                    return []

            all_results = await asyncio.gather(*[_fetch_res(it["numeroItem"]) for it in sample])

            for item, results in zip(sample, all_results):
                if not isinstance(results, list):
                    results = []
                est = _f(item.get("valorTotal"))          # valor estimado do item
                estimated_total += est

                parsed = []
                for r in results:
                    doc = str(r.get("niFornecedor") or "").strip()
                    if not doc:
                        continue
                    vtot = _f(r.get("valorTotalHomologado"))
                    is_winner = vtot > 0 and not r.get("dataCancelamento")
                    parsed.append({
                        "name": r.get("nomeRazaoSocialFornecedor") or "—",
                        "document": doc,
                        "porte": r.get("porteFornecedorNome"),
                        "ordem": r.get("ordemClassificacaoSrp"),
                        "situacao": r.get("situacaoCompraItemResultadoNome") or ("Vencedor" if is_winner else "—"),
                        "valor_total": round(vtot, 2),
                        "valor_unitario": round(_f(r.get("valorUnitarioHomologado")), 2),
                        "desconto": r.get("percentualDesconto"),
                        "is_winner": is_winner,
                    })
                    if is_winner:
                        homologated_total += vtot
                        w = winners.setdefault(doc, {
                            "document": doc,
                            "name": r.get("nomeRazaoSocialFornecedor") or "—",
                            "total_value": 0.0,
                            "items_won": 0,
                            "porte": r.get("porteFornecedorNome"),
                        })
                        w["total_value"] += vtot
                        w["items_won"] += 1

                # ordena: quem tem ordem primeiro (1,2,3...), depois vencedor, depois resto
                parsed.sort(key=lambda x: (x["ordem"] is None, x["ordem"] or 999, not x["is_winner"]))
                if parsed:
                    items_out.append({
                        "numero": item.get("numeroItem"),
                        "descricao": (item.get("descricao") or "")[:400],
                        "situacao": item.get("situacaoCompraItemNome"),
                        "valor_estimado": round(est, 2) if est else None,
                        "results": parsed,
                    })
    except Exception as e:
        logger.warning(f"get_competitors erro {external_id}: {e}")
        return {"has_result": False, "winners": [], "items": [], "reason": "erro_consulta"}

    ordered = sorted(winners.values(), key=lambda x: x["total_value"], reverse=True)
    for w in ordered:
        w["total_value"] = round(w["total_value"], 2)

    return {
        "has_result": bool(items_out),
        "items_checked": len(items_out),
        "estimated_total": round(estimated_total, 2) if estimated_total else None,
        "homologated_total": round(homologated_total, 2) if homologated_total else None,
        "winners": ordered,
        "items": items_out,
    }
