from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
from app.database import get_session
from app.db.models import ProcurementProfile, User
from app.auth import get_current_user
from app.services.alerts import _compute_score, SCORE_THRESHOLD
from app.db.models import PublicBid, BidStatus

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileBody(BaseModel):
    name: str
    preferred_spheres: Optional[str] = None
    preferred_states: Optional[str] = None
    preferred_cities: Optional[str] = None
    preferred_branches: Optional[str] = None
    preferred_categories: Optional[str] = None
    min_estimated_value: Optional[float] = None
    max_estimated_value: Optional[float] = None
    exclude_modalities: Optional[str] = None
    require_sme_reservation: bool = False
    only_with_deadline: bool = False
    alert_days_before: int = 7
    keywords: Optional[str] = None
    exclude_keywords: Optional[str] = None


@router.get("")
async def list_profiles(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(ProcurementProfile).where(
            ProcurementProfile.tenant_id == user.tenant_id,
            ProcurementProfile.user_id == user.id,
            ProcurementProfile.active == True,  # noqa: E712
        )
    )
    return result.scalars().all()


@router.post("", status_code=201)
async def create_profile(
    body: ProfileBody,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    profile = ProcurementProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        **body.model_dump(),
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/{profile_id}")
async def get_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    profile = await session.get(ProcurementProfile, profile_id)
    if not profile or profile.tenant_id != user.tenant_id:
        raise HTTPException(404, "Perfil não encontrado")
    return profile


@router.patch("/{profile_id}")
async def update_profile(
    profile_id: int,
    body: ProfileBody,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    profile = await session.get(ProcurementProfile, profile_id)
    if not profile or profile.tenant_id != user.tenant_id:
        raise HTTPException(404, "Perfil não encontrado")

    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    profile.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    profile = await session.get(ProcurementProfile, profile_id)
    if not profile or profile.tenant_id != user.tenant_id:
        raise HTTPException(404, "Perfil não encontrado")
    profile.active = False
    profile.updated_at = datetime.utcnow()
    await session.commit()


@router.post("/{profile_id}/test")
async def test_profile(
    profile_id: int,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Simula quais licitações abertas o perfil capturaria."""
    profile = await session.get(ProcurementProfile, profile_id)
    if not profile or profile.tenant_id != user.tenant_id:
        raise HTTPException(404, "Perfil não encontrado")

    result = await session.execute(
        select(PublicBid).where(PublicBid.status == BidStatus.aberta).limit(200)
    )
    bids = result.scalars().all()

    matches = []
    for bid in bids:
        score, reasons = _compute_score(bid, profile)
        if score >= SCORE_THRESHOLD:
            matches.append({
                "bid_id": bid.id,
                "title": bid.title,
                "state": bid.state,
                "city": bid.city,
                "estimated_value": float(bid.estimated_value) if bid.estimated_value else None,
                "closing_date": bid.closing_date,
                "score": float(score),
                "reasons": reasons,
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return {"total_matches": len(matches), "sample": matches[:limit]}
