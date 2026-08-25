"""Converse com o edital — responde perguntas com base no texto do edital.

Versão pragmática (sem vetor/RAG pesado): baixa o PDF do edital no PNCP, extrai
o texto e injeta um trecho no prompt do Groq junto com a pergunta. Funciona bem
para editais de tamanho normal e não exige banco vetorial (protege o Render).
"""
import io
import logging
import httpx
from app.config import settings
from app.services.bid_items import get_files

logger = logging.getLogger(__name__)

_MAX_PDF_BYTES = 9 * 1024 * 1024   # ignora PDFs gigantes
_MAX_CHARS = 14000                 # trecho enviado ao modelo (limite de tokens do Groq free)
_UA = {"User-Agent": "Mozilla/5.0 (compatible; SonarBot/1.0)"}

# palavras que indicam o documento principal (edital / termo de referência)
_PREF = ("edital", "termo de refer", "termo de refer", "aviso", "referência")


def _pick_file(files: list[dict]) -> dict | None:
    if not files:
        return None
    pdfs = [f for f in files if (f.get("url") and str(f.get("titulo", "")).lower().endswith(".pdf"))] or \
           [f for f in files if f.get("url")]
    for f in pdfs:
        t = (f.get("titulo") or "").lower()
        if any(p in t for p in _PREF):
            return f
    return pdfs[0] if pdfs else None


async def get_edital_text(external_id: str) -> dict:
    """Baixa e extrai o texto do documento principal do edital."""
    data = await get_files(external_id)
    files = data.get("files") or []
    chosen = _pick_file(files)
    if not chosen:
        return {"ok": False, "reason": "sem_arquivo", "text": "", "titulo": None}

    try:
        from pypdf import PdfReader
    except Exception:
        return {"ok": False, "reason": "sem_pypdf", "text": "", "titulo": chosen.get("titulo")}

    try:
        async with httpx.AsyncClient(timeout=25, verify=False, follow_redirects=True) as client:
            resp = await client.get(chosen["url"], headers=_UA)
            if resp.status_code != 200:
                return {"ok": False, "reason": f"http_{resp.status_code}", "text": "", "titulo": chosen.get("titulo")}
            content = resp.content
        if len(content) > _MAX_PDF_BYTES:
            return {"ok": False, "reason": "pdf_grande", "text": "", "titulo": chosen.get("titulo")}
        reader = PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
            if sum(len(p) for p in parts) > _MAX_CHARS:
                break
        text = "\n".join(parts).strip()
    except Exception as e:
        logger.warning(f"get_edital_text erro {external_id}: {e}")
        return {"ok": False, "reason": "erro_leitura", "text": "", "titulo": chosen.get("titulo")}

    if not text:
        return {"ok": False, "reason": "sem_texto", "text": "", "titulo": chosen.get("titulo"),
                "url": chosen.get("url")}
    return {"ok": True, "text": text[:_MAX_CHARS], "titulo": chosen.get("titulo"), "url": chosen.get("url")}


_SYS = (
    "Você é o assistente do Sonar (Drive Data) especializado em leitura de editais de "
    "licitação. Responda a pergunta do usuário USANDO SOMENTE o trecho do edital fornecido. "
    "Se a resposta não estiver no trecho, diga que não encontrou essa informação no documento "
    "e sugira conferir o edital completo. Seja objetivo, cite números, prazos e itens quando houver. "
    "Responda em português."
)


async def ask_edital(text: str, question: str) -> str:
    if not settings.groq_api_key:
        return "O assistente de IA não está configurado (falta a chave do Groq)."
    messages = [
        {"role": "system", "content": _SYS},
        {"role": "user", "content": f"TRECHO DO EDITAL:\n\"\"\"\n{text}\n\"\"\"\n\nPERGUNTA: {question}"},
    ]
    payload = {"model": settings.groq_model, "messages": messages, "temperature": 0.2, "max_tokens": 900}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.groq_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
            if resp.status_code != 200:
                logger.warning(f"ask_edital groq {resp.status_code}: {resp.text[:300]}")
                return f"[debug groq {resp.status_code}] {resp.text[:200]}"
            return resp.json()["choices"][0]["message"]["content"] or "Não consegui responder."
    except Exception as e:
        logger.warning(f"ask_edital groq erro: {e}")
        return f"[debug erro] {type(e).__name__}: {str(e)[:200]}"
