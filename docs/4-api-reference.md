# Referência da API

> Backend FastAPI :8003. Docs interativas: `GET /docs` (Swagger) e `GET /openapi.json`.
> **Auth:** `OAuth2PasswordBearer(tokenUrl="/api/auth/login")`, JWT HS256, bcrypt. Tokens de 24h (`access_token_expire_minutes=1440`).
> **Públicos (sem JWT):** `POST /api/auth/{register,login,sso,forgot-password,reset-password}`, `GET /api/cnpj/{digits}`. Todos os demais exigem JWT.
> **Paginação** padrão `page=1&limit=20` (portals/chat usam 50) → resposta `{total, page, limit, pages, data}`.
> **RBAC deps:** `get_current_user` (qualquer ativo), `require_admin`, `require_full_or_admin`.

---

## `/api/auth` — autenticação & tenants

| Método | Path | Auth | Descrição |
|---|---|---|---|
| POST | `/register` | não | cria tenant + admin; se CNPJ, auto-cria `TenantCompany` via BrasilAPI. Body: `{tenant_name, document, document_type, name, email, password, ...}` → 201 |
| POST | `/login` | não | OAuth2 form (`username`, `password`) → `{access_token, token_type, user, tenant}` |
| POST | `/sso` | não | valida JWT externo com `SSO_KEY`; usuário deve pré-existir. Body `{token}` |
| POST | `/forgot-password` | não | gera token (memória, 30 min) + email. ⚠️ se SMTP vazio, **devolve o link no JSON** |
| POST | `/reset-password` | não | consome token, seta senha (min 6). Body `{token, password}` |
| GET | `/me` | sim | perfil básico do usuário |
| GET | `/me/tenant` | sim | tenant completo (Receita, plano) |

## `/api/bids` — licitações

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | lista filtrada/paginada. Params: `sphere, state, city, branch, status, modality, min_value, max_value, days_before_closing, object_type, q, only_open_for_proposals (default true), sort_by (closing_date\|estimated_value\|publication_date\|opening_date\|title\|state\|status), sort_dir, page, limit (≤100)` |
| GET | `/search` | busca rápida (title/description/organ/category). `q` (min 2) |
| GET | `/geo` | agregação por estado (heatmap). `status=aberta` |
| GET | `/geo/cities?state=XX` | agregação por cidade + centroides IBGE (via `geo_cache`) |
| GET | `/stats` | total, valor, média, top-5 ramos, distribuição por esfera, próximos 7 dias |
| GET | `/{bid_id}` | detalhe completo |

> `only_open_for_proposals` = `status=aberta AND (closing_date null OR ≥ today)`. Sorting com `nullslast()`.

## `/api/profiles` — perfis de busca

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | perfis **ativos** do usuário |
| POST | `/` | cria. Body: `{name, preferred_spheres?, preferred_states?, preferred_cities?, preferred_branches?, preferred_categories?, min/max_estimated_value?, exclude_modalities?, require_sme_reservation?, only_with_deadline?, alert_days_before?, keywords?, exclude_keywords?}` |
| GET | `/{id}` | detalhe (tenant-scoped) |
| PATCH | `/{id}` | atualiza (`exclude_unset`) |
| DELETE | `/{id}` | ⚠️ **soft-delete** (`active=False`) — fica invisível no GET |
| POST | `/{id}/test?limit=10` | dry-run do `_compute_score` contra 200 bids abertas (matches ≥ 0.5) |

## `/api/alerts` — alertas

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | paginado (JOIN bid). Params: `profile_id, status, include_expired=false, page, limit` |
| GET | `/summary` | total / novos / favoritos (só bids válidas) |
| PATCH | `/{id}/mark-viewed` | `novo→visto`, stampa `viewed_at` |
| PATCH | `/{id}/favorite` | toggle `favorito↔visto` |
| PATCH | `/{id}/discard` | status `descartado` |
| POST | `/bulk/mark-all-viewed` | bulk do tenant |
| POST | `/bulk/discard-all` | bulk (preserva favoritos; `?status=` opcional) |
| DELETE | `/bulk/discarded` | purge dos já descartados |
| DELETE | `/bulk/all?keep_favorites=true` | purge total (ou só não-favoritos) |

## `/api/tracking` — acompanhamento

| Método | Path | Descrição |
|---|---|---|
| POST | `/{bid_id}` | inicia (1 por tenant → 409 se duplicado). Body `{participated, proposal_submitted, proposal_date?, proposal_value?, won?, result_date?, contract_value?, contract_id?, notes?}` |
| GET | `/` | paginado. `won?` |
| PATCH | `/{bid_id}` | atualiza |
| DELETE | `/{bid_id}` | para de acompanhar |

