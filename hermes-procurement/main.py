"""Hermes Licita — Subagente especializado em licitações públicas brasileiras."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import date

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    procurement_api_url: str = "http://procurement-backend:8003"
    hermes_url: str = "http://hermes:4000"
    litellm_master_key: str = "Dfc@1947"
    proc_api_token: str = ""  # JWT de serviço para chamadas internas
    hermes_procurement_url: str = "http://hermes-procurement:8004"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
scheduler = AsyncIOScheduler()

SYSTEM_PROMPT = """Você é o Hermes Licita, assistente inteligente de licitações públicas do Acrasystem.

Sua especialidade é ajudar empresas brasileiras a encontrar e ganhar licitações públicas (federais, estaduais e municipais) publicadas no PNCP (Portal Nacional de Contratações Públicas) e outros portais.

Você pode:
- Buscar licitações abertas por palavras-chave, estado, esfera, ramo de atividade e valor
- Explicar termos e modalidades de licitação (Pregão Eletrônico, Concorrência, Dispensa, etc.)
- Sugerir palavras-chave para busca com base no CNAE da empresa
- Detalhar licitações específicas (objeto, prazo, valor estimado, órgão)
- Auxiliar na criação de perfis de monitoramento personalizados
- Analisar alertas de licitações compatíveis com o perfil do usuário
- Disparar sincronizações do PNCP para buscar licitações com novos termos

