"use client";
import { useState, useRef, useEffect } from "react";
import { X, Send, Loader2 } from "lucide-react";

type Msg = { role: "user" | "assistant"; content: string };

const WELCOME: Msg = {
  role: "assistant",
  content: "Olá! 👋 Sou o **Assistente Sonar**, da Drive Data. Consigo buscar licitações reais pra você, explicar termos da Lei 14.133, sugerir palavras-chave pelo seu CNAE e até criar perfis de monitoramento.\n\nComo posso ajudar hoje?",
};

function renderContent(text: string) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n•/g, "<br/>•")
    .replace(/\n/g, "<br/>");
}

// Avatar "sonar": círculo em degradê com ondas de radar
function SonarAvatar({ size = 32, glow = false }: { size?: number; glow?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"
      style={glow ? { filter: "drop-shadow(0 0 6px rgba(63,208,124,.65))" } : undefined}>
      <defs>
        <linearGradient id="ddAv" x1="4" y1="4" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3FD07C" /><stop offset=".5" stopColor="#17B6C6" /><stop offset="1" stopColor="#1E86E0" />
        </linearGradient>
      </defs>
      <circle cx="20" cy="20" r="20" fill="url(#ddAv)" />
      <g fill="none" stroke="#fff" strokeWidth="2.3" strokeLinecap="round">
        <circle cx="14" cy="26" r="2.1" fill="#fff" stroke="none" />
        <path d="M14 20.5 A5.5 5.5 0 0 1 19.5 26" opacity=".95" />
        <path d="M14 15 A11 11 0 0 1 25 26" opacity=".7" />
        <path d="M14 9.5 A16.5 16.5 0 0 1 30.5 26" opacity=".45" />
      </g>
    </svg>
  );
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
      fetch(`${API}/api/chat/history?limit=30`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json())
        .then((hist: Msg[]) => {
          if (hist.length > 0) setMsgs([WELCOME, ...hist]);
          setHistLoaded(true);
        })
        .catch(() => setHistLoaded(true));
    }
  }, [open]);

  async function send(e?: React.FormEvent, forced?: string) {
    e?.preventDefault();
    const text = (forced ?? input).trim();
    if (!text || loading) return;
    setMsgs(prev => [...prev, { role: "user", content: text }]);
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
        className={`fixed bottom-24 right-5 w-[370px] bg-white rounded-3xl shadow-2xl border border-slate-200/70 flex flex-col overflow-hidden z-50 transition-all duration-250 origin-bottom-right ${
          open ? "opacity-100 scale-100 pointer-events-auto" : "opacity-0 scale-90 pointer-events-none"
        }`}
        style={{ height: 520 }}
      >
        {/* Header */}
        <div className="dd-gradient px-4 py-3.5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="rounded-full ring-2 ring-white/40">
              <SonarAvatar size={38} />
            </div>
            <div>
              <div className="text-sm font-bold text-white leading-tight">Assistente Sonar</div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_6px_#fff] animate-pulse" />
                <span className="text-[10.5px] text-white/80">online · por Drive Data</span>
              </div>
            </div>
          </div>
          <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white transition p-1 rounded-lg hover:bg-white/10">
            <X size={17} />
          </button>
        </div>

        {/* Quick actions */}
        <div className="px-3 py-2 bg-slate-50 border-b border-slate-100 flex gap-1.5 overflow-x-auto shrink-0">
          {[
            "Licitações de BI e dados",
            "Criar perfil de alertas",
            "O que é pregão eletrônico?",
            "Abertas hoje",
          ].map(q => (
            <button key={q} onClick={() => send(undefined, q)}
              className="whitespace-nowrap text-[11px] px-2.5 py-1 bg-white border border-slate-200 rounded-full text-slate-600 hover:border-proc-300 hover:text-proc-700 hover:shadow-sm transition shrink-0">
              {q}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/60">
          {msgs.map((m, i) => (
            <div key={i} className={`dd-up flex items-end gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              {m.role === "assistant" && <SonarAvatar size={24} />}
              <div
                className={`max-w-[82%] px-3.5 py-2.5 text-[13.5px] leading-relaxed ${
                  m.role === "user"
                    ? "dd-gradient text-white rounded-2xl rounded-br-md shadow-sm"
                    : "bg-white text-slate-700 border border-slate-200 rounded-2xl rounded-bl-md shadow-sm"
                }`}
                dangerouslySetInnerHTML={{ __html: renderContent(m.content) }}
              />
            </div>
          ))}
          {loading && (
            <div className="dd-up flex items-end gap-2">
              <SonarAvatar size={24} />
              <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-3.5 py-3 shadow-sm flex gap-1 items-center">
                <span className="w-1.5 h-1.5 bg-proc-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-proc-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-proc-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
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
            placeholder="Pergunte sobre licitações…"
            disabled={loading}
            rows={1}
            className="flex-1 text-sm border border-slate-200 rounded-2xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-proc-400/30 focus:border-proc-400 disabled:opacity-50 transition resize-none max-h-24"
            style={{ lineHeight: "1.4" }}
          />
          <button type="submit" disabled={loading || !input.trim()}
            className="w-10 h-10 dd-gradient text-white rounded-2xl flex items-center justify-center hover:opacity-90 disabled:opacity-40 transition shrink-0 shadow">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </form>
      </div>

      {/* Toggle button */}
      <button
        onClick={() => setOpen(v => !v)}
        className="fixed bottom-5 right-5 rounded-full shadow-xl flex items-center justify-center z-50 transition-transform duration-200 hover:scale-105"
        style={{ width: 58, height: 58 }}
        title="Assistente Sonar"
      >
        {open ? (
          <span className="w-full h-full rounded-full bg-slate-800 flex items-center justify-center text-white">
            <X size={22} />
          </span>
        ) : (
          <>
            <span className="absolute inset-0 rounded-full dd-gradient opacity-40 animate-ping" style={{ animationDuration: "2.4s" }} />
            <SonarAvatar size={58} glow />
          </>
        )}
        {unread && !open && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 border-2 border-white rounded-full" />
        )}
      </button>
    </>
  );
}
