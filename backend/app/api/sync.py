from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import ScrapeLog, User
from app.auth import get_current_user, require_user_or_cron
from app.services.pncp import sync_pncp
from app.services.pncp_search import sync_keyword, sync_all_profile_keywords
from app.services.alerts import process_alerts
from app.services.comprasnet import sync_comprasnet
from app.services.bec_sp import sync_bec_sp
from app.services.licitacoes_e import sync_licitacoes_e
from app.services.licitacoes_e2_bb import sync_licitacoes_e2_bb
from app.services.querido_diario import sync_querido_diario
from app.services.portal_compras_publicas import sync_portal_compras_publicas
from app.services.e_lic_sc import sync_e_lic_sc
from app.services.celic_rs import sync_celic_rs
from app.services.comprasnet_ba import sync_comprasnet_ba
from app.services.compra_aberta import sync_compra_aberta
from app.services.bnc import sync_bnc
from app.cron.jobs import run_all_sources_sync

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("")
async def trigger_full_sync(
    background_tasks: BackgroundTasks,
    days_back: int = Query(3, ge=1, le=180),
    _: User = Depends(require_user_or_cron),
):
    """Sincroniza licitações por data (PNCP) + keywords dos perfis + processa alertas."""
    async def _run():
        await sync_pncp(days_back=days_back)
        await sync_all_profile_keywords()
        await process_alerts()

    background_tasks.add_task(_run)
    return {"message": f"Sincronização completa iniciada (últimos {days_back} dias + keywords dos perfis)"}


class KeywordSearchBody(BaseModel):
    keyword: str
    max_pages: int = 4


@router.post("/keyword")
async def sync_by_keyword(
    body: KeywordSearchBody,
    background_tasks: BackgroundTasks,
    _: User = Depends(require_user_or_cron),
):
    """Busca licitações no PNCP por palavra-chave específica (full-text nos editais)."""
    async def _run():
        found, ins, upd = await sync_keyword(body.keyword, max_pages=body.max_pages)
        await process_alerts()
        return {"found": found, "inserted": ins, "updated": upd}

    background_tasks.add_task(_run)
    return {"message": f"Buscando '{body.keyword}' no PNCP em background (até {body.max_pages * 20} resultados)"}


@router.post("/keywords/profiles")
async def sync_profile_keywords(
    background_tasks: BackgroundTasks,
    _: User = Depends(require_user_or_cron),
):
    """Busca no PNCP por todas as keywords e ramos dos perfis ativos."""
    background_tasks.add_task(sync_all_profile_keywords)
    return {"message": "Sincronização por keywords dos perfis iniciada em background"}


@router.post("/all")
async def trigger_all_sources(
    background_tasks: BackgroundTasks,
    days_back: int = Query(1, ge=1, le=30),
    _: User = Depends(require_user_or_cron),
):
    """Dispara sync de todas as fontes em background."""
    async def _run():
        await sync_pncp(days_back=days_back)
        await sync_comprasnet(days_back=days_back)
        await sync_bec_sp(days_back=days_back)
        await sync_licitacoes_e(days_back=days_back)
        await sync_licitacoes_e2_bb(days_back=days_back)
        await sync_querido_diario(days_back=days_back)
        await sync_portal_compras_publicas(days_back=days_back)
        await sync_e_lic_sc(days_back=days_back)
        await sync_celic_rs(days_back=days_back)
        await sync_comprasnet_ba(days_back=days_back)
        await sync_compra_aberta(days_back=days_back)
        await sync_bnc(days_back=days_back)

    background_tasks.add_task(_run)
    return {"message": f"Sync de todas as fontes iniciado (últimos {days_back} dias)"}


@router.post("/{source}")
async def trigger_source_sync(
    source: str,
    background_tasks: BackgroundTasks,
    days_back: int = Query(3, ge=1, le=180),
    _: User = Depends(require_user_or_cron),
):
    SOURCE_MAP = {
        "pncp":        (sync_pncp,           {"days_back": days_back}),
        "comprasnet":  (sync_comprasnet,      {"days_back": days_back}),
        "bec_sp":      (sync_bec_sp,          {"days_back": days_back}),
        "licitacoes_e":(sync_licitacoes_e,      {"days_back": days_back}),
        "licitacoes_e2_bb":         (sync_licitacoes_e2_bb,          {"days_back": days_back}),
        "dou":                      (sync_querido_diario,            {"days_back": days_back}),
        "portal_compras_publicas":  (sync_portal_compras_publicas,   {"days_back": days_back}),
        "e_lic_sc":                 (sync_e_lic_sc,                  {"days_back": days_back}),
        "celic_rs":                 (sync_celic_rs,                  {"days_back": days_back}),
        "comprasnet_ba":            (sync_comprasnet_ba,             {"days_back": days_back}),
        "compra_aberta":            (sync_compra_aberta,             {"days_back": days_back}),
        "bnc":                      (sync_bnc,                       {"days_back": days_back}),
        "alerts":      (process_alerts,       {}),
        "keywords":    (sync_all_profile_keywords, {}),
    }
    if source not in SOURCE_MAP:
        return {"error": f"Fonte '{source}' não suportada. Disponíveis: {', '.join(SOURCE_MAP)}"}
    fn, kwargs = SOURCE_MAP[source]
    background_tasks.add_task(fn, **kwargs)
    return {"message": f"Sync de '{source}' iniciado"}


@router.get("/status")
async def sync_status(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_user_or_cron),
):
    result = await session.execute(
        select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(20)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "source": l.source,
            "status": l.status,
            "start_time": l.start_time,
            "end_time": l.end_time,
            "records_found": l.records_found,
            "records_inserted": l.records_inserted,
            "records_updated": l.records_updated,
            "error_message": l.error_message,
        }
        for l in logs
    ]
