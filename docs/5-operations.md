# Operações

## Deploy

### Serviços (`docker-compose.yml`)

| Serviço | Imagem/Build | Notas |
|---|---|---|
| `postgres` | `postgres-16-alpine-patched` (build context `/opt/dockerfiles/postgres-alpine`) | DB `acraprocurement`, role `procurement`, TZ SP. ⚠️ depende de path do VPS |
| `backend` | build `./backend` | :8003, healthcheck `/health`, redes `procurement_net` + `acra_shared` |
| `frontend` | build `./frontend` | :3000, **hardened** (`read_only`, tmpfs `/tmp`+`/.next/cache`, `cap_drop: ALL`, `no-new-privileges`), stage `pkgpatch` no Dockerfile |
| `nginx` | `nginx:alpine` | proxy interno, labels Traefik |
| `hermes-procurement` | build `./hermes-procurement` | :8004, depende de `backend` healthy |

**Redes:** `procurement_net` (bridge), `acra_shared` (external — SSO com Office/Finance), `proxy` (external — Traefik).

### Subir do zero / operar

> ⚠️ **Sempre `-p procurement`.** O volume do banco é prefixado pelo nome do projeto → `procurement_procurement_postgres`. Sem `-p` (default `saas-licitacoes`), um volume **vazio** seria criado e o app subiria com banco em branco. **Nunca `down -v`** (apagaria o volume e todos os dados).

```bash
cp .env.example .env   # preencher secrets (Bitwarden), ou copie o .env de produção existente
docker compose -p procurement up -d --build
```

> O build do `postgres` usa `context: /opt/dockerfiles/postgres-alpine` (específico do VPS Nanuck). Em outro host, troque por `image: postgres:16-alpine` e remova o bloco `build`.

> **Histórico:** este projeto antes rodava de `/root/platform/procurement` (preservado como backup). O cutover manteve o nome do projeto para reutilizar volume e redes — zero perda de dados (39.668 bids, 2 tenants, 2 users).

### Traefik (labels no `nginx`)

```yaml
- traefik.enable=true
- traefik.docker.network=proxy
- traefik.http.routers.procurement.entrypoints=https
- traefik.http.routers.procurement.rule=Host(`licita.nanuck.com.br`)
- traefik.http.routers.procurement.tls.certresolver=cloudflare
- traefik.http.services.procurement.loadbalancer.server.port=80
```

### Nginx interno (`nginx.conf`)

- `/api/`, `/docs`, `/openapi.json` → `procurement-backend:8003`
- `/` → `procurement-frontend:3000` (com upgrade p/ HMR)
- `client_max_body_size 10M`

## Migrations

SQLModel `create_all()` **só cria tabelas novas**. Mudanças exigem `ALTER TABLE` manual:

```bash
docker exec procurement-postgres psql -U procurement -d acraprocurement -c "
  ALTER TABLE proc_tenants ADD COLUMN IF NOT EXISTS razao_social VARCHAR;
"
```

Não há Alembic. **Registre migrations no commit message.** Para unicidade de `public_bids`:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_public_bids_source_external
  ON public_bids (source, external_id);
```

## Operações comuns

```bash
# logs
docker logs -f procurement-backend
docker logs -f hermes-procurement
docker logs -f procurement-frontend

# health
curl -s https://licita.nanuck.com.br/health
curl -s https://licita.nanuck.com.br/api/dashboard -H "Authorization: Bearer $TOKEN"

# sync manual (uma fonte)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "https://licita.nanuck.com.br/api/sync/comprasnet?days_back=7"

# status dos syncs (últimos 20)
curl -H "Authorization: Bearer $TOKEN" https://licita.nanuck.com.br/api/sync/status

# status de todas as fontes
curl -H "Authorization: Bearer $TOKEN" https://licita.nanuck.com.br/api/sources

# psql
docker exec -it procurement-postgres psql -U procurement -d acraprocurement

