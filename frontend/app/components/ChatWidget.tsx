"use client";
import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Loader2, Bot, FileSearch } from "lucide-react";

type Msg = { role: "user" | "assistant"; content: string };

const WELCOME: Msg = {
  role: "assistant",
  content: "Olá! Sou o **Hermes Licita**, seu assistente de licitações. Posso ajudar você a:\n\n• Buscar licitações por área de atuação\n• Criar perfis de monitoramento\n• Explicar modalidades e termos jurídicos\n• Sugerir palavras-chave com base no seu CNAE\n• Disparar buscas específicas no PNCP\n\nComo posso ajudar hoje?",
};

function renderContent(text: string) {
  // Bold, quebra de linha, bullets simples
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n•/g, "<br/>•")
    .replace(/\n/g, "<br/>");
}

export default function ChatWidget() {
  const [open, setOpen]       = useState(false);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [msgs, setMsgs]       = useState<Msg[]>([WELCOME]);
  const [histLoaded, setHistLoaded] = useState(false);
  const bottomRef  = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLTextAreaElement>(null);
  const API = process.env.NEXT_PUBLIC_API_URL ?? "";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, open]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 120);
    if (open && !histLoaded) {
      const token = localStorage.getItem("proc_token");
      if (!token) return;
      fetch(`${API}/api/chat/history?limit=30`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(r => r.json())
        .then((hist: Msg[]) => {
          if (hist.length > 0) setMsgs([WELCOME, ...hist]);
          setHistLoaded(true);
        })
        .catch(() => setHistLoaded(true));
    }
  }, [open]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    const userMsg: Msg = { role: "user", content: text };
    setMsgs(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const token = localStorage.getItem("proc_token");
      const res = await fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message: text,
          messages: msgs.slice(-8).map(m => ({ role: m.role, content: m.content })),
        }),
      });
      const data = await res.json();
      const content = res.ok ? data.content : (data.detail ?? "Erro ao processar.");
      setMsgs(prev => [...prev, { role: "assistant", content }]);
    } catch {
      setMsgs(prev => [...prev, { role: "assistant", content: "Erro de conexão. Tente novamente." }]);
    }
    setLoading(false);
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  const unread = !open && msgs.filter(m => m.role === "assistant").length > 1;

  return (
    <>
      {/* Panel */}
      <div
        className={`fixed bottom-20 right-5 w-[360px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden z-50 transition-all duration-200 ${
          open ? "opacity-100 scale-100 pointer-events-auto" : "opacity-0 scale-95 pointer-events-none"
        }`}
        style={{ height: 500 }}
      >
        {/* Header */}
        <div className="bg-proc-900 px-4 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-proc-500 flex items-center justify-center shadow">
              <Bot size={15} className="text-white" />
            </div>
            <div>
              <div className="text-sm font-semibold text-white leading-tight">Hermes Licita</div>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[10px] text-white/50">Assistente de licitações</span>
              </div>
            </div>
          </div>
          <button onClick={() => setOpen(false)} className="text-white/50 hover:text-white transition">
            <X size={16} />
          </button>
        </div>

        {/* Quick actions */}
        <div className="px-3 py-2 bg-slate-50 border-b border-slate-100 flex gap-1.5 overflow-x-auto shrink-0">
          {[
            "Buscar licitações de TI",
            "Criar perfil de alertas",
            "O que é pregão eletrônico?",
            "Licitações abertas hoje",
          ].map(q => (
            <button key={q} onClick={() => { setInput(q); setTimeout(() => send(), 50); }}
              className="whitespace-nowrap text-[11px] px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-slate-600 hover:border-proc-300 hover:text-proc-700 transition shrink-0">
              {q}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/50">
          {msgs.map((m, i) => (
            <div key={i} className={`flex items-end gap-1.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              {m.role === "assistant" && (
                <div className="w-6 h-6 rounded-full bg-proc-100 flex items-center justify-center shrink-0 mb-0.5">
                  <Bot size={11} className="text-proc-600" />
                </div>
              )}
              <div
                className={`max-w-[84%] px-3 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-proc-500 text-white rounded-br-sm"
                    : "bg-white text-slate-700 border border-slate-200 rounded-bl-sm shadow-sm"
                }`}
                dangerouslySetInnerHTML={{ __html: renderContent(m.content) }}
              />
            </div>
          ))}
          {loading && (
            <div className="flex items-end gap-1.5">
              <div className="w-6 h-6 rounded-full bg-proc-100 flex items-center justify-center shrink-0">
                <Bot size={11} className="text-proc-600" />
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-3 py-2.5 shadow-sm flex gap-1 items-center">
                <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form onSubmit={send} className="p-3 border-t border-slate-100 flex gap-2 items-end shrink-0 bg-white">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Pergunte sobre licitações… (Enter envia)"
            disabled={loading}
            rows={1}
            className="flex-1 text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-proc-400/30 focus:border-proc-400 disabled:opacity-50 transition resize-none max-h-24"
            style={{ lineHeight: "1.4" }}
          />
          <button type="submit" disabled={loading || !input.trim()}
            className="w-9 h-9 bg-proc-500 text-white rounded-xl flex items-center justify-center hover:bg-proc-600 disabled:opacity-40 transition shrink-0">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </form>
      </div>

      {/* Toggle button */}
      <button
        onClick={() => setOpen(v => !v)}
        className={`fixed bottom-5 right-5 text-white rounded-2xl shadow-xl flex items-center justify-center z-50 transition-all duration-200 hover:scale-105 ${
          open ? "bg-slate-700 hover:bg-slate-800" : "bg-proc-500 hover:bg-proc-600"
        }`}
        style={{ width: 52, height: 52 }}
        title="Hermes Licita"
      >
        {open ? <X size={20} /> : <MessageCircle size={22} />}
        {unread && !open && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[9px] font-bold flex items-center justify-center">
            ●
          </span>
        )}
      </button>
    </>
  );
}
