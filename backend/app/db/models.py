from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship, Column
import sqlalchemy as sa
from sqlalchemy import Text


# ─── Enums ────────────────────────────────────────────────────────────────────

class TenantType(str, Enum):
    cnpj = "cnpj"
    cpf = "cpf"


class BidSphere(str, Enum):
    federal = "federal"
    estadual = "estadual"
    municipal = "municipal"


class BidStatus(str, Enum):
    aberta = "aberta"
    andamento = "andamento"
    encerrada = "encerrada"
    cancelada = "cancelada"
    programada = "programada"


class BidModality(str, Enum):
    pregao = "pregao"
    concorrencia = "concorrencia"
    tomada_preco = "tomada_preco"
    convite = "convite"
    dispensa = "dispensa"
    inexigibilidade = "inexigibilidade"
    leilao = "leilao"
    dialogo_competitivo = "dialogo_competitivo"


class ObjectType(str, Enum):
    bem = "bem"
    servico = "servico"
    obra = "obra"
    consultoria = "consultoria"
    misto = "misto"


class AlertStatus(str, Enum):
    novo = "novo"
    visto = "visto"
    favorito = "favorito"
    descartado = "descartado"


class ScrapeStatus(str, Enum):
    sucesso = "sucesso"
    erro = "erro"
    parcial = "parcial"


class PortalType(str, Enum):
    api_rest = "api_rest"
    scraping_html = "scraping_html"
    pncp_passthrough = "pncp_passthrough"
    manual = "manual"


class UserRole(str, Enum):
    admin = "admin"    # Admin da empresa: gerencia usuários, vê tudo
    full = "full"      # Full: visualiza tudo de todos da empresa, não gerencia
    simple = "simple"  # Simple: vê apenas seu próprio perfil e interações


# ─── Tenant ───────────────────────────────────────────────────────────────────

