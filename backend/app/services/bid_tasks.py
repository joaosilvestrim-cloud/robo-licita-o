"""Gerador de tarefas do 'negócio' (checklist com prazos).

A partir da data de abertura da licitação, monta as etapas que a empresa precisa
cumprir, com prazos em DIAS ÚTEIS (não considera feriados — o edital manda no
prazo final). Baseado na Lei 14.133/2021 (impugnação/esclarecimento art. 164,
recursos art. 165).
"""
from datetime import date, timedelta
from typing import Optional


def add_business_days(base: date, n: int) -> date:
    """Soma (ou subtrai, se n<0) n dias úteis a partir de base, pulando fim de semana."""
    if base is None:
        return None
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    d = base
    while remaining > 0:
        d = d + timedelta(days=step)
        if d.weekday() < 5:  # 0-4 seg-sex
            remaining -= 1
    return d


# Modelo padrão de tarefas. offset = dias úteis relativo à abertura.
_TEMPLATE = [
    ("Preparação",  "Analisar edital e termo de referência",        "analise",       -5, False),
    ("Preparação",  "Solicitar esclarecimentos / impugnar o edital", "impugnacao",    -3, True),
    ("Preparação",  "Conferir habilitação e atestados exigidos",     "habilitacao",   -2, False),
    ("Preparação",  "Montar proposta e planilha de preços",          "proposta",      -1, False),
    ("Disputa",     "Participar da sessão de disputa",               "disputa",        0, True),
    ("Disputa",     "Enviar documentos de habilitação",              "docs",           0, False),
    ("Pós-disputa", "Manifestar intenção de recurso (na sessão)",    "intencao",       0, False),
    ("Pós-disputa", "Enviar recurso / contrarrazão",                 "recurso",        3, True),
]


def build_tasks(opening: Optional[date]) -> list[dict]:
    """Retorna a lista de tarefas (dicts) com prazos calculados da abertura."""
    tasks = []
    for i, (section, title, kind, offset, agenda) in enumerate(_TEMPLATE):
        due = add_business_days(opening, offset) if opening else None
        tasks.append({
            "section": section,
            "title": title,
            "kind": kind,
            "due_date": due,
            "on_agenda": agenda,
            "ordem": i,
        })
    return tasks
