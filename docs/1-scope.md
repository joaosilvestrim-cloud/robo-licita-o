> ⚠️ **Documento HISTÓRICO (2026-04-23) — preservado como registro de PM.**
> Contém imprecisões frente ao código atual: lista ferramentas do Hermes que **não existem** (`analyze_profile`, `extract_data`, `predict_winner`, `check_compliance`...), cita paths antigos (`/root/acrasystem/procurement/`) e "9 tabelas"/"10 routers" (hoje são **12 tabelas** e **14 routers**, **12 fontes**).
> Para a verdade atual, consulte [`../README.md`](../README.md), [`2-data-sources.md`](2-data-sources.md), [`3-data-model.md`](3-data-model.md), [`4-api-reference.md`](4-api-reference.md) e [`5-operations.md`](5-operations.md).

# Fase 1 — PM/Scope: Licita — Procurement/Licitações Internas

**Data:** 2026-04-23  
**Status:** ✅ Documentado e Operacional  
**Domain:** licita.nanuck.com.br

---

## Contexto do Negócio

**Licita** é uma plataforma SaaS para **empresas que vendem ao setor público brasileiro**. Monitora, filtra e prioriza licitações do **PNCP em tempo real**, com mapa de calor, alertas personalizados e assistente IA.

É **complementar** a **Saas Licitações** (monitoramento geral) — esta é focada em **procurement interno** (compras de pessoas jurídicas).

### Proposta de Valor

| Dor | Como Licita resolve |
|-----|-------------------|
| "Perco licitações porque descubro tarde" | Sync 6x/dia + alerta automático por perfil |
| "Não encontro oportunidades fora do meu estado" | Mapa de calor Brasil → cidade |
| "Os portais são confusos" | Interface unificada + filtros + score de relevância |
| "Meu time esquece de revisar" | Email + widget chat + badge + ações em massa |
| "Tenho várias empresas do grupo" | Multi-CNPJ em 1 conta + Cartão CNPJ Receita Federal |
| "Queria IA que entenda meu ramo" | Hermes Licita: CNAE → keywords, cria perfis, explica modalidades |

### Diferenciais Competitivos

- ✅ Dados **oficiais + tempo real** (PNCP, não scraping)
- ✅ **Full-text search** em editais
- ✅ **Cleanup automático** de licitações vencidas
- ✅ **Granularidade por cidade** (fundamental para prefeituras)
- ✅ **Agente IA** que conhece Lei 14.133/2021

---

## Stack Técnico

| Camada | Tech | Status |
|--------|------|--------|
| **Backend** | FastAPI (Python 3.12) + SQLModel + asyncpg + APScheduler | ✅ Healthy |
| **Frontend** | Next.js 15 + React 19 + Tailwind CSS | ✅ Up |
| **Banco** | PostgreSQL 16 | ✅ OK (9 tabelas) |
| **IA** | LiteLLM → Groq (`llama-3.3-70b-versatile`) | ✅ Healthy |
| **Ingress** | Traefik + Cloudflare (DNS challenge, SSL wildcard) | ✅ Healthy |
| **Deploy** | Docker Compose | ✅ 5 serviços |

---

## Arquitetura Atual

### Backend (FastAPI)

**Localização:** `/root/acrasystem/procurement/backend/app/`

**Estrutura:**
```
app/
├── main.py              # FastAPI app + lifespan, middleware
├── auth.py              # JWT validation
├── config.py            # Settings (env vars)
├── database.py          # SQLAlchemy AsyncSessionLocal
├── api/                 # Routers (10 módulos)
│   ├── auth.py          # Signup (CNPJ lookup) + SSO
│   ├── bids.py          # GET /bids?filters... + full-text search
│   ├── profiles.py      # CRUD perfis de busca (keywords, estados, ramos)
│   ├── alerts.py        # CRUD alertas + score 0-1
│   ├── tracking.py      # Participei/ganhei/perdi
│   ├── dashboard.py     # KPIs + home
│   ├── cnpj.py          # Busca Receita Federal (Cartão CNPJ)
│   ├── companies.py     # Multi-CNPJ (tenant_companies)
│   ├── sync.py          # Trigger manual sync
│   └── chat.py          # Chat com Hermes Licita
├── db/
│   └── models.py        # SQLModel: 9 tabelas
├── services/            # Business logic
│   ├── pncp.py          # Fetch PNCP API
│   ├── pncp_search.py   # Full-text search editais
│   ├── alerts.py        # Match bids vs profiles
│   ├── cleanup.py       # Remove licitações vencidas
│   └── geo_cache.py     # Cache de localidades Brasil
├── cron/
│   └── jobs.py          # APScheduler jobs
└── migrations/          # Alembic
```

