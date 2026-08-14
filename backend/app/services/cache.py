"""Cache TTL em memória (processo único no Render free).

Reduz o custo de endpoints pesados (ranking de TI, mapa, dashboard) que
recalculam sobre milhares de linhas. Como os dados só mudam nos syncs,
um TTL de 1-3 min deixa a navegação instantânea sem defasagem relevante.
"""
import time

_store: dict = {}
_MAX = 500  # trava simples contra crescimento infinito


def cache_get(key: str):
    v = _store.get(key)
    if v and v[0] > time.monotonic():
        return v[1]
    if v:
        _store.pop(key, None)
    return None


def cache_set(key: str, value, ttl: int = 180):
    if len(_store) > _MAX:
        _store.clear()
    _store[key] = (time.monotonic() + ttl, value)
