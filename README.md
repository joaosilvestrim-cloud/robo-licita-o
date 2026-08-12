# Licita — SaaS de Licitações Públicas

> Plataforma SaaS para empresas que **vendem ao setor público brasileiro**. Monitora, filtra e prioriza licitações de **12 fontes oficiais** (PNCP, ComprasNet, Licitações-e, Querido Diário, portais estaduais e municipais) em tempo real, com mapa de calor, alertas por perfil e assistente IA (Hermes Licita).

**Produção:** [licita.nanuck.com.br](https://licita.nanuck.com.br) — deploy rodando a partir de `/root/products/saas-licitacoes/`.
**Repo:** extraído do monorepo `nanuck-platform` (preserva o commit inicial).

> ⚠️ **CRÍTICO — preservação de dados:** sempre opere este Compose com **`-p procurement`** (nome do projeto). O volume do banco é prefixado pelo nome do projeto → `procurement_procurement_postgres`. Se você rodar sem `-p` (o default viraria `saas-licitacoes`), **um volume vazio novo seria criado e o app subiria com banco em branco**. Mantenha `-p procurement` em todo `docker compose`.

---

## Sumário

- [Proposta de valor](#proposta-de-valor)
- [Stack](#stack)
- [Arquitetura](#arquitetura)
- [Fontes de dados (12 scrapers)](#fontes-de-dados)
- [Modelo de dados (12 tabelas)](#modelo-de-dados)
- [API (14 routers)](#api)
- [Jobs / APScheduler](#jobs--apscheduler)
- [Hermes Licita (agente IA)](#hermes-licita-agente-ia)
- [Multi-tenant, RBAC e SSO](#multi-tenant-rbac-e-sso)
- [Frontend](#frontend)
- [Deploy](#deploy)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Operações (migrations, sync manual, logs)](#operações)
- [Estado real dos scrapers e issues conhecidas](#estado-real-e-issues-conhecidas)
- [Roadmap](#roadmap)

---

## Proposta de valor

| Dor da empresa | Como a Licita resolve |
|---|---|
| "Perco licitações porque descubro tarde" | Sync automático (PNCP a cada 6h, outras fontes a cada 8h) + alerta por perfil |
| "Não encontro oportunidades fora do meu estado" | Mapa de calor interativo Brasil → cidade (centroides IBGE computados em backend) |
| "Os portais são confusos e lentos" | Interface unificada, 12 fontes numa só tabela, filtros e ordenação |
| "Meu time esquece de revisar alertas" | Chat widget + badge no menu + ações em massa (marcar visto / descartar / favoritar) |
| "Tenho várias empresas do grupo" | Multi-CNPJ em uma conta, com Cartão CNPJ completo da Receita (BrasilAPI) |
| "Queria uma IA que entendesse meu ramo" | Hermes Licita sugere palavras-chave por CNAE, cria perfis, explica modalidades da Lei 14.133/2021 |

**Diferenciais:**
- Dados **oficiais** (PNCP/SIASG/diários oficiais), não scraping de portais privados
- **Full-text search** nos editais via endpoint de busca do PNCP
- **Cleanup automático** de licitações vencidas (preserva favoritos)
- **Granularidade por cidade** — mapa drill-down estado → município
- **Score de relevância (0–1)** por perfil, com motivos explicados

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | **FastAPI** (Python 3.12) + SQLModel + asyncpg + APScheduler — porta `8003` |
| Frontend | **Next.js 15** (App Router) + React 19 + Tailwind + react-simple-maps + Recharts — porta `3000` |
| Banco | **PostgreSQL 16** (DB `acraprocurement`) |
| IA | subagente `hermes-procurement` (FastAPI, porta `8004`) → orquestrador LiteLLM (`hermes:4000`) → Groq `llama-3.3-70b-versatile` |
| Ingress | Traefik + Cloudflare DNS challenge (SSL wildcard `*.nanuck.com.br`) |
| Deploy | Docker Compose (5 serviços) |

---

## Arquitetura

```
saas-licitacoes/
├── backend/                     # FastAPI :8003
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # app + lifespan (registra 14 routers + 14 jobs)
│       ├── config.py            # Settings (pydantic-settings, lê .env)
│       ├── auth.py              # JWT: get_current_user / require_admin / require_full_or_admin
│       ├── database.py          # AsyncSessionLocal + init_db (create_all)
│       ├── api/                 # 14 routers (ver #API)
│       ├── db/models.py         # SQLModel — 12 tabelas + enums
│       ├── services/            # 12 scrapers + alerts/cleanup/geo_cache/source_tracker/base_portal
│       └── cron/jobs.py         # wrappers chamados pelo APScheduler
├── frontend/                    # Next.js 15 :3000
│   ├── Dockerfile               # multi-stage + stage pkgpatch (corrige npm node:22-alpine)
│   └── app/
│       ├── login/ forgot-password/ reset-password/
│       ├── dashboard/
│       │   ├── page.tsx         # KPIs + busca ad-hoc no PNCP
│       │   ├── bids/            # tabela + BrazilMap + [id]/íntegra
│       │   ├── alerts/ profiles/ tracking/ reports/ sources/ company/
│       │   └── layout.tsx
│       └── components/          # BidDrawer, ChatWidget
├── hermes-procurement/          # FastAPI :8004 — agente IA (8 tools)
│   ├── Dockerfile
│   └── main.py
├── nginx.conf                   # proxy interno /api→backend, /→frontend
├── docker-compose.yml           # 5 serviços + 3 redes
├── .env.example
└── docs/                        # documentação estendida
```

**Fluxo de tráfego:**
```
Internet → Cloudflare → Traefik (Host licita.nanuck.com.br, TLS Cloudflare)
        → procurement-nginx :80
            ├─ /api/* , /docs , /openapi.json  → procurement-backend :8003
            └─ /                                  → procurement-frontend :3000
procurement-backend :8003 → hermes-procurement :8004 → hermes :4000 (LiteLLM) → Groq
procurement-backend → fontes públicas (PNCP, ComprasNet, BrasilAPI, IBGE, ...)
```

---

## Fontes de dados

A plataforma agrega **12 fontes** oficiais. Todos os scrapers gravam na tabela `public_bids` com chave de dedup `(source, external_id)`, registram `scrape_logs` e atualizam `data_sources` via `source_tracker`. **Nenhum scraper usa auth/API key** — todos consomem endpoints públicos. Detalhe completo em [`docs/2-data-sources.md`](docs/2-data-sources.md).

| source key | Fonte | Esfera | Cobertura | Status |
|---|---|---|---|---|
| `pncp` | PNCP — Portal Nacional de Contratações Públicas | todas | nacional (9 modalidades) | ✅ working |
| `pncp` (search) | PNCP full-text (`/api/search`) | todas | nacional por keyword | ✅ working |
| `comprasnet` | ComprasNet/SIASG (federal, Lei 8.666 legado) | federal | nacional | ✅ working |
| `licitacoes_e` | Licitações-e (Banco do Brasil) | municipal | nacional | ⚠️ working (modalidade fixa `pregao`) |
| `licitacoes_e2_bb` | Licitações-e v2 (interface estática BB) | municipal | nacional | ⚠️ working (modalidade fixa `pregao`) |
| `dou` | Querido Diário (OKBR) — diários oficiais | municipal | 17 cidades SP | ✅ working |
| `comprasnet_ba` | ComprasNet Bahia | estadual | BA | ✅ working |
| `e_lic_sc` | e-lic SC (Santa Catarina) | estadual | SC | ⚠️ working (modalidade fixa `pregao`) |
| `celic_rs` | CELIC RS (Central de Licitações do RS) | estadual | RS | ⚠️ bug `dtAbertura` duplicado |
| `portal_compras_publicas` | Portal de Compras Públicas | municipal | nacional | ⚠️ speculative (3 endpoints guess) |
| `compra_aberta` | Compra Aberta | municipal | SP/Sul | ⚠️ speculative |
| `bnc` | BNC — Banco Nacional de Compras | municipal | SP/Sul | ⚠️ speculative |
| `bec_sp` | BEC/SP — Bolsa Eletrônica de Compras (SP) | estadual | SP | ❌ stub (endpoint SOAP descontinuado) |

> Os scrapers que seguem `BasePortalScraper` (`bnc`, `celic_rs`, `compra_aberta`, `comprasnet_ba`, `e_lic_sc`, `portal_compras_publicas`) implementam `fetch_bids()` + `sync()` herdado. PNCP, ComprasNet federal, Licitações-e, Querido Diário e BEC/SP são funções módulo-free.

---

## Modelo de dados

12 tabelas em PostgreSQL (SQLModel → `create_all()`). Esquema detalhado em [`docs/3-data-model.md`](docs/3-data-model.md).

| Tabela | Descrição |
|---|---|
| `proc_tenants` | Empresas (multi-tenant). Dados Receita + `plan` (free/pro/enterprise) |
| `proc_users` | Usuários por tenant, com `role` (admin/full/simple) |
| `tenant_companies` | CNPJs adicionais do tenant (Cartão CNPJ completo: CNAEs, QSA JSON, endereço) |
| `public_bids` | Licitações (28+ campos). **Chave dedup `(source, external_id)`** |
| `procurement_profiles` | Perfis de busca por usuário (keywords, estados, ramos, faixas de valor, flags) |
| `procurement_alerts` | Matches bid×profile com `match_score` 0–1 e `match_reasons` (JSON) |
| `bid_tracking` | Acompanhamento (participei/ganhei/perdi, valores propostos/contratados) |
| `bid_interactions` | Favorito/visto/descartado/notas **por usuário** (distinto do tracking) |
| `scrape_logs` | Histórico de cada sincronização (found/inserted/updated, status, erro) |
| `data_sources` | Registro informativo das fontes + último sync |
| `municipal_portals` | Catálogo de portais municipais (URL, tipo, scraper_key) — global, sem tenant |
| `proc_chat_messages` | Histórico do chat com Hermes Licita |

**Enums:** `BidSphere`, `BidStatus`, `BidModality`, `ObjectType`, `AlertStatus`, `ScrapeStatus`, `PortalType`, `UserRole`, `TenantType`.

---

## API

14 routers, prefixo `/api/*`. Endpoints públicos (sem JWT): `POST /api/auth/{register,login,sso,forgot-password,reset-password}` e `GET /api/cnpj/{digits}`. **Todos os demais exigem JWT** (`OAuth2PasswordBearer`, bcrypt + python-jose). Referência completa em [`docs/4-api-reference.md`](docs/4-api-reference.md).

| Router | Prefix | Resumo |
|---|---|---|
| `auth` | `/api/auth` | registro com CNPJ lookup, login OAuth2, SSO, forgot/reset password, `/me`, `/me/tenant` |
| `bids` | `/api/bids` | lista filtrada/paginada, `/search`, `/geo` (mapa estado), `/geo/cities`, `/stats`, `/{id}` |
| `profiles` | `/api/profiles` | CRUD de perfis + `/{id}/test` (dry-run do scorer) |
| `alerts` | `/api/alerts` | lista, summary, `mark-viewed`/`favorite`/`discard`, bulk actions |
| `tracking` | `/api/tracking` | acompanhar bid, registrar proposta/resultado |
| `interactions` | `/api/interactions` | favorito/visto/descartado/notas por usuário + visão empresa |
| `companies` | `/api/companies` | multi-CNPJ (BrasilAPI), `import-from-tenant`, `set-primary` |
| `cnpj` | `/api/cnpj/{digits}` | lookup público na BrasilAPI (razão, CNAEs, QSA, endereço) |
| `dashboard` | `/api/dashboard` | KPIs agregados do tenant |
| `sync` | `/api/sync` | sync manual: `/`, `/keyword`, `/keywords/profiles`, `/all`, `/{source}`, `/status` |
| `sources` | `/api/sources` | lista fontes com último status de sync |
| `portals` | `/api/portals` | CRUD do catálogo de portais municipais (+ `/stats`) |
| `users` | `/api/users` | gerenciar usuários do tenant (admin) |
| `chat` | `/api/chat` | proxy para Hermes Licita + histórico |

> Paginação padrão: `page=1`, `limit=20` (bids/alerts/interactions/tracking); `limit=50` (portals, chat). Resposta: `{total, page, limit, pages, data}`.

---

## Jobs / APScheduler

Registrados no `lifespan` de `backend/app/main.py`:

| Job | Agenda | Ação |
|---|---|---|
| `pncp_sync` | a cada 6h | `sync_pncp(days_back=7)` — 9 modalidades |
| `comprasnet_sync` | a cada 8h | ComprasNet federal |
| `bec_sp_sync` | a cada 8h | loga "pulando — endpoint descontinuado" |
| `licitacoes_e_sync` | a cada 8h | Licitações-e (BB) |
| `querido_diario_sync` | a cada 12h | DOU (17 cidades SP) |
| `portal_compras_publicas_sync` | a cada 8h | Portal de Compras Públicas |
| `e_lic_sc_sync` | a cada 8h | e-lic SC |
| `celic_rs_sync` | a cada 8h | CELIC RS |
| `comprasnet_ba_sync` | a cada 8h | ComprasNet BA |
| `compra_aberta_sync` | a cada 8h | Compra Aberta |
| `bnc_sync` | a cada 8h | BNC |
| `keyword_sync` | a cada 12h | `sync_all_profile_keywords` — busca cada keyword/ramo dos perfis ativos no PNCP |
| `alert_processing` | a cada 1h | gera alertas bid×profile (score ≥ 0.5) |
| `close_expired_bids` | diário 01:00 | marca `encerrada` quem passou do prazo |
| cleanup (logo após) | diário 01:00 | remove alertas de bids vencidas (preserva favoritos) |
| `daily_briefing` (Hermes) | diário 08:00 | resumo do dia (hoje só loga) |

---

## Hermes Licita (agente IA)

Container `hermes-procurement` (:8004). Loop agentic (até 6 iterações) com `tool_choice=auto`. Se o orquestrador LiteLLM falhar, retorna mensagem amigável com atalhos manuais (busca PNCP, mapa, perfis).

**8 ferramentas function-calling** (definidas em `hermes-procurement/main.py`):

| Ferramenta | O que faz |
|---|---|
| `search_bids` | busca licitações com filtros (q, sphere, state, city, status, min/max_value) |
| `get_bid_detail` | detalhe de uma licitação por id |
| `get_dashboard` | KPIs do tenant |
| `list_alerts` | alertas por status |
| `trigger_keyword_sync` | dispara `POST /api/sync/keyword` |
| `create_profile` | cria perfil de monitoramento |
| `explain_modality` | explica modalidade (conhecimento local, Lei 14.133/2021) |
| `suggest_keywords` | sugere keywords a partir do CNAE (mapa setorial embutido) |

> As ferramentas chamam a API Procurement repassando o `user_token` (JWT) do usuário — assim respeitam o tenant. Modalidades explicadas localmente: pregão, concorrência, tomada de preços, convite, dispensa, inexigibilidade, diálogo competitivo, leilão.

---

## Multi-tenant, RBAC e SSO

- **Multi-tenant:** toda query de dados do tenant filtra por `tenant_id == user.tenant_id`. Exceção: `municipal_portals` é um catálogo **global** (sem isolamento por tenant).
- **RBAC** (`UserRole`):
  - `admin` — gerencia usuários, vê tudo do tenant
  - `full` — vê tudo do tenant, não gerencia usuários
  - `simple` — vê apenas seus próprios perfis/interações
- **SSO:** `POST /api/auth/sso` valida um JWT externo com `SSO_KEY=acra-sso-2024` (compartilhado com Office/Finance). O usuário precisa pré-existir.
- **Reset de senha:** tokens em memória (`_reset_tokens`, 30 min) — **não é HA** (perde a cada restart; ver issues conhecidas).

---

## Frontend

Next.js 15 (App Router) + React 19 + Tailwind. Sem SSR de dados (tudo client-side via fetch ao `/api/*`).

**Páginas:**
- `/login` — signup com lookup CNPJ (BrasilAPI) + login
- `/forgot-password`, `/reset-password`
- `/dashboard` — KPIs + campo "Buscar no PNCP"
- `/dashboard/bids` — tabela 12+ filtros + ** mapa de calor** (BrazilMap com `react-simple-maps`) + `<BidDrawer>`
- `/dashboard/bids/[id]` — íntegra do edital (dados ao vivo do PNCP)
- `/dashboard/alerts` — lista com ações em massa
- `/dashboard/profiles` — CRUD + "testar regras" (dry-run do scorer)
- `/dashboard/tracking` — participei/ganhei/perdi
- `/dashboard/reports` — KPIs históricos
- `/dashboard/company` — Cartão CNPJ + multi-CNPJ
- `/dashboard/sources` — status das 12 fontes
- `<ChatWidget>` flutuante → Hermes Licita

---

## Deploy

### Serviços (`docker-compose.yml`)

| Serviço | Imagem/Build | Notas |
|---|---|---|
| `postgres` | `postgres-16-alpine-patched` (build de `/opt/dockerfiles/postgres-alpine`) | DB `acraprocurement`, TZ SP |
| `backend` | `./backend` (FastAPI :8003) | healthcheck `/health`, redes `procurement_net` + `acra_shared` |
| `frontend` | `./frontend` (Next :3000) | **hardened**: `read_only`, tmpfs `/tmp`+`/.next/cache`, `cap_drop: ALL`, `no-new-privileges` |
| `nginx` | `nginx:alpine` | proxy interno; labels Traefik |
| `hermes-procurement` | `./hermes-procurement` (:8004) | depede de `backend` healthy |

**Redes:** `procurement_net` (bridge interna), `acra_shared` (externa — SSO com Office), `proxy` (externa — Traefik).

**Labels Traefik (no `nginx`):**
```yaml
- traefik.enable=true
- traefik.docker.network=proxy
- traefik.http.routers.procurement.entrypoints=https
- traefik.http.routers.procurement.rule=Host(`licita.nanuck.com.br`)
- traefik.http.routers.procurement.tls.certresolver=cloudflare
- traefik.http.services.procurement.loadbalancer.server.port=80
```

### Rodar / subir

> Sempre passe `-p procurement` (ver aviso crítico no topo). O `.env` precisa estar presente (não versionado — copie de `/root/platform/procurement/.env` ou regenere via Bitwarden).

```bash
cp .env.example .env   # edite os secrets (ou copie o .env de produção existente)
docker compose -p procurement up -d --build
```

> O build do `postgres` depende do context `/opt/dockerfiles/postgres-alpine` (presente no VPS Nanuck). Em outro host, troque por `image: postgres:16-alpine` e remova o bloco `build`.

> Histórico: este projeto antes rodava de `/root/platform/procurement` (ainda preservado como backup). O cutover foi feito mantendo o nome do projeto (`-p procurement`) para reutilizar o volume e as redes — **sem perda de dados**.

---

## Variáveis de ambiente

Ver `.env.example`. Principais:

| Var | Default | Descrição |
|---|---|---|
| `POSTGRES_PASSWORD` | `procurement-secret-2024` | senha do role `procurement` |
| `SECRET_KEY` | `procurement-jwt-secret` | assinatura JWT do backend |
| `SSO_KEY` | `acra-sso-2024` | chave SSO compartilhada com Office/Finance |
| `OFFICE_API_URL` | `http://acra-backend:8000` | API do Office (control plane) |
| `HERMES_URL` | `http://hermes:4000` | orquestrador LiteLLM |
| `LITELLM_MASTER_KEY` | — | auth no orquestrador |
| `PROC_API_TOKEN` | vazio | JWT de serviço p/ Hermes chamar a API (gerar via `/api/auth/login`) |
| `HERMES_PROCUREMENT_URL` | `http://hermes-procurement:8004` | usado pelo backend (`/api/chat`) |
| `SMTP_*` | — | email (forgot-password, alertas). Se vazio, o link de reset **volta no JSON** (dev only) |
| `FRONTEND_URL` | `http://localhost:3003` | usado em links de email |
| `PNCP_SYNC_INTERVAL_HOURS` | `6` | lido mas o agendamento real é fixo no `main.py` |

---

## Operações

### Migrations

SQLModel usa `create_all()` (só cria tabelas novas; **não altera**). Mudanças de schema exigem `ALTER TABLE` manual:

```bash
docker exec procurement-postgres psql -U procurement -d acraprocurement -c "
  ALTER TABLE proc_tenants ADD COLUMN IF NOT EXISTS razao_social VARCHAR;
"
```

### Sync manual

```bash
# full (PNCP + keywords + alertas)
curl -X POST -H "Authorization: Bearer $TOKEN" "https://licita.nanuck.com.br/api/sync?days_back=3"
# uma fonte
curl -X POST -H "Authorization: Bearer $TOKEN" "https://licita.nanuck.com.br/api/sync/comprasnet?days_back=7"
# status dos últimos 20 logs
curl -H "Authorization: Bearer $TOKEN" "https://licita.nanuck.com.br/api/sync/status"
```

Fontes válidas em `/api/sync/{source}`: `pncp, comprasnet, bec_sp, licitacoes_e, licitacoes_e2_bb, dou, portal_compras_publicas, e_lic_sc, celic_rs, comprasnet_ba, compra_aberta, bnc, alerts, keywords`.

### Healthchecks

- Backend: `GET /health` → `{"status":"ok"}`
- Hermes: `GET /health` (na porta 8004 interna)
- Postgres: `pg_isready`
- Nginx: `wget --spider http://127.0.0.1/`
- Docs OpenAPI: `GET /docs` e `GET /openapi.json`

---

## Estado real e issues conhecidas

Documentado para futuros mantenedores (detalhe em [`docs/4-operations.md`](docs/4-operations.md#issues-conhecidas)):

- ❌ `bec_sp` é **stub** — endpoint SOAP descontinuado; precisa de Playwright ou migração para PNCP.
- ⚠️ `celic_rs` tem bug de chave duplicada no dict de params (`dtAbertura` sobrescrito → consulta só 1 dia).
- ⚠️ `bnc`, `compra_aberta`, `portal_compras_publicas` são **speculativos** — tentam 3 endpoints cada, não validados contra API real; podem retornar vazio silenciosamente.
- ⚠️ `e_lic_sc`, `licitacoes_e`, `licitacoes_e2_bb` fixam `modality=pregao` (não detectam a real).
- ⚠️ `querido_diario` grava `source="dou"` (não bate com o nome do arquivo); 17 cidades SP hardcoded; `days_back` ignorado (latência do QD).
- ⚠️ Reset de senha usa `_reset_tokens` em **memória** (perde a cada restart; sem HA).
- ⚠️ `municipal_portals` **sem isolamento por tenant** (catálogo global editável por qualquer autenticado).
- ⚠️ `profiles DELETE` é soft (`active=False`) mas GET só lista ativos → perfil "excluído" fica invisível/irrecuperável pela API.
- ⚠️ `sync.py /{source}` retorna **HTTP 200** com `{error:...}` para fonte desconhecida (cliente deve checar body).
- ⚠️ `chat.py` persiste uma mensagem falsa "dificuldades técnicas" no histórico quando Hermes falha.
- ⚠️ Unicidade de `public_bids (source, external_id)` garantida só em migration; ORM faz select-then-upsert (condição de corrida possível).
- ⚠️ CORS do backend com `allow_origins=["*"]` (o frontend é protegido pelo nginx/Traefik, mas convém restringir).
- ⚠️ `httpx ... verify=False` em vários scrapers (TLS desabilitado).
- ⚠️ `forgot-password` retorna o link de reset no JSON quando SMTP não configurado (risco de vazar em prod se `smtp_user` ficar vazio).

---

## Roadmap

- [ ] Corrigir bugs (celic_rs, modality fixa, scrapers especulativos)
- [ ] Webhook de alertas (Telegram/Slack/n8n) — `daily_briefing` já produz o conteúdo
- [ ] Mover reset-tokens para DB (HA) + 2FA opcional
- [ ] Exportação de relatórios PDF/Excel
- [ ] Isolamento por tenant em `municipal_portals` (ou torná-lo admin-only)
- [ ] Predição de probabilidade de vitória por perfil (usando `bid_tracking`)
- [ ] Restringir CORS, habilitar `verify=True` onde possível
- [ ] Alembic no lugar de `create_all` + ALTER manual
- [ ] Testes (unit + E2E Playwright: signup → perfil → busca → tracking)

---

## Licença

Proprietário — Acrasystem / Nanuck.
