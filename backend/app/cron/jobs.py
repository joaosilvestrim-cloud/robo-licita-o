import logging
from app.services.pncp import sync_pncp
from app.services.pncp_search import sync_all_profile_keywords
from app.services.alerts import process_alerts
from app.services.cleanup import close_expired_bids, delete_expired_alerts
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

logger = logging.getLogger(__name__)


async def run_pncp_sync():
    logger.info("Cron: iniciando sync PNCP")
    await sync_pncp(days_back=7)


async def run_comprasnet_sync():
    logger.info("Cron: iniciando sync ComprasNet")
    await sync_comprasnet(days_back=7)


async def run_bec_sp_sync():
    logger.info("Cron: pulando BEC/SP — endpoint descontinuado")
    await sync_bec_sp()


async def run_licitacoes_e_sync():
    logger.info("Cron: iniciando sync Licitações-e")
    await sync_licitacoes_e(days_back=7)


async def run_licitacoes_e2_bb_sync():
    logger.info("Cron: iniciando sync Licitações-e2 BB")
    await sync_licitacoes_e2_bb(days_back=7)


async def run_querido_diario_sync():
    logger.info("Cron: iniciando sync Querido Diário")
    await sync_querido_diario(days_back=1)


async def run_portal_compras_publicas_sync():
    logger.info("Cron: iniciando sync Portal Compras Públicas")
    await sync_portal_compras_publicas(days_back=7)


async def run_e_lic_sc_sync():
    logger.info("Cron: iniciando sync e-lic SC")
    await sync_e_lic_sc(days_back=7)


async def run_celic_rs_sync():
    logger.info("Cron: iniciando sync CELIC RS")
    await sync_celic_rs(days_back=7)


async def run_comprasnet_ba_sync():
    logger.info("Cron: iniciando sync ComprasNet BA")
    await sync_comprasnet_ba(days_back=7)


async def run_compra_aberta_sync():
    logger.info("Cron: iniciando sync Compra Aberta")
    await sync_compra_aberta(days_back=7)


async def run_bnc_sync():
    logger.info("Cron: iniciando sync BNC")
    await sync_bnc(days_back=7)


async def run_all_sources_sync():
    """Roda todas as fontes em sequência."""
    await sync_pncp(days_back=1)
    await sync_comprasnet(days_back=1)
    await sync_bec_sp(days_back=1)
    await sync_licitacoes_e(days_back=1)
    await sync_licitacoes_e2_bb(days_back=1)
    await sync_querido_diario(days_back=1)
    await sync_portal_compras_publicas(days_back=1)
    await sync_e_lic_sc(days_back=1)
    await sync_celic_rs(days_back=1)
    await sync_comprasnet_ba(days_back=1)
    await sync_compra_aberta(days_back=1)
    await sync_bnc(days_back=1)


async def run_keyword_sync():
    logger.info("Cron: iniciando sync PNCP por keywords de perfis")
    await sync_all_profile_keywords()


async def run_cleanup():
    logger.info("Cron: encerrando licitações vencidas")
    await close_expired_bids()
    logger.info("Cron: removendo alertas expirados")
    await delete_expired_alerts()


async def run_alert_processing():
    logger.info("Cron: processando alertas")
    await process_alerts()


async def run_all_jobs():
    await run_all_sources_sync()
    await run_keyword_sync()
    await run_cleanup()
    await run_alert_processing()
