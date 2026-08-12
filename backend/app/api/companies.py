"""Gerenciamento de CNPJs/empresas do tenant."""
import json
import re
from decimal import Decimal
from datetime import date
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.db.models import TenantCompany, User
from app.auth import get_current_user
from app.api.cnpj import lookup_cnpj

router = APIRouter(prefix="/api/companies", tags=["companies"])


class AddCompanyBody(BaseModel):
    cnpj_digits: str


def _company_dict(c: TenantCompany) -> dict:
    return {
        "id": c.id,
        "cnpj": c.cnpj,
        "cnpj_digits": c.cnpj_digits,
        "razao_social": c.razao_social,
        "nome_fantasia": c.nome_fantasia,
        "situacao_cadastral": c.situacao_cadastral,
        "data_situacao_cadastral": c.data_situacao_cadastral,
        "tipo": c.tipo,
        "natureza_juridica": c.natureza_juridica,
        "porte": c.porte,
        "capital_social": float(c.capital_social) if c.capital_social else None,
        "data_abertura": str(c.data_abertura) if c.data_abertura else None,
        "regime_tributario": c.regime_tributario,
        "opcao_simples": c.opcao_simples,
        "opcao_mei": c.opcao_mei,
        "cnae_code": c.cnae_code,
        "cnae_description": c.cnae_description,
        "cnae_principal": f"{c.cnae_code} - {c.cnae_description}" if c.cnae_code and c.cnae_description else None,
        "cnaes_secundarios": json.loads(c.cnaes_secundarios_json) if c.cnaes_secundarios_json else [],
        "tipo_logradouro": c.tipo_logradouro,
        "logradouro": c.logradouro,
        "numero": c.numero,
        "complemento": c.complemento,
        "bairro": c.bairro,
        "municipio": c.municipio,
        "uf": c.uf,
        "cep": c.cep,
        "telefone": c.telefone,
        "email": c.email,
        "socios": json.loads(c.socios_json) if c.socios_json else [],
        "is_primary": c.is_primary,
        "created_at": c.created_at,
    }


@router.get("")
async def list_companies(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(TenantCompany)
        .where(TenantCompany.tenant_id == user.tenant_id)
        .order_by(TenantCompany.is_primary.desc(), TenantCompany.razao_social)
    )
    return [_company_dict(c) for c in result.scalars().all()]