class Tenant(SQLModel, table=True):
    __tablename__ = "proc_tenants"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    document: str = Field(max_length=18, unique=True)
    document_type: TenantType
    email: str = Field(max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Dados da Receita Federal
    razao_social: Optional[str] = Field(default=None)
    nome_fantasia: Optional[str] = Field(default=None)
    cnae_code: Optional[str] = Field(default=None, max_length=10)
    cnae_description: Optional[str] = Field(default=None, max_length=255)
    natureza_juridica: Optional[str] = Field(default=None, max_length=255)
    situacao_cadastral: Optional[str] = Field(default=None, max_length=50)
    capital_social: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    data_abertura: Optional[date] = Field(default=None)
    porte: Optional[str] = Field(default=None, max_length=50)

    # Endereço
    logradouro: Optional[str] = Field(default=None, max_length=255)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=100)
    bairro: Optional[str] = Field(default=None, max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    uf_address: Optional[str] = Field(default=None, max_length=2)
    cep: Optional[str] = Field(default=None, max_length=10)

    # Plano
    plan: str = Field(default="free")
    plan_expires_at: Optional[datetime] = Field(default=None)

    users: List["User"] = Relationship(back_populates="tenant")
    profiles: List["ProcurementProfile"] = Relationship(back_populates="tenant")
    trackings: List["BidTracking"] = Relationship(back_populates="tenant")


class User(SQLModel, table=True):
    __tablename__ = "proc_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="proc_tenants.id")
    name: str = Field(max_length=255)
    email: str = Field(max_length=255, unique=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.admin)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    tenant: Optional[Tenant] = Relationship(back_populates="users")
    interactions: List["BidInteraction"] = Relationship(back_populates="user")


# ─── Public Bids ──────────────────────────────────────────────────────────────

class PublicBid(SQLModel, table=True):
    __tablename__ = "public_bids"

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(max_length=255)
    source: str = Field(max_length=50)

    # Identificação
    title: str = Field(max_length=500)
    description: Optional[str] = Field(default=None)
    object_type: Optional[ObjectType] = Field(default=None)

    # Classificação
    category_code: Optional[str] = Field(default=None, max_length=10)
    category_name: Optional[str] = Field(default=None, max_length=255)
    branch_code: Optional[str] = Field(default=None, max_length=10)
    branch_name: Optional[str] = Field(default=None, max_length=255)

    # Localização
    sphere: Optional[BidSphere] = Field(default=None)
    state: Optional[str] = Field(default=None, max_length=2)
    city: Optional[str] = Field(default=None, max_length=255)
    city_code: Optional[str] = Field(default=None, max_length=7)

    # Órgão
    organ_name: Optional[str] = Field(default=None, max_length=255)
    organ_cnpj: Optional[str] = Field(default=None, max_length=18)

    # Datas
    publication_date: Optional[date] = Field(default=None)
    opening_date: Optional[date] = Field(default=None)
    closing_date: Optional[date] = Field(default=None)
    status: BidStatus = Field(default=BidStatus.aberta)
    status_date: Optional[datetime] = Field(default=None)

    # Valores
    estimated_value: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    maximum_value: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    modality: Optional[BidModality] = Field(default=None)
    dispute_mode: Optional[str] = Field(default=None, max_length=40)   # modoDisputaNome do PNCP

    # Requisitos
    min_patrimony: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    min_revenue: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    years_of_operation: Optional[int] = Field(default=None)
    requires_sme: bool = Field(default=False)
    requires_mei: bool = Field(default=False)

    # Contato
    contact_name: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = Field(default=None, max_length=20)

    # URLs
    edital_url: Optional[str] = Field(default=None, max_length=500)
    details_url: Optional[str] = Field(default=None, max_length=500)
    platform_url: Optional[str] = Field(default=None, max_length=500)

    # Classificação TI & Dados pré-calculada no sync (deixa a busca instantânea)
    is_ti: Optional[bool] = Field(default=None)
    ti_score: Optional[int] = Field(default=None)

    # Sistema
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_scraped: Optional[datetime] = Field(default=None)
    winners_synced_at: Optional[datetime] = Field(default=None)   # quando checamos vencedores no PNCP

    alerts: List["ProcurementAlert"] = Relationship(back_populates="bid")
    trackings: List["BidTracking"] = Relationship(back_populates="bid")

    class Config:
        # Garante unicidade source + external_id via constraint na migração
        pass


# ─── Procurement Profile ──────────────────────────────────────────────────────

class ProcurementProfile(SQLModel, table=True):
    __tablename__ = "procurement_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="proc_tenants.id")
    user_id: int = Field(foreign_key="proc_users.id")
    name: str = Field(max_length=255)
    active: bool = Field(default=True)

    # Filtros (armazenados como texto separado por vírgula)
    preferred_spheres: Optional[str] = Field(default=None)     # "federal,estadual"
    preferred_states: Optional[str] = Field(default=None)      # "SP,RJ,MG"
    preferred_cities: Optional[str] = Field(default=None)
    preferred_branches: Optional[str] = Field(default=None)    # "TI,Construção"
    preferred_categories: Optional[str] = Field(default=None)  # códigos CATMAT

    # Limites de valor
    min_estimated_value: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    max_estimated_value: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)

    # Preferências
    exclude_modalities: Optional[str] = Field(default=None)    # "dispensa,inexigibilidade"
    require_sme_reservation: bool = Field(default=False)
    only_with_deadline: bool = Field(default=False)
    alert_days_before: int = Field(default=7)

    # Keywords
    keywords: Optional[str] = Field(default=None)              # "software,sistema,dados"
    exclude_keywords: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    tenant: Optional[Tenant] = Relationship(back_populates="profiles")
    alerts: List["ProcurementAlert"] = Relationship(back_populates="profile")


# ─── Alerts ───────────────────────────────────────────────────────────────────

class ProcurementAlert(SQLModel, table=True):
    __tablename__ = "procurement_alerts"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="proc_tenants.id")
    profile_id: int = Field(foreign_key="procurement_profiles.id")
    bid_id: int = Field(foreign_key="public_bids.id")

    match_score: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=3)
    match_reasons: Optional[str] = Field(default=None)  # JSON serializado

    status: AlertStatus = Field(default=AlertStatus.novo)
    viewed_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = Field(default=None)

    profile: Optional[ProcurementProfile] = Relationship(back_populates="alerts")
    bid: Optional[PublicBid] = Relationship(back_populates="alerts")


# ─── Tracking ─────────────────────────────────────────────────────────────────

