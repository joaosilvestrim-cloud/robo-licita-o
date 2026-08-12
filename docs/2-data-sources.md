# Fontes de dados — os 12 scrapers

> Path: `backend/app/services/`. Todos gravam em `public_bids` (chave de dedup `(source, external_id)`), registram `scrape_logs` e atualizam `data_sources` via `source_tracker.update_source_status`. **Nenhum usa auth/API key** — todos consomem endpoints públicos via `httpx`.

## Padrões universais

- `BidSphere {federal, estadual, municipal}`, `BidStatus {aberta, andamento, encerrada, cancelada, programada}`, `BidModality {pregao, concorrencia, tomada_preco, convite, dispensa, inexigibilidade, leilao, dialogo_competitivo}`.
- Cada scraper pula bids com `closing_date < today` durante o mapeamento (expiradas não entram, só são atualizadas se já existirem).
- `BasePortalScraper.sync()` faz select-then-insert/update (não upsert com `ON CONFLICT` — condição de corrida possível; a unicidade real é garantida só por migration).
- `verify=False` (TLS desabilitado) em `base_portal`, `bec_sp`, `licitacoes_e`, `licitacoes_e2_bb`.

---

## Fontes (status atual)

### 1. `pncp` — PNCP (sync por data) ✅ working
- **URL:** `https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao`
- **Funções:** `sync_pncp(days_back=1)` itera as **9 modalidades** (`PNCP_MODALITIES=[1..9]`), `tamanhoPagina=50`, até 5 páginas cada.
- **Maps:** `MODALITY_MAP`, `SPHERE_MAP` (F/E/M), `STATUS_MAP` (1=aberta,2/5=andamento,3=encerrada,4=cancelada).
- **external_id:** `numeroControlePNCP`; órgão de `orgaoEntidade`, local de `unidadeOrgao` (uf, municipio, codigoIbge[:7]).
- **Detalhe:** `_fetch_modality` está anotado `-> tuple[list,int,int]` mas retorna só `items_all` (anotação errada, código funciona).