@router.post("/import-from-tenant", status_code=201)
async def import_from_tenant(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Importa o CNPJ principal do cadastro do tenant para tenant_companies.

    Usado por contas antigas que foram criadas antes do recurso multi-CNPJ.
    """
    from app.db.models import Tenant, TenantType
    from app.api.cnpj import lookup_cnpj

    tenant = await session.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")

    if tenant.document_type != TenantType.cnpj:
        raise HTTPException(400, "Tenant principal não é CNPJ")

    digits = re.sub(r"\D", "", tenant.document)
    if len(digits) != 14:
        raise HTTPException(400, "CNPJ do tenant inválido")

    # Verifica se já existe
    existing = await session.execute(
        select(TenantCompany).where(
            TenantCompany.tenant_id == user.tenant_id,
            TenantCompany.cnpj_digits == digits,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Empresa já está importada")

    # Busca dados completos via BrasilAPI
    try:
        d = await lookup_cnpj(digits)
    except Exception as e:
        raise HTTPException(502, f"Erro ao consultar CNPJ: {e}")

    company = TenantCompany(
        tenant_id=user.tenant_id,
        cnpj=d["cnpj"],
        cnpj_digits=digits,
        razao_social=d["razao_social"],
        nome_fantasia=d.get("nome_fantasia"),
        situacao_cadastral=d.get("situacao_cadastral"),
        data_situacao_cadastral=d.get("data_situacao_cadastral"),
        tipo=d.get("tipo"),
        natureza_juridica=d.get("natureza_juridica"),
        porte=d.get("porte"),
        capital_social=Decimal(str(d["capital_social"])) if d.get("capital_social") else None,
        data_abertura=date.fromisoformat(d["data_abertura"]) if d.get("data_abertura") else None,
        regime_tributario=d.get("regime_tributario"),
        opcao_simples=d.get("opcao_simples"),
        opcao_mei=d.get("opcao_mei"),
        cnae_code=d.get("cnae_code"),
        cnae_description=d.get("cnae_description"),
        cnaes_secundarios_json=json.dumps(d.get("cnaes_secundarios", []), ensure_ascii=False),
        tipo_logradouro=d.get("tipo_logradouro"),
        logradouro=d.get("logradouro"),
        numero=d.get("numero"),
        complemento=d.get("complemento"),
        bairro=d.get("bairro"),
        municipio=d.get("municipio"),
        uf=d.get("uf"),
        cep=d.get("cep"),
        telefone=d.get("telefone"),
        email=d.get("email"),
        socios_json=json.dumps(d.get("socios", []), ensure_ascii=False),
        is_primary=True,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return _company_dict(company)


@router.post("", status_code=201)
async def add_company(
    body: AddCompanyBody,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    digits = re.sub(r"\D", "", body.cnpj_digits)
    if len(digits) != 14:
        raise HTTPException(400, "CNPJ inválido")

    # Verificar se já existe para este tenant
    existing = await session.execute(
        select(TenantCompany).where(
            TenantCompany.tenant_id == user.tenant_id,
            TenantCompany.cnpj_digits == digits,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Este CNPJ já está cadastrado nesta conta")

    # Consultar BrasilAPI (reutiliza o endpoint)
    try:
        d = await lookup_cnpj(digits)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erro ao consultar CNPJ: {e}")

    # Verificar se é o primeiro (primário)
    count = (await session.execute(
        select(TenantCompany).where(TenantCompany.tenant_id == user.tenant_id)
    )).scalars().all()
    is_primary = len(count) == 0

    company = TenantCompany(
        tenant_id=user.tenant_id,
        cnpj=d["cnpj"],
        cnpj_digits=digits,
        razao_social=d["razao_social"],
        nome_fantasia=d.get("nome_fantasia"),
        situacao_cadastral=d.get("situacao_cadastral"),
        data_situacao_cadastral=d.get("data_situacao_cadastral"),
        tipo=d.get("tipo"),
        natureza_juridica=d.get("natureza_juridica"),
        porte=d.get("porte"),
        capital_social=Decimal(str(d["capital_social"])) if d.get("capital_social") else None,
        data_abertura=date.fromisoformat(d["data_abertura"]) if d.get("data_abertura") else None,
        regime_tributario=d.get("regime_tributario"),
        opcao_simples=d.get("opcao_simples"),
        opcao_mei=d.get("opcao_mei"),
        cnae_code=d.get("cnae_code"),
        cnae_description=d.get("cnae_description"),
        cnaes_secundarios_json=json.dumps(d.get("cnaes_secundarios", []), ensure_ascii=False),
        tipo_logradouro=d.get("tipo_logradouro"),
        logradouro=d.get("logradouro"),
        numero=d.get("numero"),
        complemento=d.get("complemento"),
        bairro=d.get("bairro"),
        municipio=d.get("municipio"),
        uf=d.get("uf"),
        cep=d.get("cep"),
        telefone=d.get("telefone"),
        email=d.get("email"),
        socios_json=json.dumps(d.get("socios", []), ensure_ascii=False),
        is_primary=is_primary,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return _company_dict(company)


@router.delete("/{company_id}", status_code=204)
async def remove_company(
    company_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    company = await session.get(TenantCompany, company_id)
    if not company or company.tenant_id != user.tenant_id:
        raise HTTPException(404, "Empresa não encontrada")
    if company.is_primary:
        raise HTTPException(400, "Não é possível remover a empresa principal")
    await session.delete(company)
    await session.commit()


@router.patch("/{company_id}/set-primary", status_code=200)
async def set_primary(
    company_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Desmarca todas
    result = await session.execute(
        select(TenantCompany).where(TenantCompany.tenant_id == user.tenant_id)
    )
    for c in result.scalars().all():
        c.is_primary = (c.id == company_id)
        session.add(c)

    await session.commit()
    return {"ok": True}
