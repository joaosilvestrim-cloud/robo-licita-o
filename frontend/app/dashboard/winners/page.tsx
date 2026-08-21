"use client";
import { useEffect, useState, useCallback } from "react";
import { Trophy, Building2, MapPin, Loader2, Globe, Award, Medal, Search, Package } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "valor n/d";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}
function fmtFull(v: number | null | undefined) {
  if (!v) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}
function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}
function pncpUrl(externalId: string) {
  const m = (externalId || "").match(/^(\d+)-(\d+)-0*(\d+)\/(\d+)$/);
  if (!m) return null;
  return `https://pncp.gov.br/app/editais/${m[1]}/${m[4]}/${m[3]}`;
}

export default function WinnersPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [lista, setLista] = useState<any[]>([]);
  const [ranking, setRanking] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [months, setMonths] = useState(0);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    const params = new URLSearchParams({ months: String(months), limit: "25" });
    if (q.trim()) params.set("q", q.trim());
    fetch(`${API}/api/winners?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setLista(d.lista ?? []); setRanking(d.ranking ?? []); setTotal(d.total ?? 0); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, months, q]);

  useEffect(() => { const t = setTimeout(load, q ? 350 : 0); return () => clearTimeout(t); }, [load, q]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Trophy size={22} className="text-amber-500" /> Vencedores
        </h1>
        <p className="text-slate-500 text-sm mt-1 max-w-2xl">
          Quem <strong>ganhou</strong> as licitações de TI &amp; Dados e por quanto. Ao lado, o <strong>ranking dos concorrentes</strong> que
          mais vencem no nicho. Use como benchmark de preço e mapa da concorrência. Dados públicos do PNCP após a homologação.
        </p>
      </div>

      <div className="flex items-center gap-2 mb-5 flex-wrap">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Buscar concorrente ou objeto"
            className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-64 focus:outline-none focus:border-proc-300" />
        </div>
        <span className="text-xs text-slate-400 ml-1">Homologadas em:</span>
        {[{ v: 0, l: "tudo" }, { v: 6, l: "6 meses" }, { v: 12, l: "12 meses" }].map(o => (
          <button key={o.v} onClick={() => setMonths(o.v)}
            className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition ${
              months === o.v ? "text-white dd-gradient border-transparent shadow-sm" : "bg-white border-slate-200 text-slate-500 hover:border-proc-300"
            }`}>
            {o.l}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-proc-400" /></div>
      ) : total === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <Trophy size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium text-slate-500">Ainda estamos apurando os vencedores.</p>
          <p className="text-xs mt-1">O radar de vencedores roda 2x ao dia sobre as licitações de TI já homologadas. Vai populando aos poucos.</p>
        </div>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          {/* lista: quem ganhou o quê */}
          <div className="lg:col-span-2 space-y-3">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Quem ganhou o quê · {total} resultados</div>
            {lista.map(w => {
              const url = pncpUrl(w.external_id);
              return (
                <div key={w.id} className="bg-white rounded-2xl border border-slate-100 shadow-card p-4 hover:shadow-card-hover transition">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                      <Award size={11} /> Vencedor
                    </span>
                    {w.state && <span className="text-[11px] text-slate-400 flex items-center gap-0.5"><MapPin size={11} /> {w.state}</span>}
                    <span className="text-[11px] text-slate-400">homolog. {fmtDate(w.homologated_at)}</span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800 leading-snug line-clamp-2">{w.bid_title}</h3>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400 mt-2 flex-wrap">
                    <span className="flex items-center gap-1"><Building2 size={12} /> {w.organ_name ?? "—"}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3 mt-3 pt-3 border-t border-slate-50">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-800 truncate">{w.supplier_name ?? "—"}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        CNPJ {w.supplier_document}{w.porte ? ` · ${w.porte}` : ""} · {w.items_won} {w.items_won === 1 ? "item" : "itens"}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-bold text-slate-900">{fmt(w.valor_total)}</div>
                      {url && (
                        <a href={url} target="_blank" rel="noopener noreferrer"
                          className="text-[11px] text-proc-600 hover:text-proc-700 font-medium inline-flex items-center gap-0.5">
                          <Globe size={11} /> PNCP
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* ranking de concorrentes */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl border border-slate-100 shadow-card overflow-hidden sticky top-4">
              <div className="bg-slate-900 px-4 py-3 flex items-center gap-2 text-white">
                <Medal size={15} />
                <span className="text-sm font-semibold">Ranking de concorrentes</span>
              </div>
              <div className="p-3 space-y-1.5">
                {ranking.length === 0 && <p className="text-xs text-slate-400 p-3">Sem dados suficientes ainda.</p>}
                {ranking.map((r, i) => (
                  <div key={r.supplier_document} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-slate-50">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                      i === 0 ? "bg-amber-400 text-white" : i === 1 ? "bg-slate-300 text-white" : i === 2 ? "bg-amber-700 text-white" : "bg-slate-100 text-slate-500"
                    }`}>{i + 1}</div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-slate-800 truncate">{r.supplier_name}</div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-1">
                        <Package size={9} /> {r.licitacoes} {r.licitacoes === 1 ? "licitação" : "licitações"}{r.porte ? ` · ${r.porte}` : ""}
                      </div>
                    </div>
                    <div className="text-xs font-semibold text-slate-900 shrink-0" title={fmtFull(r.total_value)}>{fmt(r.total_value)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
