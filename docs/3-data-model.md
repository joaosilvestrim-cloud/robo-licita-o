# Modelo de dados

> `backend/app/db/models.py` — SQLModel → PostgreSQL. 12 tabelas + 9 enums. Criadas via `create_all()` no `lifespan` (`database.py::init_db`). **Mudanças de schema exigem `ALTER TABLE` manual** (não há Alembic).

## Enums

| Enum | Valores |
|---|---|
| `TenantType` | `cnpj`, `cpf` |
| `BidSphere` | `federal`, `estadual`, `municipal` |
| `BidStatus` | `aberta`, `andamento`, `encerrada`, `cancelada`, `programada` |
| `BidModality` | `pregao`, `concorrencia`, `tomada_preco`, `convite`, `dispensa`, `inexigibilidade`, `leilao`, `dialogo_competitivo` |
| `ObjectType` | `bem`, `servico`, `obra`, `consultoria`, `misto` |
| `AlertStatus` | `novo`, `visto`, `favorito`, `descartado` |
| `ScrapeStatus` | `sucesso`, `erro`, `parcial` |
| `PortalType` | `api_rest`, `scraping_html`, `pncp_passthrough`, `manual` |
| `UserRole` | `admin` (gerencia usuários, vê tudo), `full` (vê tudo), `simple` (só o seu) |

## Tabelas

### `proc_tenants` — Empresas (multi-tenant)
`id, name, document (unique), document_type, email, phone, active, created_at, updated_at` + dados Receita (`razao_social, nome_fantasia, cnae_code/description, natureza_juridica, situacao_cadastral, capital_social, data_abertura, porte`) + endereço completo + `plan` (default `free`) + `plan_expires_at`.
Relationships: `users`, `profiles`, `trackings`.

### `proc_users` — Usuários
`id, tenant_id (FK proc_tenants), name, email (unique), hashed_password, role (UserRole), active, created_at`.
Relationships: `tenant`, `interactions`.

### `tenant_companies` — CNPJs adicionais (multi-CNPJ)
Cartão CNPJ completo da BrasilAPI: `cnpj, cnpj_digits, razao_social, nome_fantasia, situacao_cadastral, tipo (Matriz/Filial), natureza_juridica, porte, capital_social, data_abertura, regime_tributario, opcao_simples, opcao_mei, cnae_code/description, cnaes_secundarios_json (Text), endereço, telefone, email, socios_json (Text QSA), is_primary, created_at`.

### `public_bids` — Licitações (núcleo)
- **Identificação:** `id, external_id, source, title, description, object_type`
- **Classificação:** `category_code/name` (CATMAT), `branch_code/name` (CNAE/ramo)
- **Localização:** `sphere (BidSphere), state (UF), city, city_code (IBGE 7)`
- **Órgão:** `organ_name, organ_cnpj`
- **Datas:** `publication_date, opening_date, closing_date, status (BidStatus), status_date`
- **Valores:** `estimated_value, maximum_value, modality (BidModality)`
- **Requisitos:** `min_patrimony, min_revenue, years_of_operation, requires_sme, requires_mei`
- **Contato:** `contact_name/email/phone`
- **URLs:** `edital_url, details_url, platform_url`
- **Sistema:** `created_at, updated_at, last_scraped`
- ⚠️ Unicidade `(source, external_id)` **só em migration** — `Config` vazio; ORM faz select-then-upsert.
- Relationships: `alerts`, `trackings`.

### `procurement_profiles` — Perfis de busca
Por usuário. Filtros armazenados como **texto CSV**: `preferred_spheres, preferred_states, preferred_cities, preferred_branches, preferred_categories`. Limites `min/max_estimated_value`. Preferências: `exclude_modalities, require_sme_reservation, only_with_deadline, alert_days_before (default 7)`. Keywords: `keywords, exclude_keywords` (CSV; `*` = todos). `active` (soft-delete).

### `procurement_alerts` — Matches bid×profile
`id, tenant_id, profile_id (FK), bid_id (FK), match_score (Decimal 0.00–1.00), match_reasons (JSON text), status (AlertStatus), viewed_at, created_at, sent_at`. Inserido por `process_alerts()` quando score ≥ 0.5; dedup por `(profile_id, bid_id)`.

### `bid_tracking` — Acompanhamento (por tenant, 1 por bid)
`participated, proposal_submitted, proposal_date, proposal_value, won (bool nullable), result_date, contract_value, contract_id, notes`. Um row por `(tenant_id, bid_id)`.

### `bid_interactions` — Favorito/visto/descartado (por usuário)
Distinto do tracking: `user_id, tenant_id (desnormalizado), bid_id, is_favorite, is_viewed, is_discarded, notes, viewed_at, favorited_at`. Permite visão consolidada da empresa.

### `scrape_logs` — Histórico de syncs
`source, start_time, end_time, status (ScrapeStatus), records_found, records_inserted, records_updated, error_message, created_at`.

### `data_sources` — Registro de fontes (informativo)
`key (unique), name, description, official_url, active, last_sync_at, last_sync_status, last_sync_records`. Atualizado por `source_tracker.update_source_status`.

### `municipal_portals` — Catálogo de portais municipais (global)
`ibge_code, city, state, portal_name, portal_url, system_name, portal_type (PortalType), api_endpoint, scraper_key, active, verified, contact_email/phone, notes, last_sync_at/status`. ⚠️ **Sem tenant** — catálogo compartilhado.

### `proc_chat_messages` — Histórico do chat
`tenant_id, user_id, role ("user"|"assistant"), content (Text), created_at`.

## Diagrama de relacionamentos

```
proc_tenants ──< proc_users ──< bid_interactions >── public_bids
     │              │                                 │
     │              └──< procurement_profiles ──< procurement_alerts
     │                                                 │
     ├──< tenant_companies                             │
     ├──< bid_tracking >───────────────────────────────┘
     └──< proc_chat_messages

data_sources      (catálogo, isolado)
municipal_portals (catálogo global, isolado)
scrape_logs       (audit, isolado)
```
