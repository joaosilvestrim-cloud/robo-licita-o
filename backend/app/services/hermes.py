"""Assistente Sonar — agente de IA sobre licitações, via Groq (OpenAI-compatible).

Roda dentro do próprio backend. As ferramentas chamam a API interna usando o
JWT do usuário, respeitando o tenant. Se GROQ_API_KEY estiver vazio, devolve uma
mensagem amigável com atalhos manuais.
"""
import json
import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o Assistente Sonar, o assistente de IA de licitações públicas da Drive Data.

Sua especialidade é ajudar empresas brasileiras a encontrar e ganhar licitações públicas (federais, estaduais e municipais) publicadas no PNCP e em outros portais oficiais.

Você pode:
- Buscar licitações abertas por palavra-chave, estado, esfera, ramo e valor
- Explicar termos e modalidades de licitação (Pregão Eletrônico, Concorrência, Dispensa, etc.)
- Sugerir palavras-chave de busca com base no CNAE da empresa
- Detalhar licitações específicas (objeto, prazo, valor estimado, órgão)
- Ajudar a criar perfis de monitoramento
- Analisar alertas compatíveis com o perfil do usuário
- Disparar sincronizações do PNCP para novos termos

Sempre responda em português, de forma clara, direta e com foco em dados concretos.
Valores no formato brasileiro (R$ 1.234.567,89). Datas em DD/MM/AAAA.
Priorize licitações abertas e com prazo próximo quando relevante.
Use as ferramentas disponíveis para consultar dados reais antes de responder."""

PROCUREMENT_TOOLS = [
    {"type": "function", "function": {
        "name": "search_bids",
        "description": "Busca licitações com filtros. Use para perguntas sobre licitações disponíveis.",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Palavras-chave no título/objeto"},
            "sphere": {"type": "string", "enum": ["federal", "estadual", "municipal"]},
            "state": {"type": "string", "description": "UF, ex: SP, RJ, MG"},
            "city": {"type": "string"},
            "status": {"type": "string", "enum": ["aberta", "andamento", "encerrada", "programada"]},
            "limit": {"type": "integer", "default": 10},
            "min_value": {"type": "number"},
            "max_value": {"type": "number"},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "get_bid_detail",
        "description": "Detalhes de uma licitação pelo ID interno",
        "parameters": {"type": "object", "properties": {
            "bid_id": {"type": "integer"},
        }, "required": ["bid_id"]},
    }},
    {"type": "function", "function": {
        "name": "get_dashboard",
        "description": "KPIs: total de licitações, valor em jogo, distribuição por esfera/ramo",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "list_alerts",
        "description": "Lista alertas compatíveis com o perfil do usuário",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["novo", "visto", "favorito", "descartado"]},
            "limit": {"type": "integer", "default": 5},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "trigger_keyword_sync",
        "description": "Dispara busca no PNCP por uma palavra-chave, trazendo licitações novas",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"},
        }, "required": ["keyword"]},
    }},
    {"type": "function", "function": {
        "name": "create_profile",
        "description": "Cria um perfil de monitoramento (filtros automáticos p/ alertas)",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "spheres": {"type": "string", "description": "Esferas separadas por vírgula"},
            "states": {"type": "string", "description": "UFs separadas por vírgula"},
            "branches": {"type": "string", "description": "Ramos separados por vírgula"},
            "keywords": {"type": "string", "description": "Palavras-chave separadas por vírgula"},
            "min_value": {"type": "number"},
            "max_value": {"type": "number"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "explain_modality",
        "description": "Explica uma modalidade de licitação (conhecimento jurídico local)",
        "parameters": {"type": "object", "properties": {
            "modality_name": {"type": "string"},
        }, "required": ["modality_name"]},
    }},
    {"type": "function", "function": {
        "name": "suggest_keywords",
        "description": "Sugere palavras-chave a partir do CNAE/atividade da empresa",
        "parameters": {"type": "object", "properties": {
            "cnae_description": {"type": "string"},
        }, "required": ["cnae_description"]},
    }},
]

MODALITY_EXPLANATIONS = {
    "pregão": "Pregão (Lei 14.133/2021): modalidade para bens e serviços comuns. No eletrônico, disputa em sessão pública com lances sucessivos. É a mais comum, favorável a PMEs. Critério: menor preço ou maior desconto. Sem limite de valor.",
    "concorrência": "Concorrência (Lei 14.133/2021): obras, engenharia de grande porte e compras de alto valor. Ampla publicidade e prazo mínimo. Critérios: menor preço, melhor técnica, técnica e preço, maior retorno econômico ou maior desconto.",
    "tomada de preços": "Tomada de Preços: modalidade da Lei 8.666/93 para valores intermediários. Na Nova Lei foi substituída pela Concorrência. Ainda aparece em contratos antigos.",
    "convite": "Convite: modalidade da Lei 8.666/93 para pequenos valores. Substituído pelo Diálogo Competitivo ou Concorrência simplificada na Nova Lei.",
    "dispensa": "Dispensa (Lei 14.133/2021, art. 75): contratação direta sem licitação em casos específicos: valor baixo, emergência, calamidade, fornecedor único. Processo ágil, oportunidade para PMEs.",
    "inexigibilidade": "Inexigibilidade (Lei 14.133/2021, art. 74): contratação direta quando há inviabilidade de competição (fornecedor exclusivo, serviço técnico singular). Requer justificativa robusta.",
    "diálogo competitivo": "Diálogo Competitivo (Lei 14.133/2021): para contratos complexos. O poder público dialoga com fornecedores para desenvolver a solução antes de abrir a licitação.",
    "leilão": "Leilão (Lei 14.133/2021): venda de bens do poder público ou concessão de direitos. Critério: maior lance. É o governo vendendo, não comprando.",
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
}


def _self_base() -> str:
    return f"http://127.0.0.1:{settings.port}"


async def _call_api(path: str, method: str = "GET", params: dict = None,
                    body: dict = None, token: str = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=20) as client:
        url = f"{_self_base()}{path}"
        if method == "GET":
            resp = await client.get(url, params=params, headers=headers)
        else:
            resp = await client.request(method, url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _explain_modality_local(name: str) -> str:
    n = (name or "").lower().strip()
    for key, exp in MODALITY_EXPLANATIONS.items():
        if key in n or n in key:
            return exp
    return ("Modalidade não reconhecida. As principais da Lei 14.133/2021 são: "
            "Pregão Eletrônico, Concorrência, Diálogo Competitivo, Leilão, Dispensa e Inexigibilidade.")


def _suggest_keywords_local(desc: str) -> str:
    d = (desc or "").lower()
    suggested = []
    for sector, kws in CNAE_KEYWORDS_MAP.items():
        if any(term in d for term in [sector] + kws[:2]):
            suggested = kws
            break
    if not suggested:
        words = [w for w in (desc or "").split() if len(w) > 4]
        suggested = words[:5] + ["serviço", "fornecimento", "aquisição"]
    return ("Com base em '" + (desc or "") + "', sugiro estas palavras-chave: "
            + ", ".join(f'"{k}"' for k in suggested[:10])
            + ". Configure-as num perfil para receber alertas automáticos.")


async def execute_tool(name: str, args: dict, user_token: str = None) -> str:
    try:
        if name == "search_bids":
            params = {k: v for k, v in args.items() if v is not None}
            return json.dumps(await _call_api("/api/bids", params=params, token=user_token), ensure_ascii=False, default=str)
        if name == "get_bid_detail":
            return json.dumps(await _call_api(f"/api/bids/{args['bid_id']}", token=user_token), ensure_ascii=False, default=str)
        if name == "get_dashboard":
            return json.dumps(await _call_api("/api/dashboard", token=user_token), ensure_ascii=False, default=str)
        if name == "list_alerts":
            params = {k: v for k, v in args.items() if v is not None}
            return json.dumps(await _call_api("/api/alerts", params=params, token=user_token), ensure_ascii=False, default=str)
        if name == "trigger_keyword_sync":
            return json.dumps(await _call_api("/api/sync/keyword", method="POST",
                              body={"keyword": args.get("keyword", "")}, token=user_token), ensure_ascii=False, default=str)
        if name == "create_profile":
            profile = {
                "name": args.get("name", "Perfil Automático"),
                "preferred_spheres": args.get("spheres"),
                "preferred_states": args.get("states"),
                "preferred_branches": args.get("branches"),
                "keywords": args.get("keywords"),
                "min_estimated_value": args.get("min_value"),
                "max_estimated_value": args.get("max_value"),
            }
            profile = {k: v for k, v in profile.items() if v is not None}
            return json.dumps(await _call_api("/api/profiles", method="POST", body=profile, token=user_token), ensure_ascii=False, default=str)
        if name == "explain_modality":
            return json.dumps({"explanation": _explain_modality_local(args.get("modality_name", ""))}, ensure_ascii=False)
        if name == "suggest_keywords":
            return json.dumps({"suggestion": _suggest_keywords_local(args.get("cnae_description", ""))}, ensure_ascii=False)
        return json.dumps({"error": f"Ferramenta '{name}' não encontrada"})
    except Exception as e:
        logger.error(f"Tool {name} erro: {e}")
        return json.dumps({"error": str(e)})


async def _call_groq(messages: list, tools: list = None) -> dict:
    payload = {"model": settings.groq_model, "messages": messages, "temperature": 0.4, "max_tokens": 1800}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.groq_base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        )
        resp.raise_for_status()
        return resp.json()


_UNAVAILABLE = (
    "⚠️ O Assistente Sonar ainda não está configurado (falta a chave do Groq).\n\n"
    "Enquanto isso, você pode:\n"
    "• Buscar no PNCP pelo Dashboard\n"
    "• Ver o mapa e os filtros em **Licitações**\n"
    "• Criar seu perfil em **Meus Perfis** para receber alertas."
)


async def run_agent(user_message: str, user_token: str = None) -> str:
    if not settings.groq_api_key:
        return _UNAVAILABLE

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    try:
        for _ in range(6):
            response = await _call_groq(messages, PROCUREMENT_TOOLS)
            choice = response["choices"][0]
            msg = choice["message"]
            messages.append(msg)

            tool_calls = msg.get("tool_calls")
            if choice.get("finish_reason") != "tool_calls" or not tool_calls:
                return msg.get("content") or "Não consegui gerar uma resposta. Tente reformular."

            for tc in tool_calls:
                raw = tc["function"].get("arguments") or "{}"
                try:
                    args = json.loads(raw)
                except Exception:
                    args = {}
                result = await execute_tool(tc["function"]["name"], args, user_token=user_token)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        return "Consultei bastante coisa mas não fechei a resposta. Tente reformular a pergunta."
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            detail = (e.response.text or "")[:160]
        logger.warning(f"Groq {e.response.status_code}: {detail}")
        if e.response.status_code in (401, 403):
            return "⚠️ A chave do Groq parece inválida. Verifique GROQ_API_KEY no servidor."
        if e.response.status_code == 429:
            return "⚠️ Limite de uso do Groq atingido no momento. Tente de novo em alguns minutos."
        return "⚠️ O assistente está com dificuldade para responder agora. Tente novamente em instantes."
    except Exception as e:
        logger.error(f"run_agent erro: {e}", exc_info=True)
        return "Ocorreu um erro ao processar sua mensagem. Tente reformular."
