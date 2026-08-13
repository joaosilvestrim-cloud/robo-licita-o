from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.config import settings
from app.database import get_session
from app.db.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


async def get_current_user(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)) -> User:
    credentials_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc
    user = await session.get(User, int(user_id))
    if not user or not user.active:
        raise credentials_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requer perfil Admin da empresa")
    return user


def require_full_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role == UserRole.simple:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requer perfil Full ou Admin")
    return user


async def require_user_or_cron(
    x_cron_secret: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Libera o endpoint para o cron externo (header X-Cron-Secret) ou usuário JWT.

    Usado nos endpoints de sync, que são chamados tanto pela interface quanto
    pelo agendador externo (GitHub Actions / pg_cron).
    """
    # 1) chamada do cron
    if settings.cron_secret and x_cron_secret and x_cron_secret == settings.cron_secret:
        return None
    # 2) chamada autenticada de usuário
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id = payload.get("sub")
            if user_id is not None:
                user = await session.get(User, int(user_id))
                if user and user.active:
                    return user
        except JWTError:
            pass
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Requer JWT de usuário ou X-Cron-Secret válido",
    )


def verify_sso_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.sso_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
