# Deploy — Supabase + Render + Vercel

Guia para colocar o sistema no ar sem nada rodando na sua maquina.

Arquitetura:

```
Vercel (frontend Next.js)  ->  Render (backend FastAPI)  ->  Supabase (Postgres)
                                       ^
                                 GitHub Actions (cron dispara os syncs)
```

Ordem de execucao: **1) Supabase  ->  2) Render  ->  3) Vercel  ->  4) Cron**.

---

## 1. Supabase (banco)

1. Crie um projeto novo em https://supabase.com (plano free serve).
2. Anote a senha do banco que voce definir na criacao.
3. No projeto, va em **Connect** (botao no topo) ou **Settings > Database**.
4. Copie a connection string do **Session Pooler** (nao a Direct connection).
   - Ela tem a forma `...pooler.supabase.com:5432/postgres`.
   - Troque `[YOUR-PASSWORD]` pela senha do banco.
5. Guarde essa string. Ela vira o `DATABASE_URL` no Render.

Observacao: nao precisa criar tabela nem rodar SQL. O backend cria tudo sozinho no
primeiro start (`init_db`). Nao precisa ativar RLS: so o backend acessa o banco.

---

## 2. Koyeb (backend) — recomendado (free, sem cartao, nao dorme)

1. Suba este repositorio no GitHub (ja esta em `joaosilvestrim-cloud/robo-licita-o`).
2. Em https://koyeb.com: **Create Web Service > GitHub** e selecione este repo.
3. Build:
   - Builder: **Dockerfile**.
   - **Work directory**: `backend`.
   - **Dockerfile location**: `backend/Dockerfile`.
     (se o Koyeb reclamar do caminho, troque para so `Dockerfile`.)
4. Exposicao / porta:
   - Porta: **8000** (protocolo HTTP).
   - Health check path: `/health`.
5. Instance: **Free** (nano).
6. **Environment variables** (aba Environment):
   - `DATABASE_URL` = string do Session Pooler do Supabase (passo 1).
   - `PORT` = `8000`.
   - `ENABLE_SCHEDULER` = `false`.
   - `CORS_ORIGINS` = `*` (ajusta depois de ter a URL da Vercel).
   - `SECRET_KEY` = uma frase aleatoria longa (invente qualquer coisa forte).
   - `CRON_SECRET` = outra frase aleatoria longa. **Guarde este valor** (vai no cron).
   - E-mail (`SMTP_*`) e `FRONTEND_URL`: deixe em branco por enquanto.
7. **Deploy** e espere o build.
8. Teste: abra `https://SEU-APP.koyeb.app/health`. Deve responder
   `{"status":"ok","module":"procurement"}`.
9. Confira `https://SEU-APP.koyeb.app/docs` (Swagger da API).

> O free do Koyeb fica sempre ligado (nao dorme). O cron so dispara os syncs.

### Alternativa: Render (free, dorme apos 15min)

Este repo tem `render.yaml`. Em https://render.com: **New > Blueprint**, selecione o
repo, preencha `DATABASE_URL` e `CORS_ORIGINS`. `SECRET_KEY`/`CRON_SECRET` o Render gera.
O plano free dorme apos 15min; a primeira chamada demora ~30-60s pra acordar (o cron
ja trata com retry). URL fica `https://SEU-BACKEND.onrender.com`.

---

## 3. Vercel (frontend)

1. Em https://vercel.com: **Add New > Project** e selecione este repo.
2. Em **Root Directory**, escolha `frontend`.
3. Framework: Next.js (detecta sozinho).
4. Em **Environment Variables**, adicione:
   - `NEXT_PUBLIC_API_URL` = a URL do backend (ex `https://SEU-APP.koyeb.app`), sem barra no final.
5. Deploy.
6. Anote a URL final, ex `https://robo-licitacao.vercel.app`.

Depois que tiver a URL da Vercel:

7. Volte no backend (Koyeb/Render) e ajuste `CORS_ORIGINS` para a URL da Vercel
   (ex `https://robo-licitacao.vercel.app`). Salve. O backend redeploy sozinho.
8. Opcional: ajuste `FRONTEND_URL` para a mesma URL (links de e-mail).

---

## 4. Cron (GitHub Actions)

Os syncs sao disparados por um workflow em `.github/workflows/sync.yml`.

1. No GitHub do repo: **Settings > Secrets and variables > Actions > New repository secret**.
2. Crie dois secrets:
   - `API_URL` = a URL do backend (ex `https://SEU-APP.koyeb.app`).
   - `CRON_SECRET` = o mesmo valor que voce colocou no backend (passo 2).
3. Em **Actions**, habilite os workflows se pedir.
4. Teste manual: abra o workflow **Sync licitacoes (cron)** e clique em **Run workflow**.
   Deixe `source = pncp`. Isso puxa licitacoes reais do PNCP pro banco.

Agenda automatica ja configurada:

| Frequencia | Fonte |
|---|---|
| de hora em hora | processa alertas |
| a cada 6h | PNCP (principal) |
| a cada 8h | ComprasNet federal |
| 2x ao dia | Querido Diario + keywords dos perfis |

---

## 5. Primeiro uso

1. Abra a URL da Vercel.
2. Em **/login**, cadastre sua empresa pelo CNPJ (busca automatica na BrasilAPI).
3. Rode um sync (passo 4.4 acima) ou espere a agenda.
4. Veja as licitacoes em **/dashboard/bids**, com mapa de calor e filtros.
5. Crie um **perfil** de monitoramento (keywords, estados, faixa de valor).
6. Os alertas aparecem conforme o cron cruza licitacoes com o perfil.

---

## Notas

- **IA (Hermes):** o chat depende de um orquestrador LLM externo que nao vem neste
  deploy. Sem ele, o chat cai num modo com atalhos manuais. Religar a IA e uma fase
  posterior (apontar direto pra Groq ou Anthropic).
- **Scrapers especulativos:** `bnc`, `compra_aberta`, `portal_compras_publicas` e
  `bec_sp` nao entram no cron por enquanto (nao sao confiaveis). PNCP + ComprasNet +
  Querido Diario cobrem o essencial. Da pra ligar por sync manual quando quiser testar.
- **Variaveis do backend:** referencia completa em `.env.example`.
