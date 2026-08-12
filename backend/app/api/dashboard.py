from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlmodel import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import PublicBid, BidTracking, ProcurementAlert, BidStatus, AlertStatus, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    today = date.today()
    next_7d = today + timedelta(days=7)

    # ── Licitações ainda válidas para proposta ──
    # status = aberta E (closing_date >= hoje OU sem prazo definido)
    valid_stmt = select(PublicBid).where(
        PublicBid.status == BidStatus.aberta,
        or_(
            PublicBid.closing_date == None,  # noqa: E711
            PublicBid.closing_date >= today,
        ),
    )
    valid_bids = (await session.execute(valid_stmt)).scalars().all()

    total_open = len(valid_bids)
    total_value = sum((b.estimated_value or 0) for b in valid_bids)
    avg_value = float(total_value / total_open) if total_open else 0

    # Próximas 7 dias (que vencem logo)
    coming_7d = [b for b in valid_bids if b.closing_date and b.closing_date <= next_7d]

    # Sem prazo (Dispensa/Inexigibilidade — podem receber proposta até negociar)
    no_deadline = [b for b in valid_bids if b.closing_date is None]

    # Distribuição por esfera
    sphere_dist: dict = {}
    for b in valid_bids:
        key = b.sphere.value if b.sphere else "outros"
        sphere_dist[key] = sphere_dist.get(key, 0) + 1

    # Top ramos
    branch_map: dict = {}
    for b in valid_bids:
        key = b.branch_name or "Outros"
        if key not in branch_map:
            branch_map[key] = {"count": 0, "value": 0}
        branch_map[key]["count"] += 1
        branch_map[key]["value"] += float(b.estimated_value or 0)
    top_branches = sorted(branch_map.items(), key=lambda x: x[1]["count"], reverse=True)[:5]

    # Total de licitações no DB (inclui encerradas) — para contexto
    total_all = (await session.execute(
        select(func.count()).select_from(PublicBid)
    )).scalar_one()

    # Alertas não lidos
    novos_alerts = (await session.execute(
        select(func.count()).select_from(ProcurementAlert).where(
            ProcurementAlert.tenant_id == user.tenant_id,
            ProcurementAlert.status == AlertStatus.novo,
        )
    )).scalar_one()

    # Tracking stats
    tracking_result = await session.execute(
        select(BidTracking).where(BidTracking.tenant_id == user.tenant_id)
    )
    trackings = tracking_result.scalars().all()
    total_tracking = len(trackings)
    total_won = len([t for t in trackings if t.won])
    success_rate = round(total_won / total_tracking, 2) if total_tracking else 0

    return {
        "total_bids_open": total_open,           # só as que ainda aceitam proposta
        "total_bids_coming_7d": len(coming_7d),
        "total_bids_no_deadline": len(no_deadline),
        "total_bids_in_db": total_all,
        "total_estimated_value": float(total_value),
        "average_value": avg_value,
        "spheres_distribution": sphere_dist,
        "branches_top_5": [
            {"branch": k, "count": v["count"], "value": v["value"]}
            for k, v in top_branches
        ],
        "new_alerts": novos_alerts,
        "tracking": {
            "total": total_tracking,
            "won": total_won,
            "success_rate": success_rate,
        },
    }
