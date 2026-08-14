"""Notificação proativa — digest de oportunidades de TI & Dados via Telegram."""
import logging
from datetime import date
import httpx
from sqlmodel import select, or_
from app.db.models import PublicBid, BidStatus
from app.config import settings

logger = logging.getLogger(__name__)


async def send_telegram(text: str) -> bool:
    """Envia mensagem ao chat configurado. Retorna False se não configurado."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if resp.status_code != 200:
                logger.warning(f"Telegram {resp.status_code}: {resp.text[:150]}")
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram erro: {e}")
        return False


async def build_ti_digest(session, limit: int = 8) -> str | None:
    """Monta o texto do digest com as melhores oportunidades de TI & Dados abertas."""
    from app.api.bids import _it_counts

    stmt = select(PublicBid).where(
        PublicBid.status == BidStatus.aberta,
        or_(PublicBid.closing_date == None, PublicBid.closing_date >= date.today()),  # noqa: E711
    ).limit(3000)
    rows = (await session.execute(stmt)).scalars().all()

    today = date.today()
    scored = []
    for b in rows:
        s, w = _it_counts(b)
        if s < 1:
            continue
        dl = (b.closing_date - today).days if b.closing_date else None
        scored.append((s * 3 + w, dl if dl is not None else 9999, b, dl))

    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:limit]

    front = (settings.frontend_url or "").rstrip("/")
    header = f"📡 <b>Sonar</b> · {len(scored)} oportunidades de TI &amp; Dados abertas hoje\n"
    lines = [header]
    for _, _, b, dl in top:
        if dl is None:
            prazo = "sem prazo"
        elif dl <= 2:
            prazo = f"⏰ vence em {dl}d"
        elif dl <= 7:
            prazo = f"vence em {dl}d"
        else:
            prazo = f"{dl}d restantes"
        val = ""
        if b.estimated_value:
            val = f" · R$ {float(b.estimated_value):,.0f}".replace(",", ".")
        link = f"\n  {front}/dashboard/bids/{b.id}" if front else ""
        title = (b.title or "")[:75]
        lines.append(f"• <b>{title}</b>\n  {b.state or '—'} · {prazo}{val}{link}")

    return "\n\n".join(lines)