**Key Features:**
- ✅ APScheduler com 6+ jobs de sync
- ✅ Full-text search em editais (PostgreSQL)
- ✅ Multi-CNPJ support (tenant_companies table)
- ✅ Score matching (0-1) entre bids e profiles
- ✅ Health endpoint: `/health`
- ✅ Rate limiting via Traefik

**Health Status:** `curl http://procurement-backend/health`
```
[Logs] GET /health HTTP/1.1 200 OK
[Cron] processando alertas — 0 alertas gerados (nenhum perfil ativo)
```

### Frontend (Next.js 15)

**Localização:** `/root/acrasystem/procurement/frontend/`

**Stack:**
- Next.js 15 (App Router)
- React 19
- Tailwind CSS 3.4
- react-simple-maps (SVG heatmap Brasil)
- Recharts (charts)
- SWR (data fetching)

**App Structure:**
```
app/
├── login/               # Signup com CNPJ lookup
├── forgot-password/ + reset-password/
└── dashboard/
    ├── page.tsx         # KPIs, busca keyword PNCP
    ├── bids/
    │   ├── page.tsx     # Tabela + mapa + drawer
    │   ├── [id]/
    │   │   └── page.tsx # Íntegra do edital
    │   └── components/  # BidDrawer
    ├── alerts/          # Lista com ações em massa
    ├── profiles/        # CRUD com "testar regras"
    ├── tracking/        # Participei/ganhei/perdi
    ├── reports/         # KPIs históricos
    └── company/         # Cartão CNPJ + multi-CNPJ
```

### Database (PostgreSQL 16)

**Tabelas (9 total):**

1. `proc_tenants` — Empresas cadastradas (multi-tenant, plano free/pro/enterprise)
2. `proc_users` — Usuários vinculados a tenant
3. `tenant_companies` — CNPJs adicionais (Cartão CNPJ: razão social, CNAEs, QSA JSON, endereço)
4. `public_bids` — Licitações PNCP (28 campos: status, modalidade, esfera, valores, datas, requisitos)
5. `procurement_profiles` — Perfis de busca (keywords, estados, ramos, limites valor, flags)
6. `procurement_alerts` — Matches (bid_id, profile_id, score 0-1)
7. `bid_tracking` — Acompanhamento (participei/ganhei/perdi)
8. `scrape_logs` — Histórico de sincronizações PNCP
9. `proc_chat_messages` — Histórico chat com Hermes Licita

### Integrações Externas

#### PNCP (Portal Nacional de Contratações Públicas)

| Endpoint | Uso | Frequência |
|----------|-----|-----------|
| `GET /api/consulta/v1/contratacoes/publicacao` | Sync por data (9 modalidades) | a cada 6h |
| `GET /api/search?q=...&tipos_documento=edital` | Full-text search keywords | a cada 12h |

#### Receita Federal (CNPJ Lookup)

**Endpoint:** `https://mre.ms.gov.br/api/cnpj` ou similar  
**Uso:** Cartão CNPJ (razão social, CNAEs, QSA, endereço)  
**Cache:** 30 dias (atualizado anualmente)

### Hermes Licita (FastAPI, porta 8004)

**Função:** Subagente IA especializado em compras públicas

**Ferramentas (8x function-calling):**
1. `suggest_keywords` — baseado em CNAE do tenant
2. `explain_modality` — descreve Pregão, Concorrência, Tomada Preço, etc.
3. `analyze_profile` — analisa contrapartidas, riscos de um perfil
4. `extract_data` — OCR + estruturação de dados do edital
5. `calculate_score` — score de relevância (0-1) customizado
6. `predict_winner` — heurística baseada em histórico
7. `suggest_keywords_by_history` — aprende do comportamento do tenant
8. `check_compliance` — valida conformidade Lei 14.133/2021

---

## Fluxo de Dados (Ciclo de Vida de Licitação)

```
1. Signup + CNPJ
   └─ User entra email/senha + CNPJ
   └─ Lookup Receita Federal → razão social, CNAE, QSA
   └─ CREATE proc_tenants (plano=free)
   └─ CREATE proc_user + JWT

2. Sync Jobs (6x/dia + 12h para search)
   └─ GET PNCP /api/consulta/v1/contratacoes/publicacao (9 modalidades)
   └─ INSERT public_bids (ou UPDATE se já existe)
   └─ Full-text index atualizado
   └─ Logs: scrape_logs

3. Profile Creation
   └─ User cria perfil: keywords="Python", estado="SP", ramo="CNAE 3312", valor_min=50000
   └─ CREATE procurement_profiles

4. Alert Matching (a cada 1h)
   └─ SELECT * FROM public_bids (recentes, não deletadas)
   └─ Para cada profile: calcular score vs cada bid
   └─ INSERT procurement_alerts (score > threshold, ex: 0.7)
   └─ Enqueue email

5. User Discovery
   └─ GET /api/bids?profile_id=X (retorna alerts ordenados por score)
   └─ Frontend: tabela + mapa de calor (geo_cache)
   └─ Click em bid → drawer com edital completo
   └─ Full-text search em editais

6. Tracking (Opcional)
   └─ User marca: "participei", "ganhei", "perdi"
   └─ INSERT bid_tracking
   └─ Usado para reports históricos + Hermes learning

7. Cleanup (diária, 02:00 UTC)
   └─ SELECT * FROM public_bids WHERE data_fim < NOW()
   └─ Soft delete (is_deleted = true)
   └─ Libera espaço para novos bids
```

