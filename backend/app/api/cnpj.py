import re
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/cnpj", tags=["cnpj"])


def format_cnpj(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


@router.get("/{digits}")
async def lookup_cnpj(digits: str):
    clean = re.sub(r"\D", "", digits)
    if len(clean) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 dígitos")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{clean}")
            resp.raise_for_status()
            d = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="CNPJ não encontrado na Receita Federal")
        raise HTTPException(status_code=502, detail="Erro ao consultar BrasilAPI")
    except Exception:
        raise HTTPException(status_code=502, detail="Serviço de consulta indisponível")

    cnae_code = str(d.get("cnae_fiscal", ""))
    cnae_desc = d.get("cnae_fiscal_descricao", "")
    cnae_principal = f"{cnae_code} - {cnae_desc}" if cnae_code and cnae_desc else None

    # CNAEs secundários
    cnaes_sec = [
        {"codigo": str(c.get("codigo", "")), "descricao": c.get("descricao", "")}
        for c in (d.get("cnaes_secundarios") or [])
        if c.get("codigo")
    ]

    # Quadro Societário (QSA)
    socios = [
        {
            "nome": s.get("nome_socio", ""),
            "qualificacao": s.get("qualificacao_socio", ""),
            "faixa_etaria": s.get("faixa_etaria", ""),
            "data_entrada": s.get("data_entrada_sociedade", ""),
            "cpf_cnpj": s.get("cnpj_cpf_do_socio", ""),
        }
        for s in (d.get("qsa") or [])
        if s.get("nome_socio")
    ]

    # Telefones
    tel1 = (d.get("ddd_telefone_1") or "").strip()
    tel2 = (d.get("ddd_telefone_2") or "").strip()
    telefone = tel1
    if tel2 and tel2 != tel1:
        telefone = f"{tel1} / {tel2}" if tel1 else tel2

    # Simples / MEI
    simples = d.get("opcao_pelo_simples")
    mei     = d.get("opcao_pelo_mei")

    # Regime tributário: BrasilAPI retorna array de {ano, forma_de_tributacao, ...}
    # Pegamos o mais recente como string
    regime = d.get("regime_tributario")
    regime_str: Optional[str] = None
    if isinstance(regime, list) and regime:
        latest = max(regime, key=lambda r: r.get("ano") or 0)
        regime_str = latest.get("forma_de_tributacao")
    elif isinstance(regime, str):
        regime_str = regime

    return {
        "cnpj":              format_cnpj(clean),
        "cnpj_digits":       clean,
        "razao_social":      d.get("razao_social", ""),
        "nome_fantasia":     d.get("nome_fantasia") or None,
        "situacao_cadastral": d.get("descricao_situacao_cadastral"),
        "data_situacao_cadastral": d.get("data_situacao_cadastral"),
        "motivo_situacao":   d.get("descricao_motivo_situacao_cadastral") or None,
        "tipo":              "Filial" if d.get("identificador_matriz_filial") == 2 else "Matriz",
        "natureza_juridica": d.get("natureza_juridica"),
        "porte":             d.get("descricao_porte") or d.get("porte"),
        "capital_social":    float(d.get("capital_social") or 0) or None,
        "data_abertura":     d.get("data_inicio_atividade"),
        "regime_tributario": regime_str,
        "opcao_simples":     simples,
        "opcao_mei":         mei,
        # CNAE
        "cnae_code":         cnae_code,
        "cnae_description":  cnae_desc,
        "cnae_principal":    cnae_principal,
        "cnaes_secundarios": cnaes_sec,
        # Endereço
        "tipo_logradouro":   d.get("descricao_tipo_de_logradouro") or None,
        "logradouro":        d.get("logradouro"),
        "numero":            d.get("numero"),
        "complemento":       d.get("complemento") or None,
        "bairro":            d.get("bairro"),
        "municipio":         d.get("municipio"),
        "uf":                d.get("uf"),
        "cep":               re.sub(r"\D", "", str(d.get("cep") or "")),
        # Contato
        "telefone":          telefone or None,
        "email":             d.get("email") or None,
        # Quadro societário
        "socios":            socios,
    }
