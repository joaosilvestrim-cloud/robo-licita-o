import ssl
from urllib.parse import urlsplit, urlunsplit, parse_qsl

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Garante o driver asyncpg e remove query params que o asyncpg não entende.

    Aceita tanto a string do Supabase (postgresql://...?sslmode=require)
    quanto a interna (postgresql+asyncpg://...). Params de SSL/pgbouncer
    são tratados via connect_args, não na URL.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    parts = urlsplit(url)
    # descarta sslmode, pgbouncer, etc. — o asyncpg rejeita esses na querystring
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in
            ("sslmode", "pgbouncer", "channel_binding", "target_session_attrs")]
    query = "&".join(f"{k}={v}" for k, v in kept)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _connect_args(url: str) -> dict:
    """SSL + desliga cache de prepared statements (necessário no pooler do Supabase)."""
    args: dict = {}
    # Qualquer host que não seja local roda com SSL (Supabase exige).
    host = urlsplit(url).hostname or ""
    if host not in ("localhost", "127.0.0.1", "postgres", "db"):
        ctx = ssl.create_default_context()
        # o pooler do Supabase pode ter CN diferente do host; não verificamos o cert
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        args["ssl"] = ctx
        # obrigatório para o Transaction Pooler (porta 6543) e inofensivo no resto
        args["statement_cache_size"] = 0
    return args


DATABASE_URL = _normalize_db_url(settings.database_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,          # revalida conexões (o backend pode dormir na Render)
    pool_recycle=1800,
    connect_args=_connect_args(DATABASE_URL),
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app.db import models  # noqa: F401 — ensure models are registered
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

        # ── Migrations incrementais ────────────────────────────────────────────
        # role em proc_users (existentes viram admin)
        await conn.execute(text(
            "ALTER TABLE proc_users ADD COLUMN IF NOT EXISTS role VARCHAR(10) NOT NULL DEFAULT 'admin'"
        ))
        # índice único em bid_interactions (user × bid)
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_bid_interactions_user_bid "
            "ON bid_interactions(user_id, bid_id)"
        ))
        # índice único em public_bids (source × external_id) — evita duplicidade de licitação
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_public_bids_source_external "
            "ON public_bids(source, external_id)"
        ))
        # seed das fontes de dados
        await conn.execute(text("""
            INSERT INTO data_sources (key, name, description, official_url, active, created_at)
            VALUES
              ('pncp',                    'PNCP',                        'Portal Nacional de Contratações Públicas — fonte oficial da Lei 14.133/2021',          'https://pncp.gov.br',                               true, NOW()),
              ('comprasnet',              'ComprasNet/SIASG',            'Sistema federal de compras — histórico rico da Lei 8.666, ainda em operação',          'https://compras.dados.gov.br',                      true, NOW()),
              ('licitacoes_e',            'Licitações-e (BB)',           'Banco do Brasil — pregões de municípios e estados não integrados ao PNCP',             'https://www.licitacoes-e.com.br',                   true, NOW()),
              ('bec_sp',                  'BEC/SP',                      'Bolsa Eletrônica de Compras de SP — maior mercado comprador estadual',                 'https://www.bec.sp.gov.br',                         true, NOW()),
              ('dou',                     'DOU / Querido Diário',        'Diários oficiais municipais — avisos que antecedem entrada nos portais (OKBR)',        'https://queridodiario.ok.org.br',                   true, NOW()),
              ('licitacoes_e2_bb',        'Licitações-e2 BB',            'Banco do Brasil — portal v2 de licitações (licitacoes-e2.bb.com.br)',                  'https://licitacoes-e2.bb.com.br',                   true, NOW()),
              ('portal_compras_publicas', 'Portal de Compras Públicas',  'plataforma privada usada por municípios de MG, SP e outros (API REST)',                'https://www.portaldecompraspublicas.com.br',         true, NOW()),
              ('e_lic_sc',               'e-lic SC',                    'Portal de Licitações Eletrônicas de Santa Catarina (e-lic.sc.gov.br)',                  'https://e-lic.sc.gov.br',                           true, NOW()),
              ('celic_rs',               'CELIC RS',                    'Central de Licitações do Estado do RS (celic.rs.gov.br)',                               'https://www.celic.rs.gov.br',                       true, NOW()),
              ('comprasnet_ba',           'ComprasNet Bahia',            'Portal estadual de compras da Bahia (comprasnet.ba.gov.br)',                            'https://www.comprasnet.ba.gov.br',                  true, NOW()),
              ('compra_aberta',           'Compra Aberta',               'Plataforma privada Compra Aberta usada por municípios SP/Sul (compraaberta.com.br)',    'https://compraaberta.com.br',                       true, NOW()),
              ('bnc',                     'BNC',                         'Banco Nacional de Compras — usado por Sorocaba, Mauá e centenas de municípios SP/Sul',   'https://bnc.org.br',                                true, NOW())
            ON CONFLICT (key) DO NOTHING
        """))

        # seed dos portais municipais mapeados no arquivo MD
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS municipal_portals (
                id SERIAL PRIMARY KEY,
                ibge_code VARCHAR(7),
                city VARCHAR(255),
                state VARCHAR(2),
                portal_name VARCHAR(255),
                portal_url VARCHAR(500) NOT NULL,
                system_name VARCHAR(100),
                portal_type VARCHAR(30) NOT NULL DEFAULT 'scraping_html',
                api_endpoint VARCHAR(500),
                scraper_key VARCHAR(50),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                verified BOOLEAN NOT NULL DEFAULT FALSE,
                contact_email VARCHAR(255),
                contact_phone VARCHAR(20),
                notes TEXT,
                last_sync_at TIMESTAMP,
                last_sync_status VARCHAR(20),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        await conn.execute(text("""
            INSERT INTO municipal_portals (city, state, portal_name, portal_url, system_name, portal_type, scraper_key, active, verified, created_at, updated_at)
            VALUES
            -- ── PORTAIS ESTADUAIS ────────────────────────────────────────────
            ('(Estadual)', 'AC', 'Portal PNCP AC',           'https://pncp.gov.br',                              'PNCP',           'pncp_passthrough', 'pncp',        true, true,  NOW(), NOW()),
            ('(Estadual)', 'AL', 'Transparência AL',         'https://transparencia.al.gov.br/licitacao/editais/','HTML',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'AP', 'Portal Compras AP',        'https://compras.portal.ap.gov.br/',                'SIGA',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'AM', 'e-Compras AM',             'https://www.e-compras.am.gov.br/publico/',         'DLE',            'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'BA', 'ComprasNet Bahia',         'https://www.comprasnet.ba.gov.br/',                'ComprasNet BA',  'scraping_html',    'comprasnet_ba',true, false,NOW(), NOW()),
            ('(Estadual)', 'CE', 'Portal Compras CE',        'https://www.portalcompras.ce.gov.br/',             'Licitaweb',      'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'DF', 'Portal Compras DF',        'https://portal.compras.df.gov.br/licitacao',       'ComprasNet',     'pncp_passthrough', 'pncp',        true, true,  NOW(), NOW()),
            ('(Estadual)', 'ES', 'Portal Compras ES',        'https://compras.es.gov.br/',                       'SIGA',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'GO', 'SISLOG GO',                'https://sislog.go.gov.br/',                        'SISLOG',         'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'MA', 'Portal Compras MA',        'https://www.compras.ma.gov.br/portal/',            'SIGA',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'MT', 'Portal Aquisições MT',     'https://aquisicoes.seplag.mt.gov.br/home/',        'SIAG',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'MS', 'ComprasMS',                'https://www.compras.ms.gov.br/',                   'SGC',            'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'MG', 'ComprasMG',                'https://compras.mg.gov.br/',                       'CAGEF',          'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'PA', 'ComprasPará',              'https://www.compraspara.pa.gov.br/',               'SEPLAD',         'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'PB', 'Central Compras PB',       'https://centraldecompras.pb.gov.br/',              'SGC-PB',         'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'PR', 'ComprasParaná',            'https://www.administracao.pr.gov.br/Compras/',     'ComprasNet',     'pncp_passthrough', 'pncp',        true, false, NOW(), NOW()),
            ('(Estadual)', 'PE', 'PE Integrado',             'https://www.peintegrado.pe.gov.br/portal/',        'SECOP',          'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'PI', 'Central Compras PI',       'https://centraldecompras.sead.pi.gov.br/licitacoes/','SEAD',         'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'RJ', 'Portal Compras RJ',        'https://www.compras.rj.gov.br/',                   'SIGA',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'RN', 'Licita Fácil RN',          'https://licitafacil.tce.rn.gov.br/',               'LicitaFácil',    'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'RS', 'CELIC RS',                 'https://www.celic.rs.gov.br/inicial',              'CELIC',          'scraping_html',    'celic_rs',    true, false, NOW(), NOW()),
            ('(Estadual)', 'RO', 'Transparência RO',         'https://transparencia.ro.gov.br/licitacoes',       'SUPEL',          'pncp_passthrough', 'pncp',        true, false, NOW(), NOW()),
            ('(Estadual)', 'RR', 'Portal SELC RR',           'https://selc.rr.gov.br/',                          'SELC',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'SC', 'e-lic SC',                 'https://e-lic.sc.gov.br/',                         'e-lic SC',       'scraping_html',    'e_lic_sc',    true, false, NOW(), NOW()),
            ('(Estadual)', 'SC', 'CINCATARINA SC',           'https://www.cincatarina.sc.gov.br/centraldecompras/','CINCATARINA',  'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'SC', 'SIE-SC',                   'https://www.sie.sc.gov.br/licitacoes/',            'SIE-SC',         'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'SP', 'BEC/SP',                   'https://www.bec.sp.gov.br',                        'BEC/SP',         'scraping_html',    'bec_sp',      true, false, NOW(), NOW()),
            ('(Estadual)', 'SP', 'ComprasSP',                'https://compras.sp.gov.br/',                       'ComprasSP',      'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'SE', 'ComprasNet SE',            'https://www.compras.se.gov.br/',                   'ComprasNet SE',  'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('(Estadual)', 'TO', 'Portal Compras TO',        'https://portaldecompras.to.gov.br/',               'SIGA',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            -- ── PNCP (obrigatório nacional) ──────────────────────────────────
            ('(Nacional)',  NULL,'PNCP',                      'https://pncp.gov.br',                              'PNCP',           'api_rest',         'pncp',        true, true,  NOW(), NOW()),
            ('(Nacional)',  NULL,'ComprasNet Federal',        'https://compras.dados.gov.br',                     'SIASG',          'api_rest',         'comprasnet',  true, true,  NOW(), NOW()),
            ('(Nacional)',  NULL,'Licitações-e BB',           'https://www.licitacoes-e.com.br',                  'Licitações-e',   'scraping_html',    'licitacoes_e',true, true,  NOW(), NOW()),
            ('(Nacional)',  NULL,'Licitações-e2 BB',          'https://licitacoes-e2.bb.com.br',                  'Licitações-e2',  'scraping_html',    'licitacoes_e2_bb',true, true,NOW(), NOW()),
            ('(Nacional)',  NULL,'Portal Compras Públicas',   'https://www.portaldecompraspublicas.com.br',       'PCP',            'api_rest',         'portal_compras_publicas',true, false, NOW(), NOW()),
            ('(Nacional)',  NULL,'Compra Aberta',             'https://compraaberta.com.br',                      'Compra Aberta',  'api_rest',         'compra_aberta',true, false,NOW(), NOW()),
            -- ── MUNICÍPIOS SP ────────────────────────────────────────────────
            ('São Paulo',       'SP','Portal Compras SP',     'https://compras.prefeitura.sp.gov.br/',            'eProcurement',   'pncp_passthrough', 'pncp',        true, true,  NOW(), NOW()),
            ('Campinas',        'SP','Portal Licitações Campinas','https://licitacoes.campinas.sp.gov.br/',       'ComprasSP',      'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Santo André',     'SP','e-Compras Santo André', 'http://e-compras.santoandre.sp.gov.br/',           'e-Compras SA',   'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('São Bernardo do Campo','SP','Compras SBC',      'https://compras.saobernardo.sp.gov.br/portal/Mural.aspx','ComprasSBC','scraping_html',   NULL,          true, false, NOW(), NOW()),
            ('São José dos Campos','SP','Licitações SJC',     'https://servicos.sjc.sp.gov.br/sa/licitacoes/index.aspx','SJC',     'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Sorocaba',        'SP','Portal Licitações Sorocaba','https://www.sorocaba.sp.gov.br/servicos/licitacoes/','BNC',     'scraping_html',    'bnc',         true, false, NOW(), NOW()),
            ('Osasco',          'SP','Portal Federal Osasco', 'https://www.gov.br/compras/pt-br',                 'ComprasGov',     'pncp_passthrough', 'pncp',        true, false, NOW(), NOW()),
            ('Guarulhos',       'SP','Portal DCC Guarulhos',  'https://portaldcc.guarulhos.sp.gov.br/',           'DCC',            'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Santos',          'SP','LicitaSantos',          'https://egov.santos.sp.gov.br/licitasantos/',      'LicitaSantos',   'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Ribeirão Preto',  'SP','Licitações Ribeirão Preto','https://www.ribeiraopreto.sp.gov.br/portal/transparencia/pesquisa-de-licitacoes-pmrp','PMRP','scraping_html',NULL,true, false, NOW(), NOW()),
            ('Jundiaí',         'SP','Compra Aberta Jundiaí', 'https://compraaberta.jundiai.sp.gov.br/',          'Compra Aberta',  'scraping_html',    'compra_aberta',true, false,NOW(), NOW()),
            ('Piracicaba',      'SP','Licitações Piracicaba', 'https://www.piracicaba.sp.gov.br/servicos/licitacoes/','Licit@pira', 'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Araçatuba',       'SP','Portal Licitações Araçatuba','https://aracatuba.sp.gov.br/licitacoes',      'AspDigita',      'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Bauru',           'SP','Portal Bauru',          'https://www2.bauru.sp.gov.br/administracao/licitacoes/','HTML',      'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Limeira',         'SP','Portal Licitações Limeira','https://www.limeira.sp.gov.br/licitacoes',      'HTML',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Araraquara',      'SP','Portal Licitações Araraquara','https://www.araraquara.sp.gov.br/transparencia/compras-e-licitacoes/','HTML','scraping_html',NULL,true, false, NOW(), NOW()),
            ('Presidente Prudente','SP','Portal PP',          'https://www.presidenteprudente.sp.gov.br/transparencia/licitacoes/abertas','HTML','scraping_html',NULL, true, false, NOW(), NOW()),
            -- ── MUNICÍPIOS MG ────────────────────────────────────────────────
            ('Belo Horizonte',  'MG','Portal Transparência BH','https://prefeitura.pbh.gov.br/licitacoes/',       'PBH',            'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Uberlândia',      'MG','WebLicitações UDI',     'https://weblicitacoes.uberlandia.mg.gov.br/weblicitacoes/','WebLic','scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Contagem',        'MG','Portal Contagem',       'https://portal.contagem.mg.gov.br/portal/editais/1','HTML',          'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Juiz de Fora',    'MG','SELICON JF',            'https://www.pjf.mg.gov.br/secretarias/selicon/editais/','SELICON',   'scraping_html',    NULL,          true, false, NOW(), NOW()),
            -- ── MUNICÍPIOS SC ────────────────────────────────────────────────
            ('Florianópolis',   'SC','Portal Compras SC',     'https://compras.sc.gov.br/',                       'SIE-SC',         'scraping_html',    'e_lic_sc',    true, false, NOW(), NOW()),
            ('Joinville',       'SC','Licitações Joinville',  'https://www.joinville.sc.gov.br/assunto/administracao-e-governo/licitacoes-e-contratos/','HTML','scraping_html',NULL,true, false, NOW(), NOW()),
            ('Blumenau',        'SC','ComprasBR Blumenau',    'https://comprasbr.com.br/',                        'ComprasBR',      'scraping_html',    NULL,          true, false, NOW(), NOW()),
            -- ── MUNICÍPIOS RJ ────────────────────────────────────────────────
            ('Rio de Janeiro',  'RJ','E-Compras Rio',         'https://compras.rio.rj.gov.br/',                   'e-Compras Rio',  'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Niterói',         'RJ','ION Niterói',           'https://ion.niteroi.rj.gov.br/buscar-licitacoes/', 'ION',            'scraping_html',    NULL,          true, false, NOW(), NOW()),
            -- ── CAPITAIS REGIONAIS ───────────────────────────────────────────
            ('Manaus',          'AM','Portal Compras Manaus', 'https://compras.manaus.am.gov.br/publico/licitacoes.aspx','HTML',    'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Fortaleza',       'CE','Compras Fortaleza',     'https://compras.sepog.fortaleza.ce.gov.br/publico/licitacoes.asp','HTML','scraping_html',NULL,          true, false, NOW(), NOW()),
            ('Brasília',        'DF','Portal Compras DF',     'https://portal.compras.df.gov.br/licitacao',       'ComprasNet',     'pncp_passthrough', 'pncp',        true, true,  NOW(), NOW()),
            ('Goiânia',         'GO','Transparência Goiânia', 'https://www.goiania.go.gov.br/sing_transparencia/licitacoes/','HTML','scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Natal',           'RN','Compras Natal',         'https://compras.natal.rn.gov.br/',                 'HTML',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Porto Alegre',    'RS','Transparência POA',     'https://transparencia.portoalegre.rs.gov.br/licitacoes-contratos/licitacoes','HTML','scraping_html',NULL,true, false, NOW(), NOW()),
            ('Boa Vista',       'RR','Portal SELC',           'https://selc.rr.gov.br/',                          'SELC',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Maceió',          'AL','Portal Licitações Maceió','https://www.licitacao.maceio.al.gov.br/',        'HTML',           'scraping_html',    NULL,          true, false, NOW(), NOW()),
            ('Aracaju',         'SE','Compras Aracaju',       'https://www.aracajucompras.se.gov.br/publico/Processos.aspx','HTML', 'scraping_html',    NULL,          true, false, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """))
