"""Cache de centroides de municípios brasileiros via IBGE Malhas API.

Busca o GeoJSON de municípios do IBGE (uma vez por estado), computa o
centroide de cada polígono e guarda em memória. Chamadas subsequentes
para o mesmo estado respondem instantaneamente.
"""
import asyncio
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

# {uf → [{ibge_code, lat, lng}]}
_cache: dict[str, list[dict]] = {}
_lock = asyncio.Lock()

IBGE_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
    "?intrarregiao=municipio&formato=application/vnd.geo+json"
)


def _ring_centroid(coords: list) -> tuple[float, float]:
    n = len(coords)
    if n == 0:
        return 0.0, 0.0
    return sum(c[1] for c in coords) / n, sum(c[0] for c in coords) / n


def _geometry_centroid(geom: dict) -> tuple[float, float]:
    gtype = geom.get("type", "")
    rings = geom.get("coordinates", [])
    if gtype == "Polygon":
        return _ring_centroid(rings[0])
    if gtype == "MultiPolygon":
        # usa o polígono com mais vértices (geralmente o maior)
        outer_rings = [p[0] for p in rings if p]
        biggest = max(outer_rings, key=len)
        return _ring_centroid(biggest)
    return 0.0, 0.0


async def get_state_centroids(state: str) -> list[dict]:
    """Retorna [{ibge_code, lat, lng}] para todos os municípios do estado.

    Resultado é cacheado em memória para toda a vida do processo.
    """
    state = state.upper().strip()

    async with _lock:
        if state in _cache:
            return _cache[state]

    logger.info(f"geo_cache: buscando municípios de {state} no IBGE…")
    url = IBGE_URL.format(uf=state)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, headers={"Accept": "application/geo+json"})
            resp.raise_for_status()
            geojson = resp.json()
    except Exception as e:
        logger.warning(f"geo_cache: falha ao buscar {state}: {e}")
        return []

    result: list[dict] = []
    for feat in geojson.get("features", []):
        code = str(feat.get("properties", {}).get("codarea", "")).strip()
        if not code:
            continue
        geom = feat.get("geometry") or {}
        lat, lng = _geometry_centroid(geom)
        if lat == 0.0 and lng == 0.0:
            continue
        result.append({"ibge_code": code, "lat": round(lat, 5), "lng": round(lng, 5)})

    async with _lock:
        _cache[state] = result

    logger.info(f"geo_cache: {len(result)} centroides de {state} cacheados")
    return result


def clear_cache():
    _cache.clear()
