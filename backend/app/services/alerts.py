"""Processador de alertas — matches licitações vs perfis de usuário."""
import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List
from sqlmodel import select, or_
from app.db.models import PublicBid, ProcurementProfile, ProcurementAlert, AlertStatus, BidStatus
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 0.5


def _split(val: str | None) -> List[str]:
    if not val or val.strip() == "*":
        return []  # vazio ou * = todos (sem filtro)
    return [v.strip().lower() for v in val.split(",") if v.strip() and v.strip() != "*"]


def _compute_score(bid: PublicBid, profile: ProcurementProfile) -> tuple[float, List[str]]:
    """Calcula score de relevância (0-1) e razões do match."""
    score = 0.0
    reasons = []
    weight_total = 0.0

    spheres = _split(profile.preferred_spheres)
    if spheres:
        weight_total += 20
        if bid.sphere and bid.sphere.value in spheres:
            score += 20
            reasons.append(f"Esfera: {bid.sphere.value}")

    states = _split(profile.preferred_states)
    if states:
        weight_total += 25
        if bid.state and bid.state.lower() in states:
            score += 25
            reasons.append(f"Estado: {bid.state}")

    cities = _split(profile.preferred_cities)
    if cities:
        weight_total += 15
        if bid.city and bid.city.lower() in cities:
            score += 15
            reasons.append(f"Cidade: {bid.city}")

    branches = _split(profile.preferred_branches)
    if branches:
        weight_total += 25
        bid_branch = (bid.branch_name or "").lower()
        if any(b in bid_branch for b in branches):
            score += 25
            reasons.append(f"Ramo: {bid.branch_name}")

    keywords = _split(profile.keywords)
    if keywords:
        weight_total += 15
        text = f"{bid.title} {bid.description or ''}".lower()
        hits = [k for k in keywords if k in text]
        if hits:
            score += 15
            reasons.append(f"Keywords: {', '.join(hits)}")

    exclude_kw = _split(profile.exclude_keywords)
    if exclude_kw:
        text = f"{bid.title} {bid.description or ''}".lower()
        if any(k in text for k in exclude_kw):
            return 0.0, []

    exclude_mod = _split(profile.exclude_modalities)
    if bid.modality and bid.modality.value in exclude_mod:
        return 0.0, []

    if profile.min_estimated_value and bid.estimated_value:
        if bid.estimated_value < profile.min_estimated_value:
            return 0.0, []
    if profile.max_estimated_value and bid.estimated_value:
        if bid.estimated_value > profile.max_estimated_value:
            return 0.0, []

    if profile.require_sme_reservation and not bid.requires_sme:
        score *= 0.7

    # Se perfil exige prazo definido e a licitação não tem data de encerramento, descarta
    if getattr(profile, "only_with_deadline", False) and bid.closing_date is None:
        return 0.0, []

    if weight_total == 0:
        return 0.0, []

    final = round(score / weight_total, 2)
    return final, reasons


async def process_alerts():
    """Gera alertas para licitações novas vs perfis ativos.

    Só considera licitações em que ainda há prazo (closing_date >= hoje ou
    sem prazo definido — dispensa/inexigibilidade). Licitações com prazo
    vencido nunca geram alertas novos.
    """
    cutoff = datetime.utcnow() - timedelta(hours=25)
    today = date.today()
    generated = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PublicBid).where(
                PublicBid.status == BidStatus.aberta,
                PublicBid.created_at >= cutoff,
                or_(
                    PublicBid.closing_date == None,  # noqa: E711
                    PublicBid.closing_date >= today,
                ),
            )
        )
        new_bids = result.scalars().all()

        if not new_bids:
            logger.info("process_alerts: nenhuma licitação nova para processar")
            return

        profiles_result = await session.execute(
            select(ProcurementProfile).where(ProcurementProfile.active == True)  # noqa: E712
        )
        profiles = profiles_result.scalars().all()

        for profile in profiles:
            for bid in new_bids:
                # Evita duplicatas
                existing = await session.execute(
                    select(ProcurementAlert).where(
                        ProcurementAlert.profile_id == profile.id,
                        ProcurementAlert.bid_id == bid.id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                score, reasons = _compute_score(bid, profile)
                if score < SCORE_THRESHOLD:
                    continue

                alert = ProcurementAlert(
                    tenant_id=profile.tenant_id,
                    profile_id=profile.id,
                    bid_id=bid.id,
                    match_score=Decimal(str(score)),
                    match_reasons=json.dumps(reasons, ensure_ascii=False),
                    status=AlertStatus.novo,
                )
                session.add(alert)
                generated += 1

        await session.commit()

    logger.info(f"process_alerts: {generated} alertas gerados")
    return generated