class BidTracking(SQLModel, table=True):
    __tablename__ = "bid_tracking"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="proc_tenants.id")
    bid_id: int = Field(foreign_key="public_bids.id")

    participated: bool = Field(default=False)
    proposal_submitted: bool = Field(default=False)
    proposal_date: Optional[date] = Field(default=None)
    proposal_value: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)

    won: Optional[bool] = Field(default=None)
    result_date: Optional[date] = Field(default=None)
    contract_value: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    contract_id: Optional[str] = Field(default=None, max_length=255)

    notes: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    tenant: Optional[Tenant] = Relationship(back_populates="trackings")
    bid: Optional[PublicBid] = Relationship(back_populates="trackings")


# ─── Scrape Logs ──────────────────────────────────────────────────────────────

class ScrapeLog(SQLModel, table=True):
    __tablename__ = "scrape_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(max_length=50)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(default=None)
    status: ScrapeStatus = Field(default=ScrapeStatus.sucesso)
    records_found: int = Field(default=0)
    records_inserted: int = Field(default=0)
    records_updated: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Tenant Companies (CNPJs adicionais) ─────────────────────────────────────

class TenantCompany(SQLModel, table=True):
    __tablename__ = "tenant_companies"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="proc_tenants.id")

    cnpj: str = Field(max_length=18)           # formatado XX.XXX.XXX/XXXX-XX
    cnpj_digits: str = Field(max_length=14)
    razao_social: str = Field(max_length=255)
    nome_fantasia: Optional[str] = Field(default=None, max_length=255)
    situacao_cadastral: Optional[str] = Field(default=None, max_length=100)
    data_situacao_cadastral: Optional[str] = Field(default=None, max_length=20)
    tipo: Optional[str] = Field(default=None, max_length=10)     # Matriz / Filial
    natureza_juridica: Optional[str] = Field(default=None, max_length=255)
    porte: Optional[str] = Field(default=None, max_length=100)
    capital_social: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    data_abertura: Optional[date] = Field(default=None)
    regime_tributario: Optional[str] = Field(default=None, max_length=100)
    opcao_simples: Optional[bool] = Field(default=None)
    opcao_mei: Optional[bool] = Field(default=None)

    cnae_code: Optional[str] = Field(default=None, max_length=10)
    cnae_description: Optional[str] = Field(default=None, max_length=255)
    cnaes_secundarios_json: Optional[str] = Field(default=None, sa_column=Column(Text))

    tipo_logradouro: Optional[str] = Field(default=None, max_length=50)
    logradouro: Optional[str] = Field(default=None, max_length=255)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=100)
    bairro: Optional[str] = Field(default=None, max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    uf: Optional[str] = Field(default=None, max_length=2)
    cep: Optional[str] = Field(default=None, max_length=10)
    telefone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)

    socios_json: Optional[str] = Field(default=None, sa_column=Column(Text))

    is_primary: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Bid Interactions (favoritos / visto / descartado — por usuário) ─────────

class BidInteraction(SQLModel, table=True):
    __tablename__ = "bid_interactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="proc_users.id")
    tenant_id: int = Field(foreign_key="proc_tenants.id")  # desnormalizado para queries por empresa
    bid_id: int = Field(foreign_key="public_bids.id")

    is_favorite: bool = Field(default=False)
    is_viewed: bool = Field(default=False)
    is_discarded: bool = Field(default=False)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    viewed_at: Optional[datetime] = Field(default=None)
    favorited_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional["User"] = Relationship(back_populates="interactions")


# ─── Data Sources (informativo de fontes de coleta) ───────────────────────────

class DataSource(SQLModel, table=True):
    __tablename__ = "data_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(max_length=50, unique=True)        # "pncp", "comprasnet", etc.
    name: str = Field(max_length=100)
    description: str = Field(max_length=500)
    official_url: str = Field(max_length=255)
    active: bool = Field(default=True)
    last_sync_at: Optional[datetime] = Field(default=None)
    last_sync_status: Optional[str] = Field(default=None, max_length=20)  # sucesso/erro/parcial
    last_sync_records: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Chat Messages ────────────────────────────────────────────────────────────

