from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
from app.database import get_session
from app.db.models import MunicipalPortal, PortalType, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/portals", tags=["portals"])


class PortalCreate(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    ibge_code: Optional[str] = None
    portal_name: Optional[str] = None
    portal_url: str
    system_name: Optional[str] = None
    portal_type: PortalType = PortalType.scraping_html
    api_endpoint: Optional[str] = None
    scraper_key: Optional[str] = None
    active: bool = True
    verified: bool = False
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None


class PortalUpdate(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    ibge_code: Optional[str] = None
    portal_name: Optional[str] = None
    portal_url: Optional[str] = None
    system_name: Optional[str] = None
    portal_type: Optional[PortalType] = None
    api_endpoint: Optional[str] = None
    scraper_key: Optional[str] = None
    active: Optional[bool] = None
    verified: Optional[bool] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None


def _portal_dict(p: MunicipalPortal) -> dict:
    return {
        "id": p.id,
        "ibge_code": p.ibge_code,
        "city": p.city,
        "state": p.state,
        "portal_name": p.portal_name,
        "portal_url": p.portal_url,
        "system_name": p.system_name,
        "portal_type": p.portal_type,
        "api_endpoint": p.api_endpoint,
        "scraper_key": p.scraper_key,
        "active": p.active,
        "verified": p.verified,
        "contact_email": p.contact_email,
        "contact_phone": p.contact_phone,
        "notes": p.notes,
        "last_sync_at": p.last_sync_at,
        "last_sync_status": p.last_sync_status,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("")
async def list_portals(
    state: Optional[str] = Query(None, description="Filtrar por UF (SP, MG...)"),
    city: Optional[str] = Query(None, description="Filtrar por cidade (parcial)"),
    active: Optional[bool] = Query(None),
    verified: Optional[bool] = Query(None),
    portal_type: Optional[PortalType] = Query(None),
    scraper_key: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Busca por nome ou URL"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    stmt = select(MunicipalPortal)
    if state:
        stmt = stmt.where(MunicipalPortal.state == state.upper())
    if city:
        stmt = stmt.where(MunicipalPortal.city.ilike(f"%{city}%"))
    if active is not None:
        stmt = stmt.where(MunicipalPortal.active == active)
    if verified is not None:
        stmt = stmt.where(MunicipalPortal.verified == verified)
    if portal_type:
        stmt = stmt.where(MunicipalPortal.portal_type == portal_type)
    if scraper_key:
        stmt = stmt.where(MunicipalPortal.scraper_key == scraper_key)
    if q:
        from sqlmodel import or_
        stmt = stmt.where(or_(
            MunicipalPortal.portal_name.ilike(f"%{q}%"),
            MunicipalPortal.portal_url.ilike(f"%{q}%"),
            MunicipalPortal.system_name.ilike(f"%{q}%"),
            MunicipalPortal.city.ilike(f"%{q}%"),
        ))

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(MunicipalPortal.state, MunicipalPortal.city)
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    portals = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "data": [_portal_dict(p) for p in portals],
    }


@router.get("/stats")
async def portal_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    result = await session.execute(select(MunicipalPortal))
    portals = result.scalars().all()

    by_state: dict = {}
    by_type: dict = {}
    by_scraper: dict = {}

    for p in portals:
        state = p.state or "N/A"
        by_state[state] = by_state.get(state, 0) + 1
        pt = p.portal_type.value if p.portal_type else "N/A"
        by_type[pt] = by_type.get(pt, 0) + 1
        if p.scraper_key:
            by_scraper[p.scraper_key] = by_scraper.get(p.scraper_key, 0) + 1

    return {
        "total": len(portals),
        "active": sum(1 for p in portals if p.active),
        "verified": sum(1 for p in portals if p.verified),
        "with_api": sum(1 for p in portals if p.api_endpoint),
        "with_scraper": sum(1 for p in portals if p.scraper_key),
        "by_state": dict(sorted(by_state.items())),
        "by_type": by_type,
        "by_scraper": by_scraper,
    }


@router.get("/{portal_id}")
async def get_portal(
    portal_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    portal = await session.get(MunicipalPortal, portal_id)
    if not portal:
        raise HTTPException(404, "Portal não encontrado")
    return _portal_dict(portal)


@router.post("", status_code=201)
async def create_portal(
    body: PortalCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    portal = MunicipalPortal(**body.model_dump())
    session.add(portal)
    await session.commit()
    await session.refresh(portal)
    return _portal_dict(portal)


@router.patch("/{portal_id}")
async def update_portal(
    portal_id: int,
    body: PortalUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    portal = await session.get(MunicipalPortal, portal_id)
    if not portal:
        raise HTTPException(404, "Portal não encontrado")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(portal, field, value)
    portal.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(portal)
    return _portal_dict(portal)


@router.delete("/{portal_id}", status_code=204)
async def delete_portal(
    portal_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    portal = await session.get(MunicipalPortal, portal_id)
    if not portal:
        raise HTTPException(404, "Portal não encontrado")
    await session.delete(portal)
    await session.commit()
