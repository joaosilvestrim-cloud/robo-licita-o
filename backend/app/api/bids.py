from datetime import date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import PublicBid, BidStatus, BidSphere, BidModality, ObjectType, User, ProcurementProfile, Tenant
from app.auth import get_current_user
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/api/bids", tags=["bids"])

# ── Busca insensível a acento (sem depender de extensão no banco) ──────────────
import unicodedata
_ACCENTS_FROM = "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ"
_ACCENTS_TO   = "aaaaaeeeeiiiiooooouuuucaaaaaeeeeiiiiooooouuuuc"


def _fold_py(s: str) -> str:
    """Remove acentos e baixa a caixa (lado do termo buscado)."""
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()


def _fold_col(col):
    """Dobra acentos e baixa a caixa da coluna, no SQL."""
    return func.translate(func.lower(col), _ACCENTS_FROM, _ACCENTS_TO)


@router.get("/geo/cities")
async def city_geo_stats(
    state: str = Query(..., min_length=2, max_length=2, description="Sigla do estado (SP, RJ…)"),
    status: Optional[BidStatus] = Query(BidStatus.aberta),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Agrega licitações por cidade com coordenadas (centroide do município via IBGE)."""
    from app.services.geo_cache import get_state_centroids

    result = await session.execute(
        select(PublicBid).where(
            PublicBid.state.ilike(state.strip()),
            *([] if not status else [PublicBid.status == status]),
        )
    )
    bids = result.scalars().all()

    city_stats: dict[str, dict] = {}
    for b in bids:
        code = (b.city_code or "").strip()
        if not code:
            continue
        if code not in city_stats:
            city_stats[code] = {"city": b.city or "", "count": 0, "total_value": 0.0}
        city_stats[code]["count"] += 1
        city_stats[code]["total_value"] += float(b.estimated_value or 0)

    if not city_stats:
        return {"state": state.upper(), "cities": []}

    centroids = await get_state_centroids(state)
    by_code = {c["ibge_code"]: c for c in centroids}

    cities = []
    for code, stats in city_stats.items():
        # tenta match direto (7 dígitos) e pelo prefixo de 6 dígitos
        pt = by_code.get(code) or by_code.get(code[:6])
        if not pt:
            continue
        cities.append({
            "city_code": code,
            "city":       stats["city"],
            "lat":        pt["lat"],
            "lng":        pt["lng"],
            "count":      stats["count"],
            "total_value": round(stats["total_value"], 2),
        })

    cities.sort(key=lambda x: x["count"], reverse=True)
    return {"state": state.upper(), "cities": cities}


@router.get("/geo")
async def bid_geo_stats(
    status: Optional[BidStatus] = Query(BidStatus.aberta),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Agrega licitações por estado para o mapa de calor."""
    ck = f"geo:{status}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    stmt = select(PublicBid)
    if status:
        stmt = stmt.where(PublicBid.status == status)

    result = await session.execute(stmt)
    bids = result.scalars().all()

    state_stats: dict = {}
    for b in bids:
        key = (b.state or "").strip().upper()
        if not key or len(key) != 2:
            continue
        if key not in state_stats:
            state_stats[key] = {"count": 0, "total_value": 0.0}
        state_stats[key]["count"] += 1
        state_stats[key]["total_value"] += float(b.estimated_value or 0)

    result_data = {
        "states": [
            {"state": k, "count": v["count"], "total_value": round(v["total_value"], 2)}
            for k, v in sorted(state_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ]
    }
    cache_set(ck, result_data, ttl=180)
    return result_data


def _apply_filters(stmt, sphere, state, city, branch, status, modality,
                   min_value, max_value, days_before_closing, q,
                   only_open_for_proposals: bool = False,
                   object_type: Optional[ObjectType] = None,
                   dispute_mode: Optional[str] = None):
    if sphere:
        stmt = stmt.where(PublicBid.sphere == sphere)
    if state:
        stmt = stmt.where(PublicBid.state.ilike(state))
    if city:
        stmt = stmt.where(PublicBid.city.ilike(f"%{city}%"))
    if branch:
        stmt = stmt.where(
            or_(
                PublicBid.branch_name.ilike(f"%{branch}%"),
                PublicBid.branch_code.ilike(f"%{branch}%"),
            )
        )
    if status:
        stmt = stmt.where(PublicBid.status == status)
    if modality:
        stmt = stmt.where(PublicBid.modality == modality)
    if min_value is not None:
        stmt = stmt.where(PublicBid.estimated_value >= min_value)
    if max_value is not None:
        stmt = stmt.where(PublicBid.estimated_value <= max_value)
    if days_before_closing is not None:
        deadline = date.today() + timedelta(days=days_before_closing)
        stmt = stmt.where(
            PublicBid.closing_date != None,  # noqa: E711
            PublicBid.closing_date <= deadline,
            PublicBid.closing_date >= date.today(),
        )
    if only_open_for_proposals:
        # Apenas licitações em que ainda é possível enviar proposta:
        # - status = aberta
        # - closing_date ainda no futuro OU sem data definida (dispensa/inexig.)
        stmt = stmt.where(
            PublicBid.status == BidStatus.aberta,
            or_(
                PublicBid.closing_date == None,  # noqa: E711
                PublicBid.closing_date >= date.today(),
            ),
        )
    if object_type:
        stmt = stmt.where(PublicBid.object_type == object_type)
    if dispute_mode:
        stmt = stmt.where(PublicBid.dispute_mode.ilike(dispute_mode.strip()))
    if q:
        term = f"%{_fold_py(q)}%"
        stmt = stmt.where(
            or_(
                _fold_col(PublicBid.title).like(term),
                _fold_col(PublicBid.description).like(term),
                _fold_col(PublicBid.organ_name).like(term),
            )
        )
    return stmt


@router.get("")
async def list_bids(
    sphere: Optional[BidSphere] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    branch: Optional[str] = None,
    status: Optional[BidStatus] = None,
    modality: Optional[BidModality] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    days_before_closing: Optional[int] = None,
    only_open_for_proposals: bool = Query(False, description="Só licitações com prazo ainda aberto"),
    object_type: Optional[ObjectType] = Query(None, description="Tipo do objeto: bem, servico, obra, consultoria, misto"),
    dispute_mode: Optional[str] = Query(None, description="Modo de disputa: Aberto, Fechado, Aberto-Fechado, Fechado-Aberto, Dispensa Com Disputa"),
    q: Optional[str] = None,
    sort_by: str = Query("closing_date", regex="^(closing_date|estimated_value|publication_date|opening_date|title|state|status)$"),
    sort_dir: str = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    stmt = select(PublicBid)
    stmt = _apply_filters(stmt, sphere, state, city, branch, status, modality,
                          min_value, max_value, days_before_closing, q,
                          only_open_for_proposals, object_type, dispute_mode)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    sort_col = getattr(PublicBid, sort_by, PublicBid.closing_date)
    order = sort_col.desc().nullslast() if sort_dir == "desc" else sort_col.asc().nullslast()
    stmt = stmt.order_by(order).offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    bids = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "data": [_bid_summary(b) for b in bids],
    }


@router.get("/search")
async def search_bids(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    term = f"%{_fold_py(q)}%"
    stmt = select(PublicBid).where(
        or_(
            _fold_col(PublicBid.title).like(term),
            _fold_col(PublicBid.description).like(term),
            _fold_col(PublicBid.organ_name).like(term),
            _fold_col(PublicBid.category_name).like(term),
        )
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    bids = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "data": [_bid_summary(b) for b in bids],
    }


@router.get("/stats")
async def bid_stats(
    sphere: Optional[BidSphere] = None,
    state: Optional[str] = None,
    status: Optional[BidStatus] = Query(BidStatus.aberta),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    stmt = select(PublicBid)
    stmt = _apply_filters(stmt, sphere, state, None, None, status, None, None, None, None, None)

    result = await session.execute(stmt)
    bids = result.scalars().all()

    total_value = sum((b.estimated_value or 0) for b in bids)
    count = len(bids)

    # Top ramos
    branch_counts: dict = {}
    for b in bids:
        key = b.branch_name or "Outros"
        branch_counts[key] = branch_counts.get(key, {"count": 0, "value": 0})
        branch_counts[key]["count"] += 1
        branch_counts[key]["value"] += float(b.estimated_value or 0)

    top_branches = sorted(branch_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:5]

    # Distribuição por esfera
    sphere_dist = {}
    for b in bids:
        key = b.sphere.value if b.sphere else "outros"
        sphere_dist[key] = sphere_dist.get(key, 0) + 1

    # Próximas (7 dias)
    next_7d = date.today() + timedelta(days=7)
    coming = [b for b in bids if b.closing_date and b.closing_date <= next_7d]

    return {
        "total_bids": count,
        "total_estimated_value": float(total_value),
        "average_value": float(total_value / count) if count else 0,
        "total_coming_7d": len(coming),
        "spheres_distribution": sphere_dist,
        "branches_top_5": [
            {"branch": k, "count": v["count"], "value": v["value"]}
            for k, v in top_branches
        ],
    }


# ─── Busca especializada em TI & Dados (foco Drive Data) ─────────────────────
import re as _re
from app.services.ti_classifier import counts as _ti_counts


def _it_counts(b: PublicBid) -> tuple[int, int]:
    # relevância pré-calculada quando disponível; senão calcula na hora
    return _ti_counts(b.title, b.description, b.category_name, b.branch_name)


def _kw_hits(bid_text_folded: str, kw_list: list) -> list:
    """Palavras da lista que aparecem no texto (match por palavra inteira)."""
    hits = []
    for k in kw_list:
        fk = _fold_py(k)
        if fk and _re.search(r"(?<!\w)" + _re.escape(fk) + r"(?!\w)", bid_text_folded):
            hits.append(k)
    return hits


@router.get("/ti")
async def list_ti_bids(
    state: Optional[str] = None,
    status: Optional[BidStatus] = Query(BidStatus.aberta),
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    only_open_for_proposals: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Busca acurada de licitações de TI & Dados.

    Ranqueia por relevância: só entram licitações com ao menos 1 sinal forte de TI
    (software, sistema, dados, BI, cloud, ERP, etc.). A ordenação prioriza maior
    relevância, depois prazo mais próximo e maior valor.
    """
    ck = f"ti:{state}:{status}:{min_value}:{max_value}:{only_open_for_proposals}:{page}:{limit}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    result = None
    # Caminho rápido: consulta indexada usando a relevância pré-calculada.
    try:
        stmt = select(PublicBid).where(PublicBid.is_ti == True)  # noqa: E712
        stmt = _apply_filters(stmt, None, state, None, None, status, None,
                              min_value, max_value, None, None,
                              only_open_for_proposals, None)
        total = (await session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        if total > 0:  # se 0, pode ser que ainda não fez backfill -> usa fallback
            stmt = stmt.order_by(
                PublicBid.ti_score.desc().nullslast(),
                PublicBid.closing_date.asc().nullslast(),
            ).offset((page - 1) * limit).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            result = {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit,
                "data": [{**_bid_summary(b), "relevance": b.ti_score} for b in rows],
            }
    except Exception:
        result = None  # coluna ausente/não pronta -> cai no cálculo em memória

    # Fallback: pontua em Python (usado enquanto is_ti não estiver populado)
    if result is None:
        base = select(PublicBid)
        base = _apply_filters(base, None, state, None, None, status, None,
                              min_value, max_value, None, None,
                              only_open_for_proposals, None)
        rows = (await session.execute(base.limit(3000))).scalars().all()
        scored = []
        for b in rows:
            strong, weak = _it_counts(b)
            if strong >= 1:
                scored.append((strong * 3 + weak, b))
        scored.sort(key=lambda x: (-x[0], x[1].closing_date or date.max, -float(x[1].estimated_value or 0)))
        total = len(scored)
        page_items = scored[(page - 1) * limit:(page - 1) * limit + limit]
        result = {
            "total": total, "page": page, "limit": limit,
            "pages": (total + limit - 1) // limit,
            "data": [{**_bid_summary(b), "relevance": score} for score, b in page_items],
        }

    cache_set(ck, result, ttl=150)
    return result


@router.get("/for-you")
async def bids_for_you(
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Feed 'Pra você': melhores oportunidades ABERTAS pro perfil da empresa,
    ordenadas por aderência (palavras-chave) e depois por prazo mais próximo.
    Sem perfil, cai no ranking de TI & Dados.
    """
    ck = f"foryou:{user.tenant_id}:{limit}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    profiles = (await session.execute(
        select(ProcurementProfile).where(
            ProcurementProfile.tenant_id == user.tenant_id,
            ProcurementProfile.active == True,  # noqa: E712
        )
    )).scalars().all()

    kw_all, excl_all = [], []
    for p in profiles:
        kw_all += _split_csv(p.keywords) + _split_csv(p.preferred_branches)
        excl_all += _split_csv(p.exclude_keywords)

    # pool de licitações abertas (com prazo válido ou sem prazo)
    stmt = select(PublicBid).where(
        PublicBid.status == BidStatus.aberta,
        or_(PublicBid.closing_date == None, PublicBid.closing_date >= date.today()),  # noqa: E711
    ).limit(4000)
    rows = (await session.execute(stmt)).scalars().all()

    today = date.today()
    scored = []
    for b in rows:
        text = _fold_py(f"{b.title or ''} {b.description or ''} {b.category_name or ''} {b.branch_name or ''}")
        if excl_all and _kw_hits(text, excl_all):
            continue
        if kw_all:
            hits = _kw_hits(text, kw_all)
            if not hits:
                continue
            rel = len(hits) * 20
            matched = hits[:3]
        else:
            s, w = _it_counts(b)
            if s < 1:
                continue
            rel = s * 30 + w * 10
            matched = ["TI & Dados"]
        days_left = (b.closing_date - today).days if b.closing_date else None
        scored.append((rel, days_left if days_left is not None else 9999, b, rel, days_left, matched))

    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:limit]

    result = {
        "total": len(scored),
        "has_profile": bool(profiles),
        "data": [
            {**_bid_summary(b), "relevance": rel, "days_left": dl, "matched": matched}
            for _, _, b, rel, dl, matched in top
        ],
    }
    cache_set(ck, result, ttl=120)
    return result


@router.get("/{bid_id}")
async def get_bid(bid_id: int, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    bid = await session.get(PublicBid, bid_id)
    if not bid:
        raise HTTPException(404, "Licitação não encontrada")
    return _bid_detail(bid)


@router.get("/{bid_id}/competitors")
async def bid_competitors(
    bid_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Inteligência de concorrência: quem venceu esta licitação e por quanto
    (dados públicos do PNCP após a homologação)."""
    bid = await session.get(PublicBid, bid_id)
    if not bid:
        raise HTTPException(404, "Licitação não encontrada")
    if bid.source != "pncp" or not bid.external_id:
        return {"has_result": False, "winners": [], "reason": "fonte_sem_resultado"}

    ck = f"comp:{bid.external_id}"
    hit = cache_get(ck)
    if hit is not None:
        return hit

    from app.services.competitors import get_competitors
    result = await get_competitors(bid.external_id)
    # cacheia por mais tempo: resultado homologado não muda
    cache_set(ck, result, ttl=1800 if result.get("has_result") else 300)
    return result


@router.get("/{bid_id}/items")
async def bid_items(
    bid_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Itens da licitação (o que está sendo comprado, item a item). Dados do PNCP."""
    bid = await session.get(PublicBid, bid_id)
    if not bid:
        raise HTTPException(404, "Licitação não encontrada")
    if bid.source != "pncp" or not bid.external_id:
        return {"has_items": False, "items": [], "reason": "fonte_sem_itens"}
    ck = f"items:{bid.external_id}"
    hit = cache_get(ck)
    if hit is not None:
        return hit
    from app.services.bid_items import get_items
    result = await get_items(bid.external_id)
    cache_set(ck, result, ttl=1800 if result.get("has_items") else 300)
    return result


@router.get("/{bid_id}/files")
async def bid_files(
    bid_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Arquivos/documentos do edital (PDF, termo de referência...). Dados do PNCP."""
    bid = await session.get(PublicBid, bid_id)
    if not bid:
        raise HTTPException(404, "Licitação não encontrada")
    if bid.source != "pncp" or not bid.external_id:
        return {"has_files": False, "files": [], "reason": "fonte_sem_arquivos"}
    ck = f"files:{bid.external_id}"
    hit = cache_get(ck)
    if hit is not None:
        return hit
    from app.services.bid_items import get_files
    result = await get_files(bid.external_id)
    cache_set(ck, result, ttl=1800 if result.get("has_files") else 300)
    return result


def _split_csv(s):
    return [p.strip() for p in (s or "").split(",") if p.strip()]


@router.get("/{bid_id}/eligibility")
async def bid_eligibility(
    bid_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Candidatura Assistida — Fase A: analisa a aderência da licitação ao perfil
    da empresa e devolve um veredito (elegivel / revisar / fora) com checagens.
    """
    bid = await session.get(PublicBid, bid_id)
    if not bid:
        raise HTTPException(404, "Licitação não encontrada")

    tenant = await session.get(Tenant, user.tenant_id)
    profiles = (await session.execute(
        select(ProcurementProfile).where(
            ProcurementProfile.tenant_id == user.tenant_id,
            ProcurementProfile.active == True,  # noqa: E712
        )
    )).scalars().all()

    bid_text = _fold_py(f"{bid.title or ''} {bid.description or ''} {bid.category_name or ''} {bid.branch_name or ''}")
    bid_state = (bid.state or "").upper()
    bid_value = float(bid.estimated_value or 0)
    bid_sphere = bid.sphere.value if bid.sphere else None

    def _kw_hit(k):
        fk = _fold_py(k)
        if not fk:
            return False
        # casa por palavra inteira (evita "ti" achar "participacao")
        return _re.search(r"(?<!\w)" + _re.escape(fk) + r"(?!\w)", bid_text) is not None

    def evaluate(kw_list, states, spheres, vmin, vmax):
        checks = []
        # 1) palavras-chave (match por palavra inteira)
        hits = [k for k in kw_list if _kw_hit(k)]
        if kw_list:
            if hits:
                checks.append({"key": "keywords", "status": "ok",
                               "label": "Palavras-chave do perfil",
                               "detail": "bateu: " + ", ".join(hits[:4])})
            else:
                checks.append({"key": "keywords", "status": "fail",
                               "label": "Palavras-chave do perfil",
                               "detail": "nenhuma palavra do perfil no objeto"})
        # 2) estado
        if states:
            if bid_state in [s.upper() for s in states]:
                checks.append({"key": "state", "status": "ok", "label": "Estado de atuação",
                               "detail": f"{bid_state} está nos seus estados"})
            else:
                checks.append({"key": "state", "status": "warn", "label": "Estado de atuação",
                               "detail": f"{bid_state or '—'} fora dos seus estados"})
        # 3) faixa de valor
        if vmin is not None or vmax is not None:
            below = vmin is not None and bid_value and bid_value < float(vmin)
            above = vmax is not None and bid_value and bid_value > float(vmax)
            if not (below or above):
                checks.append({"key": "value", "status": "ok", "label": "Faixa de valor",
                               "detail": "valor dentro da sua faixa"})
            else:
                checks.append({"key": "value", "status": "warn", "label": "Faixa de valor",
                               "detail": "valor fora da faixa do perfil"})
        # 4) esfera
        if spheres and bid_sphere:
            if bid_sphere in [s.strip() for s in spheres]:
                checks.append({"key": "sphere", "status": "ok", "label": "Esfera",
                               "detail": bid_sphere})
            else:
                checks.append({"key": "sphere", "status": "warn", "label": "Esfera",
                               "detail": f"{bid_sphere} fora das preferidas"})
        return checks, len(hits)

    best = None
    for p in profiles:
        kw = _split_csv(p.keywords) + _split_csv(p.preferred_branches)
        checks, hitn = evaluate(
            kw, _split_csv(p.preferred_states), _split_csv(p.preferred_spheres),
            p.min_estimated_value, p.max_estimated_value,
        )
        # pontuação: keyword hits pesam mais; cada warn tira ponto
        score = hitn * 30
        score -= sum(8 for c in checks if c["status"] == "warn")
        score -= sum(40 for c in checks if c["status"] == "fail")
        if best is None or score > best["score"]:
            best = {"profile": p.name, "score": score, "checks": checks, "hits": hitn}

    # Sem perfis: cai pra aderência de TI (foco Drive Data)
    if best is None:
        s, w = _it_counts(bid)
        if s >= 1:
            return {
                "bid_id": bid_id, "verdict": "revisar", "score": 50, "matched_profile": None,
                "checks": [{"key": "ti", "status": "ok", "label": "Aderência a TI & Dados",
                            "detail": "forte sinal de TI no objeto"}],
                "hint": "Crie um perfil de monitoramento para uma análise sob medida.",
            }
        return {
            "bid_id": bid_id, "verdict": "revisar", "score": 0, "matched_profile": None,
            "checks": [{"key": "profile", "status": "warn", "label": "Sem perfil configurado",
                        "detail": "crie um perfil para o Sonar avaliar a aderência"}],
            "hint": "Crie um perfil em Meus Perfis para ativar a análise de aderência.",
        }

    has_fail = any(c["status"] == "fail" for c in best["checks"])
    has_warn = any(c["status"] == "warn" for c in best["checks"])
    if best["hits"] >= 1 and not has_warn:
        verdict = "elegivel"
    elif best["hits"] >= 1:
        verdict = "revisar"
    else:
        verdict = "fora" if has_fail else "revisar"

    return {
        "bid_id": bid_id,
        "verdict": verdict,
        "score": max(0, min(100, best["score"])),
        "matched_profile": best["profile"],
        "checks": best["checks"],
    }


def _bid_summary(b: PublicBid) -> dict:
    return {
        "id": b.id,
        "title": b.title,
        "sphere": b.sphere,
        "state": b.state,
        "city": b.city,
        "organ_name": b.organ_name,
        "status": b.status,
        "modality": b.modality,
        "dispute_mode": b.dispute_mode,
        "object_type": b.object_type,
        "branch_name": b.branch_name,
        "estimated_value": float(b.estimated_value) if b.estimated_value else None,
        "publication_date": b.publication_date,
        "opening_date": b.opening_date,
        "closing_date": b.closing_date,
        "source": b.source,
    }


def _bid_detail(b: PublicBid) -> dict:
    return {
        **_bid_summary(b),
        "external_id": b.external_id,
        "description": b.description,
        "category_code": b.category_code,
        "category_name": b.category_name,
        "organ_cnpj": b.organ_cnpj,
        "city_code": b.city_code,
        "maximum_value": float(b.maximum_value) if b.maximum_value else None,
        "min_patrimony": float(b.min_patrimony) if b.min_patrimony else None,
        "min_revenue": float(b.min_revenue) if b.min_revenue else None,
        "years_of_operation": b.years_of_operation,
        "requires_sme": b.requires_sme,
        "requires_mei": b.requires_mei,
        "contact_name": b.contact_name,
        "contact_email": b.contact_email,
        "contact_phone": b.contact_phone,
        "edital_url": b.edital_url,
        "details_url": b.details_url,
        "platform_url": b.platform_url,
        "last_scraped": b.last_scraped,
        "updated_at": b.updated_at,
    }
