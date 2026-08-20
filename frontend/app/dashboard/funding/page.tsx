"use client";
import { useEffect, useState, useCallback } from "react";
import { Sprout, Loader2, Globe, Clock, Landmark, Layers, Filter } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmtDate(d: string | null | undefined) {
  if (!d) return "sem prazo definido";
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

function Prazo({ days }: { days: number | null }) {
  const base = "inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-full";
  if (days == null) return <span className={`${base} bg-slate-100 text-slate-500`}><Clock size={11} /> Sem prazo</span>;
  if (days < 0)    return <span className={`${base} bg-slate-100 text-slate-400`}><Clock size={11} /> encerrada</span>;
  const label = days <= 60 ? `fecha em ${days}d` : `~${Math.round(days / 30)} meses`;
  if (days <= 15)  return <span className={`${base} bg-red-100 text-red-700`}><Clock size={11} /> {label}</span>;
  if (days <= 45)  return <span className={`${base} bg-amber-100 text-amber-700`}><Clock size={11} /> {label}</span>;
  return <span className={`${base} bg-proc-50 text-proc-700`}><Clock size={11} /> {label}</span>;
}

export default function FundingPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [onlyTi, setOnlyTi] = useState(true);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API}/api/funding/open?only_ti=${onlyTi}&limit=50`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setItems(d.data ?? []); setTotal(d.total ?? 0); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, onlyTi]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Sprout size={22} className="text-emerald-500" /> Fomento
        </h1>
        <p className="text-slate-500 text-sm mt-1 max-w-2xl">
          Chamadas de <strong>fomento à pesquisa e inovação</strong> abertas. Para uma consultoria de dados,
          o alvo é o <strong>PIPE da FAPESP</strong> — dinheiro não reembolsável pra desenvolver tecnologia.
          O radar prioriza o <strong>prazo mais próximo</strong>.
        </p>
      </div>

      <div className="flex items-center gap-2 mb-5">
        <Filter size={13} className="text-slate-400" />
        <button onClick={() => setOnlyTi(true)}
          className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition ${
            onlyTi ? "text-white dd-gradient border-transparent shadow-sm" : "bg-white border-slate-200 text-slate-500 hover:border-proc-300"
          }`}>
          Aderentes a TI/Dados
        </button>
        <button onClick={() => setOnlyTi(false)}
          className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition ${
            !onlyTi ? "text-white dd-gradient border-transparent shadow-sm" : "bg-white border-slate-200 text-slate-500 hover:border-proc-300"
          }`}>
          Todas as chamadas
        </button>
        {total > 0 && <span className="text-xs text-slate-400 ml-1">{total} abertas</span>}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-proc-400" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <Sprout size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium text-slate-500">Nenhuma chamada nessa visão ainda.</p>
          <p className="text-xs mt-1">O radar de fomento roda 2x ao dia lendo a FAPESP. Tente ver “Todas as chamadas”.</p>
        </div>
      ) : (
        <div className="space-y-3 dd-stagger">
          {items.map(f => (
            <div key={f.id} className="bg-white rounded-2xl border border-slate-100 shadow-card p-5 hover:shadow-card-hover transition">
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <Prazo days={f.days_left} />
                <span className="text-[11px] text-slate-400">prazo: {fmtDate(f.deadline)}</span>
                <span className="text-[11px] text-emerald-600 flex items-center gap-0.5 font-medium"><Landmark size={11} /> {f.agency}</span>
                {f.is_ti && <span className="text-[10px] font-semibold text-white bg-proc-500 px-1.5 py-0.5 rounded">TI/Dados</span>}
              </div>
              <h3 className="text-sm font-semibold text-slate-800 leading-snug">{f.title}</h3>
              {(f.modality || f.area) && (
                <div className="flex items-start gap-1.5 text-[12px] text-slate-400 mt-2">
                  <Layers size={12} className="mt-0.5 shrink-0" />
                  <span className="line-clamp-2">{[f.modality, f.area].filter(Boolean).join(" · ")}</span>
                </div>
              )}
              {f.url && (
                <div className="flex justify-end mt-3 pt-3 border-t border-slate-50">
                  <a href={f.url} target="_blank" rel="noopener noreferrer"
                    className="text-xs text-proc-600 hover:text-proc-700 font-medium flex items-center gap-1">
                    <Globe size={12} /> Ver chamada na FAPESP
                  </a>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
