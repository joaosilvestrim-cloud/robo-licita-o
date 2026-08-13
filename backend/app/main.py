import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.database import init_db
from app.api import auth, bids, profiles, alerts, tracking, dashboard, sync, cnpj, chat, companies, interactions, users, sources, municipal_portals
from app.cron.jobs import (
    run_pncp_sync, run_comprasnet_sync, run_bec_sp_sync,
    run_licitacoes_e_sync, run_querido_diario_sync,
    run_keyword_sync, run_alert_processing, run_cleanup,
    run_portal_compras_publicas_sync, run_e_lic_sc_sync,
    run_celic_rs_sync, run_comprasnet_ba_sync, run_compra_aberta_sync,
    run_bnc_sync,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Procurement database...")
    await init_db()
    logger.info("Database initialized.")

    # Agendador interno é opcional. Em cloud (Render + cron externo) fica desligado
    # via ENABLE_SCHEDULER=false, e os syncs são disparados por HTTP pelo cron.
    if settings.enable_scheduler:
        # days_back=7 garante que dias sem sync (restart, falha) sejam recuperados
        scheduler.add_job(run_pncp_sync,          "interval", hours=6,  id="pncp_sync")
        scheduler.add_job(run_comprasnet_sync,     "interval", hours=8,  id="comprasnet_sync")
        scheduler.add_job(run_bec_sp_sync,         "interval", hours=8,  id="bec_sp_sync")
        scheduler.add_job(run_licitacoes_e_sync,             "interval", hours=8,  id="licitacoes_e_sync")
        scheduler.add_job(run_querido_diario_sync,           "interval", hours=12, id="querido_diario_sync")
        scheduler.add_job(run_portal_compras_publicas_sync,  "interval", hours=8,  id="portal_compras_publicas_sync")
        scheduler.add_job(run_e_lic_sc_sync,                 "interval", hours=8,  id="e_lic_sc_sync")
        scheduler.add_job(run_celic_rs_sync,                 "interval", hours=8,  id="celic_rs_sync")
        scheduler.add_job(run_comprasnet_ba_sync,            "interval", hours=8,  id="comprasnet_ba_sync")
        scheduler.add_job(run_compra_aberta_sync,            "interval", hours=8,  id="compra_aberta_sync")
        scheduler.add_job(run_bnc_sync,                      "interval", hours=8,  id="bnc_sync")
        scheduler.add_job(run_keyword_sync,         "interval", hours=12, id="keyword_sync")
        scheduler.add_job(run_alert_processing,     "interval", hours=1,  id="alert_processing")
        scheduler.add_job(run_cleanup,              "cron", hour=1, minute=0, id="close_expired_bids")
        scheduler.start()
        logger.info("APScheduler started (%d jobs).", len(scheduler.get_jobs()))
    else:
        logger.info("APScheduler desligado (ENABLE_SCHEDULER=false). Syncs via cron externo.")
    yield
    if settings.enable_scheduler:
        scheduler.shutdown()
        logger.info("APScheduler stopped.")


app = FastAPI(
    title="Sonar · API",
    version="1.0.0",
    description="Sonar — monitoramento de licitações públicas. Por Drive Data.",
    lifespan=lifespan,
)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bids.router)
app.include_router(profiles.router)
app.include_router(alerts.router)
app.include_router(tracking.router)
app.include_router(dashboard.router)
app.include_router(sync.router)
app.include_router(cnpj.router)
app.include_router(chat.router)
app.include_router(companies.router)
app.include_router(interactions.router)
app.include_router(users.router)
app.include_router(sources.router)
app.include_router(municipal_portals.router)


@app.get("/health")
async def health():
    return {"status": "ok", "module": "procurement"}