### 2. `pncp_search` — PNCP full-text (search) ✅ working
- **URLs:** `https://pncp.gov.br/api/search` (+ detalhe `/orgaos/{cnpj}/compras/{ano}/{seq}`).
- **Funções:** `sync_keyword(keyword, max_pages=4)`, `sync_all_profile_keywords()` (coleta keywords + `preferred_branches` de todos perfis ativos).
- **Dedup:** grava com `source="pncp"` (mesma chave do sync por data → **merge** com #1). Detalhe buscado só quando a bid é nova ou falta data/valor.
- **Params:** `tipos_documento=edital`, `tam_pagina=20`.
- **Log:** `ScrapeLog` agregado com `source="pncp_search"`.

### 3. `comprasnet` — ComprasNet/SIASG (federal) ✅ working
- **URL:** `http://compras.dados.gov.br/licitacoes/v1/licitacoes.json` (HTTP, REST, Lei 8.666 legado).
- **Função:** `sync_comprasnet(days_back=1)`, itens em `_embedded.licitacoes`, pagina via `page.totalPages`, `quantidade=500`.
- **external_id:** `identificador`; esfera **federal**; state/city geralmente null.

### 4. `licitacoes_e` — Licitações-e (Banco do Brasil) ⚠️ working, modality fixa
- **URL:** POST `https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop` (HTML).
- **Form:** `opcao=preencherPesquisar`, `situacaoLicitacao=A`, `itensPorPagina=100`.
- **external_id:** número bruto (sem prefixo); esfera **municipal**; **modality hardcoded `pregao`**.
- Parsing via BeautifulSoup (`table.tabelaResultados tbody tr`); próxima página via `a.proximaPagina`.

### 5. `licitacoes_e2_bb` — Licitações-e v2 (interface estática BB) ⚠️ working, modality fixa
- **URL:** POST `https://licitacoes-e2.bb.com.br/aop-inter-estatico/pesquisar-licitacao.aop` (HTML).
- Quase clone do #4. `external_id="e2_{número}"`, esfera municipal, **modality fixa `pregao`**.

### 6. `dou` — Querido Diário (OKBR) ✅ working (escopo limitado)
- Arquivo: `services/querido_diario.py` (grava `source="dou"`, **não** `querido_diario`).
- **URL:** `https://api.queridodiario.ok.org.br/gazettes`.
- **Cobertura:** `TERRITORY_IDS` = **17 cidades SP** hardcoded (capital, Campinas, Sorocaba, Jundiaí, Ribeirão Preto, Santos, ...). `KEYWORDS = ["aviso de licitação","aviso de pregão","edital de licitação","dispensa de licitação"]`.
- **Query:** `size=5, excerpt_size=800, number_of_excerpts=2` por territory×keyword. `days_back` **ignorado** (latência multi-semana do QD). Pula gazettes > 180 dias sem data de encerramento futura.
- **Parsing:** regex extrai data de encerramento (só futura) e valor R$ do excerpt; `external_id="qd_{md5[:16]}"` de `gazette_url:idx`.

### 7. `comprasnet_ba` — ComprasNet Bahia ✅ working
- **URL:** `https://www.comprasnet.ba.gov.br/sgcl/Pesquisa/pesquisarLicitacoes` (HTML).
- **Classe:** `ComprasNetBAScraper(BasePortalScraper)`. `external_id="cnba_{id}"`, esfera **estadual**, state `BA`. Próxima página via `a.proxima, a.next, li.next:not(.disabled) a`. Sem valor/cnpj.

### 8. `e_lic_sc` — e-lic SC (Santa Catarina) ⚠️ working, modality fixa
- **URL:** POST `https://e-lic.sc.gov.br/index.php/licitacoes/pesquisar` (HTML form).
- **Classe:** `ELicSCScraper(BasePortalScraper)`. `external_id="elic_{id}"`, esfera estadual, state `SC`, **modality hardcoded `pregao`**.

### 9. `celic_rs` — CELIC RS ⚠️ bug
- **URL:** `https://www.celic.rs.gov.br/celic/consultarLicitacoes` (HTML).
- **Classe:** `CelicRSScraper(BasePortalScraper)`. `external_id="celic_{id}"`, esfera estadual, state `RS`.
- **🐛 Bug:** no dict de params, `"dtAbertura"` aparece **2x** (a 2ª = `date_to` sobrescreve a 1ª = `date_from`) → consulta só 1 dia.

### 10. `portal_compras_publicas` ⚠️ speculative
- **URLs tentadas:** `https://www.portaldecompraspublicas.com.br/api/{v1/licitacoes, licitacoes, processos}`.
- **Classe:** `PortalComprasPublicasScraper(BasePortalScraper)`. `external_id="pcp_{id}"`, esfera municipal. Tenta os 3 endpoints e usa o primeiro que responde 200 — **não validado** contra API real.

### 11. `compra_aberta` ⚠️ speculative
- **URLs tentadas:** `https://compraaberta.com.br/api/{licitacoes, v1/licitacoes, processos}`.
- **Classe:** `CompraAbertaScraper(BasePortalScraper)`. `external_id="ca_{id}"`, esfera municipal. Mesmo padrão especulativo (3 endpoints). Sem paginação.

### 12. `bnc` — Banco Nacional de Compras ⚠️ speculative
- **URLs tentadas:** `https://bnc.org.br/{api/licitacoes, api/v1/licitacoes, api/processos}`.
- **Classe:** `BNCScraper(BasePortalScraper)`. `external_id="bnc_{id}"`, esfera municipal. Mesmo padrão. Pagina até 30 páginas.

### 13. `bec_sp` — BEC/SP ❌ stub
- Arquivo: `services/bec_sp.py`. **`sync_bec_sp()` retorna cedo** gravando só um `ScrapeLog` `parcial` ("Endpoint SOAP descontinuado"). Todo o parsing SOAP abaixo do `return` é **morto**. Precisa de Playwright ou migração para PNCP.

---

## Serviços auxiliares (não-scrapers)

| Arquivo | Função |
|---|---|
| `base_portal.py` | `BasePortalScraper(ABC)` — `fetch_bids()` abstract + `sync()` concreto (upsert + log + source_tracker) |
| `source_tracker.py` | `update_source_status(key, status, records)` — atualiza `data_sources` |
| `alerts.py` | `process_alerts()` + `_compute_score(bid, profile)` (threshold 0.5; pesos: spheres 20, states 25, cities 15, branches 25, keywords 15; hard-excludes exclude_keywords/modalities e faixas de valor; `require_sme_reservation` aplica 0.7×) |
| `cleanup.py` | `close_expired_bids()` + `delete_expired_alerts()` (preserva favoritos) |
| `geo_cache.py` | centroides IBGE em memória (`get_state_centroids(uf)`) — computa centróide do maior anel externo do polígono; cache por processo com `asyncio.Lock` |

> Não existe `services/municipal_portals.py`. Portais municipais são só um catálogo (`MunicipalPortal` em `db/models.py` + router `api/municipal_portals.py`).

## Adicionar uma nova fonte

1. Crie `services/<fonte>.py` (herde `BasePortalScraper` se for portal paginado; siga o padrão de `comprasnet_ba.py`).
2. Defina `source_key`/`source_name`, implemente `fetch_bids()` retornando dicts no shape de `PublicBid`; respeite `(source, external_id)`.
3. Adicione um wrapper `run_<fonte>_sync()` em `cron/jobs.py`.
4. Registre o job no `lifespan` de `backend/app/main.py`.
5. Adicione o caso em `sync.py` (`/{source}` e/ou `/all`).
6. Garanta que exista um row em `data_sources` com o `key` (senão `source_tracker` é no-op).
7. Atualize este doc e o README.
