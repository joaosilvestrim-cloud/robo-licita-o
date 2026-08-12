# AGENTS.md — saas-licitacoes (Licita)

SaaS de **monitoramento de licitações públicas brasileiras** para empresas que vendem ao governo. Agrega 12 fontes oficiais (PNCP, ComprasNet, Licitações-e, Querido Diário, portais estaduais/municipais) com mapa de calor, alertas por perfil e assistente IA (Hermes Licita).

- **Produção:** https://licita.nanuck.com.br — deploy roda **deste repo** em `/root/products/saas-licitacoes/`.
- **Path antigo** `/root/platform/procurement` está preservado como backup (não usar).

## Stack

- **Backend:** FastAPI (Python 3.12) + SQLModel + asyncpg + APScheduler — `backend/` (porta 8003)
- **Frontend:** Next.js 15 + React 19 + Tailwind — `frontend/` (porta 3000)
- **IA:** `hermes-procurement/` (FastAPI porta 8004) → LiteLLM (`hermes:4000`) → Groq
- **Banco:** PostgreSQL 16 (`acraprocurement`)
- **Ingress:** Traefik + Cloudflare DNS challenge

## Layout rápido

| Quer alterar... | Vá em |
|---|---|
| Endpoint de API | `backend/app/api/<router>.py` (14 routers) |
| Scraper / conector de portal | `backend/app/services/<fonte>.py` (12 scrapers) |
| Modelo/tabela | `backend/app/db/models.py` (+ migration manual — ver abaixo) |
| Cron/agendamento | `backend/app/main.py` (lifespan) e `backend/app/cron/jobs.py` |
| Scorer de alertas | `backend/app/services/alerts.py` (`_compute_score`) |
| Comportamento do agente IA | `hermes-procurement/main.py` (SYSTEM_PROMPT, PROCUREMENT_TOOLS) |
| Página do dashboard | `frontend/app/dashboard/*/page.tsx` |
| Mapa de calor | `frontend/app/dashboard/bids/BrazilMap.tsx` |
| Deploy / serviços | `docker-compose.yml`, `nginx.conf` |

## Convenões do código

- **Dedup de bids:** sempre `(source, external_id)` em `public_bids`. Todo scraper novo deve respeitar.
- **Scrapers que herdam** `BasePortalScraper` (`services/base_portal.py`): implementam `fetch_bids()` e ganham `sync()` que upsert + loga em `scrape_logs` + atualiza `data_sources`. Scrapers "livres" (PNCP, ComprasNet federal, Licitações-e, QD, BEC) fazem o upsert manual.
- **Todo scraper** grava `ScrapeLog` e chama `source_tracker.update_source_status`.
- **Enums** centralizados em `db/models.py` (`BidSphere`, `BidStatus`, `BidModality`, ...). Os scrapers têm seus próprios `*_MAP` de string→enum.
- **Auth:** `get_current_user` (qualquer ativo), `require_admin`, `require_full_or_admin`. Quase tudo exige JWT.
- **Sem comentários explicativos** no código existente (mantenha o padrão). Não adicione.

## Migrations (importante)

SQLModel usa `create_all()` — **só cria tabelas novas, nunca altera**. Qualquer mudança de schema exige `ALTER TABLE` manual contra o banco de produção:

```bash
docker exec procurement-postgres psql -U procurement -d acraprocurement -c "ALTER TABLE ... "
```

Não há Alembic. Registre migrations manuais no commit.

## ⚠️ Convenção do Compose (leia antes de qualquer deploy)

**Sempre use `-p procurement`** com `docker compose` neste projeto. O nome do projeto prefixa o volume do banco (`procurement_procurement_postgres`). Rodar sem `-p` criaria um volume novo vazio → **app sobe com banco em branco**.

```bash
# exemplos
docker compose -p procurement up -d --build
docker compose -p procurement down        # NUNCA use 'down -v' (apaga o volume!)
docker compose -p procurement logs -f backend
docker compose -p procurement pull && docker compose -p procurement up -d
```

## Comandos úteis

```bash
# logs
docker logs -f procurement-backend
docker logs -f hermes-procurement
docker logs -f procurement-frontend

# sync manual de uma fonte
docker exec procurement-backend curl -sX POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/api/sync/comprasnet?days_back=7

# ver últimos syncs
docker exec procurement-backend curl -s http://localhost:8003/api/sync/status

# psql
docker exec -it procurement-postgres psql -U procurement -d acraprocurement
```

## Segredos

- **Nunca** commite `.env` (está no `.gitignore`). Use `.env.example` como template.
- Secrets reais vêm do **Bitwarden** (ver `/root/products/AGENTS.md`). As vars deste projeto: `POSTGRES_PASSWORD`, `SECRET_KEY`, `SSO_KEY`, `LITELLM_MASTER_KEY`, `SMTP_*`, `PROC_API_TOKEN`.
- `SSO_KEY=acra-sso-2024` é **compartilhado** com Office e Finance — não altere isoladamente.

## Pegadinhas (leia antes de mexer)

- `bec_sp.py` é **stub** (endpoint SOAP descontinuado).
- `celic_rs.py` tem bug de chave duplicada no dict de params.
- `bnc/compra_aberta/portal_compras_publicas` são **speculativos** (tentam endpoints à sorte).
- `e_lic_sc/licitacoes_e/licitacoes_e2_bb` fixam `modality=pregao`.
- `querido_diario.py` grava `source="dou"` (não `querido_diario`).
- `municipal_portals` é **global** (sem tenant).
- `forgot-password` retorna o link de reset no JSON quando SMTP vazio (dev only).
- CORS do backend é `*`.

Lista completa e detalhada: [`docs/5-operations.md`](docs/5-operations.md#issues-conhecidas) e [`README.md#estado-real-e-issues-conhecidas`](README.md#estado-real-e-issues-conhecidas).

## Documentação

- [`README.md`](README.md) — visão geral completa e correta
- [`docs/1-scope.md`](docs/1-scope.md) — doc histórica de PM (2026-04-23; **contém imprecisões**, manter só como histórico)
- [`docs/2-data-sources.md`](docs/2-data-sources.md) — os 12 scrapers em detalhe
- [`docs/3-data-model.md`](docs/3-data-model.md) — 12 tabelas + enums
- [`docs/4-api-reference.md`](docs/4-api-reference.md) — referência de endpoints
- [`docs/5-operations.md`](docs/5-operations.md) — deploy, ops, migrations, issues conhecidas