class MunicipalPortal(SQLModel, table=True):
    __tablename__ = "municipal_portals"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Localização
    ibge_code: Optional[str] = Field(default=None, max_length=7)
    city: Optional[str] = Field(default=None, max_length=255)
    state: Optional[str] = Field(default=None, max_length=2)

    # Portal
    portal_name: Optional[str] = Field(default=None, max_length=255)
    portal_url: str = Field(max_length=500)
    system_name: Optional[str] = Field(default=None, max_length=100)
    portal_type: PortalType = Field(default=PortalType.scraping_html)
    api_endpoint: Optional[str] = Field(default=None, max_length=500)
    scraper_key: Optional[str] = Field(default=None, max_length=50)

    # Status
    active: bool = Field(default=True)
    verified: bool = Field(default=False)

    # Contato
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    last_sync_at: Optional[datetime] = Field(default=None)
    last_sync_status: Optional[str] = Field(default=None, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Chat Messages ────────────────────────────────────────────────────────────

class ChatMessage(SQLModel, table=True):
    __tablename__ = "proc_chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="proc_tenants.id")
    user_id: int = Field(foreign_key="proc_users.id")
    role: str = Field(max_length=20)  # "user" or "assistant"
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Contratos públicos (canal "recontratação de TI") ─────────────────────────

class PublicContract(SQLModel, table=True):
    __tablename__ = "public_contracts"

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(max_length=300)   # dedup: numeroControlePncpCompra::numeroContrato
    source: str = Field(default="pncp", max_length=50)

    objeto: str = Field(max_length=1000)
    valor: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)

    organ_name: Optional[str] = Field(default=None, max_length=255)
    organ_cnpj: Optional[str] = Field(default=None, max_length=18)
    sphere: Optional[str] = Field(default=None, max_length=20)
    state: Optional[str] = Field(default=None, max_length=2)
    city: Optional[str] = Field(default=None, max_length=255)

    # incumbente (quem tem o contrato hoje)
    supplier_name: Optional[str] = Field(default=None, max_length=255)
    supplier_document: Optional[str] = Field(default=None, max_length=20)

    vigencia_inicio: Optional[date] = Field(default=None)
    vigencia_fim: Optional[date] = Field(default=None)   # o que dispara a recontratação

    is_ti: Optional[bool] = Field(default=None)
    ti_score: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FundingOpportunity(SQLModel, table=True):
    """Canal 'Fomento': editais/chamadas de agências de fomento (FAPESP etc.).
    Onde mora a oportunidade para uma consultoria de dados/TI: programas de
    inovação (PIPE) e chamadas com prazo de submissão abrindo agora."""
    __tablename__ = "funding_opportunities"

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(max_length=300)   # dedup: source::codigo
    source: str = Field(default="fapesp", max_length=50)
    agency: Optional[str] = Field(default=None, max_length=80)   # FAPESP, FINEP, BNDES...

    title: str = Field(max_length=600)
    area: Optional[str] = Field(default=None, sa_column=Column(Text))
    modality: Optional[str] = Field(default=None, max_length=300)
    url: Optional[str] = Field(default=None, max_length=500)

    deadline: Optional[date] = Field(default=None)   # data-limite de submissão
    is_open: bool = Field(default=True)

    is_ti: Optional[bool] = Field(default=None)
    ti_score: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BidWinner(SQLModel, table=True):
    """Vencedor de uma licitação (pré-calculado do PNCP após homologação).
    Uma linha por fornecedor vencedor por licitação. Alimenta a tela Vencedores
    (lista) e o ranking de concorrentes (agregado por fornecedor)."""
    __tablename__ = "bid_winners"

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(max_length=255)   # controle PNCP da licitação
    bid_id: Optional[int] = Field(default=None, index=True)

    bid_title: Optional[str] = Field(default=None, max_length=500)
    organ_name: Optional[str] = Field(default=None, max_length=255)
    state: Optional[str] = Field(default=None, max_length=2)
    sphere: Optional[str] = Field(default=None, max_length=20)
    homologated_at: Optional[date] = Field(default=None)

    supplier_name: Optional[str] = Field(default=None, max_length=255)
    supplier_document: str = Field(max_length=20)
    porte: Optional[str] = Field(default=None, max_length=40)

    valor_total: Optional[Decimal] = Field(default=None, decimal_places=2, max_digits=15)
    items_won: int = Field(default=0)
    is_ti: Optional[bool] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