## `/api/interactions` — favoritos/visto/descartado

| Método | Path | Auth | Descrição |
|---|---|---|---|
| GET | `/{bid_id}` | user | interação do usuário com a bid |
| PUT | `/{bid_id}` | user | upsert `{is_favorite?, is_viewed?, is_discarded?, notes?}` |
| GET | `/` | user | interações do usuário. `only_favorites, only_viewed, page, limit` |
| GET | `/company/all` | full/admin | interações de **todo o tenant**. `user_id?, only_favorites?` |

## `/api/companies` — multi-CNPJ

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | CNPJs do tenant (primário primeiro) |
| POST | `/` | adiciona CNPJ (BrasilAPI). Body `{cnpj_digits}`. Primeiro vira primário. 409 se duplicado |
| POST | `/import-from-tenant` | importa o CNPJ do próprio tenant como `TenantCompany` |
| PATCH | `/{id}/set-primary` | promove (rebaixa os demais) |
| DELETE | `/{id}` | remove não-primário (primário → 400) |

## `/api/cnpj/{digits}` — lookup BrasilAPI (público)

Valida 14 dígitos; consulta `https://brasilapi.com.br/api/cnpj/v1/{clean}`. Retorna: cnpj, razao_social, nome_fantasia, situacao, tipo, natureza_juridica, porte, capital_social, data_abertura, regime_tributario, opcao_simples/mei, cnae (principal + secundários), endereço, telefone, email, **socios[]**. 404 → "CNPJ não encontrado".

## `/api/dashboard` — KPIs

GET `/` → `{total_bids_open, total_bids_coming_7d, total_bids_no_deadline, total_bids_in_db, total_estimated_value, average_value, spheres_distribution, branches_top_5[{branch,count,value}], new_alerts, tracking{total, won, success_rate}}`.

## `/api/sync` — sync manual (BackgroundTasks; retorna imediatamente)

| Método | Path | Descrição |
|---|---|---|
| POST | `/?days_back=3` (1–180) | full: PNCP + keywords + alertas |
| POST | `/keyword` | `{keyword, max_pages=4}` — busca ad-hoc no PNCP |
| POST | `/keywords/profiles` | keywords de todos perfis ativos |
| POST | `/all?days_back=1` (1–30) | roda os **12 scrapers** em sequência |
| POST | `/{source}?days_back=3` | uma fonte. `source ∈ {pncp, comprasnet, bec_sp, licitacoes_e, licitacoes_e2_bb, dou, portal_compras_publicas, e_lic_sc, celic_rs, comprasnet_ba, compra_aberta, bnc, alerts, keywords}`. ⚠️ fonte inválida → **HTTP 200** com `{error:...}` |
| GET | `/status` | últimos 20 `scrape_logs` |

## `/api/sources` — fontes

GET `/` → `[{key, name, description, official_url, active, last_sync_at, last_sync_status, last_sync_records}]`.

## `/api/portals` — catálogo municipal (global, sem tenant)

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | paginado (`state, city (partial), active, verified, portal_type, scraper_key, q, page, limit ≤200`) |
| GET | `/stats` | total/active/verified/with_api/with_scraper + breakdowns |
| GET | `/{id}` | um portal |
| POST | `/` | cria. `{city?, state?, ibge_code?, portal_name?, portal_url (req), system_name?, portal_type=scraping_html, api_endpoint?, scraper_key?, active=true, verified=false, contact_email?, contact_phone?, notes?}` |
| PATCH | `/{id}` | atualiza |
| DELETE | `/{id}` | exclui |

> ⚠️ Sem isolamento por tenant — qualquer autenticado edita qualquer portal.

## `/api/users` — gestão de usuários (admin/full)

| Método | Path | Auth | Descrição |
|---|---|---|---|
| GET | `/` | full/admin | lista usuários do tenant |
| POST | `/` | admin | convida. `{name, email, password, role=simple}` → 201 (409 se email) |
| PATCH | `/{id}` | admin | `{role?, active?, name?}`. Admin não rebaixa a si |
| DELETE | `/{id}` | admin | desativa (soft). Admin não desativa a si |

## `/api/chat` — Hermes Licita

| Método | Path | Descrição |
|---|---|---|
| POST | `/` | `{message, messages[]}` → proxy para `hermes-procurement:8004/chat`. Persiste user + assistant. Falha → mensagem "dificuldades técnicas" (também persistida) |
| GET | `/history?limit=50` | histórico do usuário (antigos por último) |

> `messages[]` é aceito mas **não repassado** ao Hermes (só `message`).

## `/health`

GET → `{"status":"ok","module":"procurement"}`.