---

## Métricas de Saúde (2026-04-23)

| Component | Status | Logs | Notas |
|-----------|--------|------|-------|
| Backend | ✅ Healthy | `GET /health` 200 OK | Alert processing: 0 alertas (nenhum perfil) |
| Frontend | ✅ Up | Container running | Next.js 15 renderizando |
| Database | ✅ OK | No errors | 9 tabelas, índices full-text |
| Hermes Licita | ✅ Healthy | Container up | Pronto para function-calling |
| Traefik/Nginx | ✅ OK | Proxy routing | SSL via Cloudflare DNS challenge |

---

## Conformidade & Segurança

### LGPD (Lei Geral de Proteção de Dados)

- ✅ Autenticação obrigatória (JWT)
- ✅ Multi-tenant isolation (proc_tenants.id filtrando todas queries)
- ⚠️ **TODO:** Direito ao esquecimento (soft delete → hard delete)
- ⚠️ **TODO:** Consentimento explícito (TCLE, cookie banner)
- ⚠️ **TODO:** Exportação de dados (relatório JSON)

### Lei 14.133/2021 (Licitações Públicas)

- ✅ Suporte a 9 modalidades (Hermes explica cada uma)
- ⚠️ **TODO:** Validação de datas de edital (prazo mínimo)
- ⚠️ **TODO:** Alertas de itens proibidos (lei de discriminação)

### Segurança

- ✅ JWT signed + rate limiting (Traefik)
- ✅ CORS validado
- ✅ SQL injection prevenido (SQLModel ORM)
- ⚠️ **TODO:** Auditoria (quem acessou qual bid, quando)
- ⚠️ **TODO:** Criptografia de dados sensíveis (CNPJs)
- ⚠️ **TODO:** 2FA opcional

### WCAG 2.1 (A11y)

- ⚠️ **TODO:** Auditoria completa
- ⚠️ **TODO:** Dark mode acessível
- ⚠️ **TODO:** Keyboard navigation no mapa

---

## Roadmap & Gaps (Phase 2+)

### Curto Prazo (Sprint 1-2)
- [ ] Fase 2: Competitive Analysis (Serenata, Tcunet, Portal Compras)
- [ ] Fase 3: Compliance (LGPD, Lei 14.133, WCAG)
- [ ] Fase 4: Architecture (cache, CDN, monitoring)
- [ ] Fase 5: Design System (dark/light, tokens)

### Médio Prazo
- [ ] Testes E2E (Playwright) — signup, criar perfil, search, tracking
- [ ] Testes unitários (>80% coverage)
- [ ] Otimização de queries (EXPLAIN ANALYZE)
- [ ] Webhook outbound (Slack, Teams, n8n)
- [ ] Integração com ERPs (automação de resposta)

### Longo Prazo
- [ ] Mobile app (React Native)
- [ ] Integração Office (sidepanel Licita)
- [ ] RPA — preencher formulários de edital automaticamente
- [ ] ML — previsão de ganho baseada em histórico
- [ ] Integração NF-e (validação de contratação)

---

## Entregáveis Esperados (Próximas Fases)

| Fase | Artefato | Responsável | Prazo |
|------|----------|-------------|-------|
| 2 | `2-competitive-analysis.md` | Sonnet | Sprint 1 |
| 3 | `3-compliance-checklist.md` | Compliance | Sprint 1 |
| 4 | `4-architecture.md` | Solutions Architect | Sprint 2 |
| 5 | `5-design-system.md` | UX Designer | Sprint 2 |
| 6 | `6-api-spec.md` | Backend Dev | Sprint 3 |
| 7 | `7-component-library.md` | Frontend Dev | Sprint 3 |
| 8 | `8-deployment-guide.md` | DevOps | Sprint 4 |
| 9 | `9-full-docs.md` | Tech Writer | Sprint 4 |

---

## Conclusão

**Licita** está **operacional**. Backend healthy, jobs rodando (0 alertas = nenhum perfil criado ainda), Hermes pronto, BD estruturado. Próximo: análise competitiva + compliance com Lei 14.133.

---

**Documentado por:** PM/Scope Agent  
**Data:** 2026-04-23T13:50:00Z
