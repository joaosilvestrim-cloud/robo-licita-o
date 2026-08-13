from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import json, re, secrets, smtplib, ssl
from email.mime.text import MIMEText
from app.database import get_session
from app.db.models import User, Tenant, TenantType, TenantCompany
from app.auth import verify_password, hash_password, create_access_token, verify_sso_token, get_current_user
from app.config import settings
from app.api.cnpj import lookup_cnpj, format_cnpj

# Token temporário em memória: {token: (user_id, expires)}
_reset_tokens: dict[str, tuple[int, datetime]] = {}

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    tenant_name: str
    document: str
    document_type: TenantType
    name: str
    email: EmailStr
    password: str
    # Dados da Receita Federal (opcionais — preenchidos via consulta CNPJ)
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    cnae_code: Optional[str] = None
    cnae_description: Optional[str] = None
    natureza_juridica: Optional[str] = None
    situacao_cadastral: Optional[str] = None
    capital_social: Optional[float] = None
    data_abertura: Optional[str] = None
    porte: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    uf_address: Optional[str] = None
    cep: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    user_name: str
    user_role: str
    tenant_id: int
    tenant_name: str


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "E-mail já cadastrado")

    # Parse data_abertura string into date object if provided
    data_abertura_parsed: Optional[date] = None
    if body.data_abertura:
        try:
            data_abertura_parsed = date.fromisoformat(body.data_abertura)
        except ValueError:
            pass

    tenant = Tenant(
        name=body.tenant_name,
        document=body.document,
        document_type=body.document_type,
        email=body.email,
        razao_social=body.razao_social,
        nome_fantasia=body.nome_fantasia,
        cnae_code=body.cnae_code,
        cnae_description=body.cnae_description,
        natureza_juridica=body.natureza_juridica,
        situacao_cadastral=body.situacao_cadastral,
        capital_social=Decimal(str(body.capital_social)) if body.capital_social is not None else None,
        data_abertura=data_abertura_parsed,
        porte=body.porte,
        logradouro=body.logradouro,
        numero=body.numero,
        complemento=body.complemento,
        bairro=body.bairro,
        municipio=body.municipio,
        uf_address=body.uf_address,
        cep=body.cep,
    )
    session.add(tenant)
    await session.flush()

    user = User(
        tenant_id=tenant.id,
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    await session.flush()

    # ── Cria empresa primária automaticamente em tenant_companies ──
    # Se o documento for CNPJ, busca os dados completos (incluindo sócios e CNAEs secundários)
    if body.document_type == TenantType.cnpj:
        digits = re.sub(r"\D", "", body.document)
        if len(digits) == 14:
            try:
                full = await lookup_cnpj(digits)
                company = TenantCompany(
                    tenant_id=tenant.id,
                    cnpj=full["cnpj"],
                    cnpj_digits=digits,
                    razao_social=full["razao_social"] or body.tenant_name,
                    nome_fantasia=full.get("nome_fantasia"),
                    situacao_cadastral=full.get("situacao_cadastral"),
                    data_situacao_cadastral=full.get("data_situacao_cadastral"),
                    tipo=full.get("tipo"),
                    natureza_juridica=full.get("natureza_juridica"),
                    porte=full.get("porte"),
                    capital_social=Decimal(str(full["capital_social"])) if full.get("capital_social") else None,
                    data_abertura=date.fromisoformat(full["data_abertura"]) if full.get("data_abertura") else None,
                    regime_tributario=full.get("regime_tributario"),
                    opcao_simples=full.get("opcao_simples"),
                    opcao_mei=full.get("opcao_mei"),
                    cnae_code=full.get("cnae_code"),
                    cnae_description=full.get("cnae_description"),
                    cnaes_secundarios_json=json.dumps(full.get("cnaes_secundarios", []), ensure_ascii=False),
                    tipo_logradouro=full.get("tipo_logradouro"),
                    logradouro=full.get("logradouro"),
                    numero=full.get("numero"),
                    complemento=full.get("complemento"),
                    bairro=full.get("bairro"),
                    municipio=full.get("municipio"),
                    uf=full.get("uf"),
                    cep=full.get("cep"),
                    telefone=full.get("telefone"),
                    email=full.get("email"),
                    socios_json=json.dumps(full.get("socios", []), ensure_ascii=False),
                    is_primary=True,
                )
                session.add(company)
            except Exception:
                # Se a BrasilAPI falhar, usa apenas os dados enviados no cadastro
                company = TenantCompany(
                    tenant_id=tenant.id,
                    cnpj=format_cnpj(digits),
                    cnpj_digits=digits,
                    razao_social=body.razao_social or body.tenant_name,
                    nome_fantasia=body.nome_fantasia,
                    situacao_cadastral=body.situacao_cadastral,
                    natureza_juridica=body.natureza_juridica,
                    porte=body.porte,
                    capital_social=Decimal(str(body.capital_social)) if body.capital_social else None,
                    data_abertura=data_abertura_parsed,
                    cnae_code=body.cnae_code,
                    cnae_description=body.cnae_description,
                    logradouro=body.logradouro,
                    numero=body.numero,
                    complemento=body.complemento,
                    bairro=body.bairro,
                    municipio=body.municipio,
                    uf=body.uf_address,
                    cep=body.cep,
                    is_primary=True,
                )
                session.add(company)

    await session.commit()
    await session.refresh(user)
    return {"message": "Cadastro realizado com sucesso", "user_id": user.id}


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    tenant = await session.get(Tenant, user.tenant_id)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        user_name=user.name,
        user_role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=tenant.name if tenant else "",
    )


