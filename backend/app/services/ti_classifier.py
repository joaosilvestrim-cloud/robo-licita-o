"""Classificador de aderência a TI & Dados (foco Drive Data).

Usado no momento do sync para gravar is_ti/ti_score na licitação (pré-cálculo),
deixando as buscas de TI instantâneas (consulta indexada em vez de pontuar
milhares de linhas a cada request).
"""
import re

# Sinais FORTES de TI/dados: presença de qualquer um já classifica.
_IT_STRONG = [
    "software", "sistema de informação", "sistema informatizado", "sistemas de informação",
    "tecnologia da informação", "informática", "banco de dados", "base de dados",
    "business intelligence", "power bi", "análise de dados", "ciência de dados",
    "big data", "data warehouse", "data lake", "data center", "datacenter",
    "computação em nuvem", "cloud", "erp", "crm", "geoprocessamento", "sig ",
    "inteligência artificial", "machine learning", "aprendizado de máquina",
    "desenvolvimento de sistema", "desenvolvimento de software", "fábrica de software",
    "segurança da informação", "cibersegurança", "assinatura eletrônica",
    "certificado digital", "dashboard", "etl", "api", "governança de dados",
    "licença de software", "licenciamento de software", "sistema de gestão",
    "portal web", "aplicativo", "aplicação web", "ti ", " ti",
]
# Sinais FRACOS: reforçam relevância, mas só valem quando há pelo menos 1 forte.
_IT_WEAK = [
    "dados", "servidor", "servidores", "infraestrutura de ti", "rede de computadores",
    "firewall", "backup", "storage", "hospedagem", "datacenter", "automação",
    "integração de sistemas", "suporte técnico", "helpdesk", "service desk",
    "link de internet", "conectividade", "telecomunicações", "computador",
    "notebook", "microcomputador", "impressora", "outsourcing de impressão",
    "scanner", "equipamento de informática", "nuvem", "portal", "website",
]


def _mk_re(words):
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(w.strip()) for w in words) + r")(?!\w)", re.IGNORECASE)


_STRONG_RE = _mk_re(_IT_STRONG)
_WEAK_RE = _mk_re(_IT_WEAK)


def counts(title, description=None, category=None, branch=None) -> tuple[int, int]:
    text = f"{title or ''} {description or ''} {category or ''} {branch or ''}".lower()
    strong = len({m.group(0).lower() for m in _STRONG_RE.finditer(text)})
    weak = len({m.group(0).lower() for m in _WEAK_RE.finditer(text)})
    return strong, weak


def classify(title, description=None, category=None, branch=None) -> tuple[bool, int]:
    """Retorna (is_ti, ti_score). is_ti = tem ao menos 1 sinal forte."""
    strong, weak = counts(title, description, category, branch)
    return (strong >= 1), (strong * 3 + weak)
