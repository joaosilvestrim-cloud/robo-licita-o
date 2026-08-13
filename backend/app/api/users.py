from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from app.database import get_session
from app.db.models import User, UserRole
from app.auth import get_current_user, require_admin, require_full_or_admin, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _fmt(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "active": u.active,
        "created_at": u.created_at,
    }


@router.get("")
async def list_users(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_full_or_admin),
):
    """Lista todos os usuários da empresa (Full/Admin)."""
    result = await session.execute(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at)
    )
    return [_fmt(u) for u in result.scalars().all()]


class InviteBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.simple


@router.post("", status_code=201)
async def invite_user(
    body: InviteBody,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Convida novo usuário para a empresa (Admin)."""
    existing = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "E-mail já cadastrado")

    new_user = User(
        tenant_id=admin.tenant_id,
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return _fmt(new_user)


class UpdateRoleBody(BaseModel):
    role: Optional[UserRole] = None
    active: Optional[bool] = None
    name: Optional[str] = None
    password: Optional[str] = None  # admin redefine a senha do usuário


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateRoleBody,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Atualiza perfil/status/nome/senha de um usuário da empresa (Admin)."""
    target = await session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "Usuário não encontrado")
    if target.id == admin.id and body.role and body.role != UserRole.admin:
        raise HTTPException(400, "Admin não pode rebaixar a si mesmo")

    if body.role is not None:
        target.role = body.role
    if body.active is not None:
        target.active = body.active
    if body.name is not None:
        target.name = body.name
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(400, "A senha deve ter pelo menos 6 caracteres")
        target.hashed_password = hash_password(body.password)

    await session.commit()
    await session.refresh(target)
    return _fmt(target)


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Desativa usuário da empresa (Admin). Não apaga dados."""
    target = await session.get(User, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "Usuário não encontrado")
    if target.id == admin.id:
        raise HTTPException(400, "Admin não pode desativar a si mesmo")

    target.active = False
    await session.commit()