@router.post("/sso", response_model=TokenResponse)
async def sso_login(body: dict, session: AsyncSession = Depends(get_session)):
    payload = verify_sso_token(body.get("token", ""))
    if not payload:
        raise HTTPException(401, "Token SSO inválido")

    email = payload.get("email")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Usuário não encontrado no módulo Procurement")

    tenant = await session.get(Tenant, user.tenant_id)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        user_name=user.name,
        user_role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=tenant.name if tenant else "",
    )


class ForgotRequest(BaseModel):
    email: EmailStr

class ResetRequest(BaseModel):
    token: str
    password: str


def _send_reset_email(to_email: str, reset_link: str, user_name: str):
    body = f"""Olá, {user_name}!

Recebemos uma solicitação para redefinir a senha da sua conta no Drive Data Licitações.

Clique no link abaixo para criar uma nova senha (válido por 30 minutos):

{reset_link}

Se você não solicitou a redefinição, ignore este e-mail.

Equipe Drive Data
"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "Redefinição de senha — Drive Data"
    msg["From"]    = settings.smtp_from
    msg["To"]      = to_email

    try:
        if settings.smtp_port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx) as s:
                s.login(settings.smtp_user, settings.smtp_password)
                s.sendmail(settings.smtp_from, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
                s.ehlo(); s.starttls(); s.ehlo()
                s.login(settings.smtp_user, settings.smtp_password)
                s.sendmail(settings.smtp_from, [to_email], msg.as_string())
    except Exception as e:
        raise RuntimeError(f"SMTP error: {e}")


@router.post("/forgot-password")
async def forgot_password(body: ForgotRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Responde sempre com sucesso para não revelar se o e-mail existe
    if not user:
        return {"message": "Se este e-mail estiver cadastrado, você receberá as instruções em instantes."}

    token = secrets.token_urlsafe(32)
    _reset_tokens[token] = (user.id, datetime.utcnow() + timedelta(minutes=30))

    reset_link = f"{settings.frontend_url}/reset-password?token={token}"

    if settings.smtp_user:
        try:
            _send_reset_email(body.email, reset_link, user.name)
        except Exception as e:
            raise HTTPException(503, f"Erro ao enviar e-mail: {e}")
    else:
        # SMTP não configurado — retorna o link diretamente (desenvolvimento)
        return {"message": "SMTP não configurado.", "reset_link": reset_link}

    return {"message": "Se este e-mail estiver cadastrado, você receberá as instruções em instantes."}


@router.post("/reset-password")
async def reset_password(body: ResetRequest, session: AsyncSession = Depends(get_session)):
    entry = _reset_tokens.get(body.token)
    if not entry:
        raise HTTPException(400, "Token inválido ou expirado.")

    user_id, expires = entry
    if datetime.utcnow() > expires:
        del _reset_tokens[body.token]
        raise HTTPException(400, "Token expirado. Solicite um novo link.")

    if len(body.password) < 6:
        raise HTTPException(400, "A senha deve ter pelo menos 6 caracteres.")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")

    user.hashed_password = hash_password(body.password)
    session.add(user)
    await session.commit()
    del _reset_tokens[body.token]

    return {"message": "Senha redefinida com sucesso. Faça login com a nova senha."}


@router.get("/me")
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    tenant = await session.get(Tenant, user.tenant_id)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "tenant_name": tenant.name if tenant else "",
    }


@router.get("/me/tenant")
async def me_tenant(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    tenant = await session.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return {
        "id": tenant.id,
        "name": tenant.name,
        "document": tenant.document,
        "document_type": tenant.document_type,
        "email": tenant.email,
        "phone": tenant.phone,
        "active": tenant.active,
        "created_at": tenant.created_at,
        # Dados da Receita Federal
        "razao_social": tenant.razao_social,
        "nome_fantasia": tenant.nome_fantasia,
        "cnae_code": tenant.cnae_code,
        "cnae_description": tenant.cnae_description,
        "natureza_juridica": tenant.natureza_juridica,
        "situacao_cadastral": tenant.situacao_cadastral,
        "capital_social": float(tenant.capital_social) if tenant.capital_social is not None else None,
        "data_abertura": tenant.data_abertura,
        "porte": tenant.porte,
        # Endereço
        "logradouro": tenant.logradouro,
        "numero": tenant.numero,
        "complemento": tenant.complemento,
        "bairro": tenant.bairro,
        "municipio": tenant.municipio,
        "uf_address": tenant.uf_address,
        "cep": tenant.cep,
        # Plano
        "plan": tenant.plan,
        "plan_expires_at": tenant.plan_expires_at,
    }