# reconstruir só o backend
docker compose -p procurement up -d --build backend
```

## Variáveis de ambiente

Ver `.env.example`.

| Var | Obrig? | Descrição |
|---|---|---|
| `POSTGRES_PASSWORD` | sim | senha do role `procurement` |
| `SECRET_KEY` | sim | assinatura JWT do backend |
| `SSO_KEY` | sim | SSO compartilhado com Office/Finance (**não alterar isoladamente**) |
| `OFFICE_API_URL` | — | control plane (default `http://acra-backend:8000`) |
| `HERMES_URL` | sim | orquestrador LiteLLM (`http://hermes:4000`) |
| `LITELLM_MASTER_KEY` | sim | auth no orquestrador |
| `PROC_API_TOKEN` | — | JWT de serviço p/ Hermes chamar a API (gerar via `/api/auth/login`) |
| `HERMES_PROCUREMENT_URL` | — | usado pelo backend no `/api/chat` |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM` | — | se vazio, `forgot-password` devolve o link no JSON (dev only) |
| `FRONTEND_URL` | — | links de email (default `http://localhost:3003`) |
| `PNCP_SYNC_INTERVAL_HOURS` | — | lido, mas o agendamento real é fixo no `main.py` |

## Backup

```bash
# dump completo
docker exec procurement-postgres pg_dump -U procurement acraprocurement > backup_$(date +%F).sql
# restore
cat backup.sql | docker exec -i procurement-postgres psql -U procurement -d acraprocurement
```

O volume nomeado `procurement_postgres` guarda os dados persistentes.

## Issues conhecidas (_priorize_)

### Bugs / corretudes

1. **`bec_sp.py` stub** — `sync_bec_sp()` retorna antes do parsing SOAP (endpoint descontinuado). Decidir: Playwright ou remover e usar PNCP.
2. **`celic_rs.py` bug** — dict de params com `"dtAbertura"` duplicado → consulta só 1 dia.
3. **`bnc`, `compra_aberta`, `portal_compras_publicas` especulativos** — 3 endpoints tentados à sorte; não validados; podem retornar vazio silenciosamente.
4. **Modalidade fixa `pregao`** em `e_lic_sc`, `licitacoes_e`, `licitacoes_e2_bb` (não detectam a real).
5. **`querido_diario` grava `source="dou"`** (inconsistente com nome do arquivo). 17 cidades SP hardcoded; `days_back` ignorado.

### Segurança

6. **Reset de senha em memória** (`_reset_tokens`) — perde a cada restart; sem HA. Migrar para tabela.
7. **`forgot-password` vaza link** no JSON quando `smtp_user` vazio (risco em prod).
8. **CORS `allow_origins=["*"]`** no backend — restringir à origem do frontend.
9. **`municipal_portals` sem tenant** — qualquer autenticado edita qualquer portal. Tornar admin-only ou adicionar tenant.
10. **`verify=False`** (`httpx`) em vários scrapers — TLS desabilitado.
11. **`sync.py /{source}`** retorna HTTP 200 com `{error:...}` para fonte inválida (cliente deve checar body).
12. **Unicidade `public_bids`** só em migration; ORM select-then-upsert (race condition). Adicionar `ON CONFLICT`.
13. **`profiles DELETE` soft** mas GET só lista ativos → perfil excluído fica irrecuperável pela API.

### Confiabilidade

14. **`chat.py`** persiste mensagem falsa de "dificuldades técnicas" no histórico quando Hermes falha.
15. **`bids.py /geo/cities`** descarta cidades cujo código IBGE não casa com centróide (sem fallback claro).
16. **Cron `bec_sp`** agenda job que só loga "pulando" — remover ou desabilitar.
17. **`PNCP_SYNC_INTERVAL_HOURS`** é lido das settings mas o schedule é fixo (6h) no `main.py` — enganoso.

## Observabilidade

- Healthcheck HTTP em todos serviços. Verifique com `docker ps`.
- Logs via stdout (docker logs). Backend loga cada cron job (`logger.info`).
- `GET /api/sync/status` e `GET /api/sources` dão visibilidade de sync.
- Não há métricas/tracing (Prometheus/OTel) — item de roadmap.

## Roadmap de ops

- [ ] Alembic no lugar de `create_all` + ALTER manual
- [ ] Reset-tokens em DB + 2FA opcional
- [ ] Restringir CORS; revisar `verify=False`
- [ ] `ON CONFLICT` no upsert de bids
- [ ] Métricas (Prometheus) + alertas
- [ ] Testes automatizados (pytest backend; Playwright frontend)
- [ ] Webhook outbound (Telegram/Slack/n8n) para alertas e `daily_briefing`
- [ ] Backup automático agendado do `pg_dump`