Sempre responda em português, de forma clara, direta e com foco em dados concretos.
Quando citar valores, use formato brasileiro (R$ 1.234.567,89).
Quando citar datas, use formato DD/MM/AAAA.
Priorize licitações abertas e com prazo próximo quando relevante."""

PROCUREMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_bids",
            "description": "Busca licitações com filtros avançados. Use para responder perguntas sobre licitações disponíveis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Palavras-chave de busca no título/objeto da licitação"},
                    "sphere": {"type": "string", "enum": ["federal", "estadual", "municipal"], "description": "Esfera de governo"},
                    "state": {"type": "string", "description": "UF, ex: SP, RJ, MG"},
                    "city": {"type": "string", "description": "Município"},
                    "status": {"type": "string", "enum": ["aberta", "andamento", "encerrada", "programada"], "description": "Status da licitação"},
                    "limit": {"type": "integer", "default": 10, "description": "Quantidade de resultados"},
                    "min_value": {"type": "number", "description": "Valor mínimo estimado em reais"},
                    "max_value": {"type": "number", "description": "Valor máximo estimado em reais"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bid_detail",
            "description": "Obtém todos os detalhes de uma licitação pelo seu ID interno",
            "parameters": {
                "type": "object",
                "properties": {
                    "bid_id": {"type": "integer", "description": "ID interno da licitação"},
                },
                "required": ["bid_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard",
            "description": "Obtém KPIs gerais: total de licitações abertas, valor total em jogo, distribuição por esfera e ramo",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_alerts",
            "description": "Lista alertas de licitações compatíveis com o perfil do tenant",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["novo", "visto", "favorito", "descartado"], "description": "Status do alerta"},
                    "limit": {"type": "integer", "default": 5, "description": "Quantidade de alertas"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_keyword_sync",
            "description": "Dispara sincronização com o PNCP para uma palavra-chave específica, buscando licitações novas",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Palavra-chave para buscar no PNCP"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_profile",
            "description": "Cria um perfil de monitoramento de licitações para o tenant. O perfil define filtros automáticos para geração de alertas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do perfil, ex: 'TI - São Paulo'"},
                    "spheres": {"type": "string", "description": "Esferas separadas por vírgula, ex: 'federal,estadual'"},
                    "states": {"type": "string", "description": "UFs separadas por vírgula, ex: 'SP,RJ'"},
                    "branches": {"type": "string", "description": "Ramos separados por vírgula, ex: 'TI,Software'"},
                    "keywords": {"type": "string", "description": "Palavras-chave separadas por vírgula"},
                    "min_value": {"type": "number", "description": "Valor mínimo estimado em reais"},
                    "max_value": {"type": "number", "description": "Valor máximo estimado em reais"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_modality",
            "description": "Explica uma modalidade de licitação pública brasileira com base no conhecimento jurídico",
            "parameters": {
                "type": "object",
                "properties": {
                    "modality_name": {
                        "type": "string",
                        "description": "Nome da modalidade, ex: 'pregão eletrônico', 'concorrência', 'dispensa', 'inexigibilidade'",
                    },
                },
                "required": ["modality_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_keywords",
            "description": "Sugere palavras-chave para busca de licitações com base no CNAE ou descrição da atividade da empresa",
            "parameters": {
                "type": "object",
                "properties": {
                    "cnae_description": {
                        "type": "string",
                        "description": "Descrição do CNAE ou atividade principal da empresa",
                    },
                },
                "required": ["cnae_description"],
            },
        },
    },
]

MODALITY_EXPLANATIONS = {
    "pregão": (
        "Pregão (Lei 14.133/2021, art. 6º, XLI): Modalidade obrigatória para aquisição de bens e serviços comuns. "
        "No Pregão Eletrônico, a disputa ocorre em sessão pública virtual com lances sucessivos. "
        "É a modalidade mais comum no Brasil — favorável a PMEs pois não exige habilitação prévia e permite lance de último recurso. "
        "Critério de julgamento: menor preço ou maior desconto. Sem limite de valor."
    ),
    "concorrência": (
        "Concorrência (Lei 14.133/2021, art. 6º, XXXVIII): Usada para obras, serviços de engenharia de grande porte e compras de alto valor. "
        "Exige ampla publicidade e prazo mínimo de 25 dias úteis. "
        "Pode usar critérios: menor preço, melhor técnica, técnica e preço, maior retorno econômico ou maior desconto."
    ),
    "tomada de preços": (
        "Tomada de Preços: Modalidade da lei antiga (Lei 8.666/93) para valores intermediários. "
        "Na Nova Lei (14.133/21), foi substituída pela Concorrência. "
        "Ainda pode aparecer em contratos antigos."
    ),
    "convite": (
        "Convite: Modalidade da lei antiga (Lei 8.666/93) para pequenos valores. "
        "Substituído pelo Diálogo Competitivo ou Concorrência simplificada na Nova Lei."
    ),
    "dispensa": (
        "Dispensa de Licitação (Lei 14.133/2021, art. 75): Permite contratar diretamente sem licitação em casos específicos. "
        "Os principais casos: valor baixo (até R$ 57.484 para obras ou R$ 28.742 para bens/serviços — valores corrigidos anualmente), "
        "emergência, situação de calamidade, ou quando só há um fornecedor. "
        "Oportunidade para PMEs pois o processo é ágil."
    ),
    "inexigibilidade": (
        "Inexigibilidade (Lei 14.133/2021, art. 74): Contratação direta quando há inviabilidade de competição. "
        "Casos: fornecedor exclusivo, serviços técnicos especializados de natureza singular, artistas consagrados. "
        "Requer justificativa técnica robusta."
    ),
    "diálogo competitivo": (
        "Diálogo Competitivo (Lei 14.133/2021, art. 6º, XLII): Modalidade inovadora para contratos complexos. "
        "O poder público dialoga com fornecedores para desenvolver soluções antes de abrir a licitação. "
        "Usado em infraestrutura, tecnologia e concessões complexas."
    ),
    "leilão": (
        "Leilão (Lei 14.133/2021, art. 6º, XL): Usado para venda de bens inservíveis do poder público ou concessão de direitos. "
        "Critério: maior lance. Não é para fornecedores venderem ao governo — é o governo vendendo."
    ),
}

CNAE_KEYWORDS_MAP = {
    "tecnologia": ["software", "sistema", "TI", "tecnologia da informação", "desenvolvimento", "suporte técnico", "licença", "cloud", "servidor", "infraestrutura"],
    "construção": ["obra", "construção civil", "reforma", "pavimentação", "saneamento", "edificação", "engenharia", "instalação elétrica"],
    "saúde": ["medicamento", "material hospitalar", "equipamento médico", "assistência médica", "exame", "reagente", "insumo hospitalar"],
    "limpeza": ["limpeza", "conservação", "higienização", "zeladoria", "lavanderia", "dedetização"],
    "segurança": ["vigilância", "segurança patrimonial", "monitoramento", "controle de acesso", "câmera"],
    "transporte": ["transporte", "frete", "logística", "veículo", "combustível", "manutenção veicular", "locação de veículos"],
    "alimentos": ["gêneros alimentícios", "merenda", "refeição", "marmita", "alimento", "nutrição"],
    "consultoria": ["consultoria", "assessoria", "auditoria", "treinamento", "capacitação", "curso"],
    "mobiliário": ["mobiliário", "móveis", "cadeira", "mesa", "estante", "equipamento de escritório"],
    "comunicação": ["impressão", "gráfica", "publicidade", "comunicação", "mídia", "sinalização"],
    "engenharia elétrica": ["instalação elétrica", "subestação", "transformador", "gerador", "rede elétrica", "manutenção elétrica"],
    "jardinagem": ["jardinagem", "paisagismo", "poda", "capina", "manutenção de áreas verdes"],
}


async def call_procurement_api(
    path: str,
    method: str = "GET",
    params: dict = None,
    body: dict = None,
    token: str = None,
) -> dict:
    auth_token = token or settings.proc_api_token
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    async with httpx.AsyncClient(timeout=15) as client:
        url = f"{settings.procurement_api_url}{path}"
        if method == "GET":
            resp = await client.get(url, params=params, headers=headers)
        elif method == "POST":
            resp = await client.post(url, json=body, headers=headers)
        else:
            resp = await client.request(method, url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _explain_modality_local(name: str) -> str:
    name_lower = name.lower().strip()
    for key, explanation in MODALITY_EXPLANATIONS.items():
        if key in name_lower or name_lower in key:
            return explanation
    return (
        f"Modalidade '{name}' não reconhecida. As modalidades principais da Nova Lei de Licitações (14.133/2021) são: "
        "Pregão Eletrônico, Concorrência, Diálogo Competitivo, Leilão, Dispensa e Inexigibilidade."
    )


def _suggest_keywords_local(cnae_description: str) -> str:
    desc_lower = cnae_description.lower()
    suggested = []
    for sector, keywords in CNAE_KEYWORDS_MAP.items():
        if any(term in desc_lower for term in [sector] + keywords[:2]):
            suggested.extend(keywords)
            break

    # Fallback: return generic if nothing matched
    if not suggested:
        # Extract meaningful words from description
        words = [w for w in cnae_description.split() if len(w) > 4]
        suggested = words[:5] + ["serviço", "fornecimento", "aquisição"]

    return (
        f"Com base no CNAE '{cnae_description}', sugiro as seguintes palavras-chave para busca de licitações:\n"
        + ", ".join(f'"{kw}"' for kw in suggested[:10])
        + "\n\nDica: configure essas palavras no seu perfil de monitoramento para receber alertas automáticos."
    )


async def execute_tool(name: str, args: dict, tenant_id: int = None, user_token: str = None) -> str:
    try:
        if name == "search_bids":
            params = {k: v for k, v in args.items() if v is not None}
            data = await call_procurement_api("/api/bids", params=params, token=user_token)
            return json.dumps(data, ensure_ascii=False, default=str)

        elif name == "get_bid_detail":
            data = await call_procurement_api(f"/api/bids/{args['bid_id']}", token=user_token)
            return json.dumps(data, ensure_ascii=False, default=str)

        elif name == "get_dashboard":
            data = await call_procurement_api("/api/dashboard", token=user_token)
            return json.dumps(data, ensure_ascii=False, default=str)

        elif name == "list_alerts":
            params = {k: v for k, v in args.items() if v is not None}
            data = await call_procurement_api("/api/alerts", params=params, token=user_token)
            return json.dumps(data, ensure_ascii=False, default=str)

        elif name == "trigger_keyword_sync":
            keyword = args.get("keyword", "")
            data = await call_procurement_api(
                "/api/sync/keyword",
                method="POST",
                body={"keyword": keyword},
                token=user_token,
            )
            return json.dumps(data, ensure_ascii=False, default=str)

        elif name == "create_profile":
            # Build profile payload
            profile_data = {
                "name": args.get("name", "Perfil Automático"),
                "preferred_spheres": args.get("spheres"),
                "preferred_states": args.get("states"),
                "preferred_branches": args.get("branches"),
                "keywords": args.get("keywords"),
                "min_estimated_value": args.get("min_value"),
                "max_estimated_value": args.get("max_value"),
            }
            profile_data = {k: v for k, v in profile_data.items() if v is not None}

            if not user_token:
                return json.dumps({
                    "info": "Para criar um perfil, o usuário precisa estar autenticado. "
                    "Informe ao usuário que ele pode criar perfis diretamente na aba 'Perfis' do dashboard.",
                    "profile_data": profile_data,
                })

            data = await call_procurement_api("/api/profiles", method="POST", body=profile_data, token=user_token)
            return json.dumps(data, ensure_ascii=False, default=str)

        elif name == "explain_modality":
            modality_name = args.get("modality_name", "")
            explanation = _explain_modality_local(modality_name)
            return json.dumps({"explanation": explanation})

        elif name == "suggest_keywords":
            cnae_description = args.get("cnae_description", "")
            suggestion = _suggest_keywords_local(cnae_description)
            return json.dumps({"suggestion": suggestion})

        else:
            return json.dumps({"error": f"Ferramenta '{name}' não encontrada"})

    except Exception as e:
        logger.error(f"Tool {name} error: {e}")
        return json.dumps({"error": str(e)})


class LLMUnavailableError(Exception):
    """Erro quando o orquestrador/modelo está indisponível."""
    pass


async def call_hermes(messages: list, tools: list = None) -> dict:
    payload = {
        "model": "hermes",  # model name registrado no LiteLLM orchestrator
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 2000,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.hermes_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
            )
            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {})
                    msg = err.get("message", "") if isinstance(err, dict) else str(err)
                except Exception:
                    msg = resp.text[:200]
                logger.warning(f"LLM {resp.status_code}: {msg[:200]}")
                raise LLMUnavailableError(msg)
            return resp.json()
    except LLMUnavailableError:
        raise
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        raise LLMUnavailableError(f"Conexão com orquestrador falhou: {e}")
    except Exception as e:
        raise LLMUnavailableError(f"Erro: {e}")


async def run_agent(user_message: str, tenant_id: int = None, user_token: str = None) -> str:
    context_prefix = f"[Tenant ID: {tenant_id}] " if tenant_id else ""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context_prefix + user_message},
    ]

    try:
        for _ in range(6):
            response = await call_hermes(messages, PROCUREMENT_TOOLS)
            choice = response["choices"][0]
            msg = choice["message"]
            messages.append(msg)

            if choice["finish_reason"] != "tool_calls" or not msg.get("tool_calls"):
                return msg.get("content", "")

            for tc in msg["tool_calls"]:
                args = json.loads(tc["function"]["arguments"])
                result = await execute_tool(
                    tc["function"]["name"],
                    args,
                    tenant_id=tenant_id,
                    user_token=user_token,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        return "Não consegui concluir a análise. Tente reformular sua pergunta."

    except LLMUnavailableError as e:
        # Fallback: responder sem IA, oferecendo atalhos para navegação
        logger.warning(f"LLM indisponível: {e}")
        return (
            "⚠️ O assistente de IA está temporariamente indisponível "
            "(limite de uso atingido ou serviço fora do ar).\n\n"
            "Enquanto isso, você pode:\n"
            "• Usar a **busca manual no PNCP** no Dashboard (botão *Buscar no PNCP*)\n"
            "• Ir em **Licitações** para ver o mapa e filtros interativos\n"
            "• Criar seu perfil em **Meus Perfis** para receber alertas automáticos\n\n"
            "Tente novamente em alguns minutos."
        )
    except Exception as e:
        logger.error(f"run_agent erro: {e}", exc_info=True)
        return "Ocorreu um erro ao processar sua mensagem. Tente reformular ou reconectar."


async def daily_bid_briefing():
    """Relatório diário de licitações — pode ser expandido para envio via Telegram/email."""
    try:
        summary = await run_agent(
            "Faça um resumo das licitações abertas hoje. Destaque os 3 principais ramos, "
            "total de valor em jogo e licitações que vencem em até 7 dias. Seja conciso."
        )
        logger.info(f"Daily briefing:\n{summary}")
    except Exception as e:
        logger.error(f"daily_bid_briefing error: {e}")


# ─── FastAPI ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(daily_bid_briefing, "cron", hour=8, minute=0, id="daily_briefing")
    scheduler.start()
    logger.info("Hermes Licita iniciado.")
    yield
    scheduler.shutdown()
    logger.info("Hermes Licita encerrado.")


app = FastAPI(title="Hermes Licita", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    tenant_id: int | None = None
    user_token: str | None = None  # JWT do usuário para chamadas autenticadas à API


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    response = await run_agent(
        req.message,
        tenant_id=req.tenant_id,
        user_token=req.user_token,
    )
    return ChatResponse(response=response)


@app.get("/health")
async def health():
    return {"status": "ok", "module": "hermes-procurement"}
