"use client";
import { useEffect, useState, useCallback } from "react";
import { FileClock, Building2, MapPin, Loader2, Globe, Award, Clock } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "valor n/d";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}
function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}
// link para o edital/contrato no PNCP a partir do numeroControlePncpCompra
function pncpUrl(externalId: string) {
  const compra = (externalId || "").split("::")[0];
  const m = compra.match(/^(\d+)-(\d+)-0*(\d+)\/(\d+)$/);
  if (!m) return null;
  return `https://pncp.gov.br/app/editais/${m[1]}/${m[4]}/${m[3]}`;
}

function Prazo({ days }: { days: number | null }) {
  const base = "inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-full";
  if (days == null) return <span className={`${base} bg-slate-100 text-slate-500`}><Clock size={11} /> Sem data</span>;
  const label = days <= 60 ? `vence em ${days}d` : `~${Math.round(days / 30)} meses`;
  if (days <= 30)  return <span className={`${base} bg-red-100 text-red-700`}><Clock size={11} /> {label}</span>;
  if (days <= 120) return <span className={`${base} bg-amber-100 text-amber-700`}><Clock size={11} /> {label}</span>;
  return <span className={`${base} bg-proc-50 text-proc-700`}><Clock size={11} /> {label}</span>;
}

export default function ContractsPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [months, setMonths] = useState(12);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API}/api/contracts/expiring?months=${months}&limit=40`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setItems(d.data ?? []); setTotal(d.total ?? 0); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, months]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <FileClock size={22} className="text-proc-500" /> Recontratação
          </h1>
          <p className="text-slate-500 text-sm mt-1 max-w-2xl">
            Contratos de <strong>TI &amp; Dados</strong> que vão vencer. Quando o contrato acaba, o órgão recontrata —
            e você já sabe <strong>quem tem o contrato hoje</strong> e <strong>por quanto</strong>. Chegue antes na renovação.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-5">
        <span className="text-xs text-slate-400">Vencendo em até:</span>
        {[6, 12, 24].map(m => (
          <button key={m} onClick={() => setMonths(m)}
            className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition ${
              months === m ? "text-white dd-gradient border-transparent shadow-sm" : "bg-white border-slate-200 text-slate-500 hover:border-proc-300"
            }`}>
            {m} meses
          </button>
        ))}
        {total > 0 && <span className="text-xs text-slate-400 ml-1">{total} contratos</span>}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-proc-400" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <FileClock size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium text-slate-500">Nenhum contrato de TI vencendo nessa janela ainda.</p>
          <p className="text-xs mt-1">O radar de contratos roda 2x ao dia — vai populando conforme o PNCP publica.</p>
        </div>
      ) : (
        <div className="space-y-3 dd-stagger">
          {items.map(c => {
            const url = pncpUrl(c.external_id);
            return (
              <div key={c.id} className="bg-white rounded-2xl border border-slate-100 shadow-card p-5 hover:shadow-card-hover transition">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <Prazo days={c.days_left} />
                  <span className="text-[11px] text-slate-400">vence em {fmtDate(c.vigencia_fim)}</span>
                  {c.state && <span className="text-[11px] text-slate-400 flex items-center gap-0.5"><MapPin size={11} /> {c.state}</span>}
                </div>
                <h3 className="text-sm font-semibold text-slate-800 leading-snug line-clamp-2">{c.objeto}</h3>
                <div className="flex items-center gap-3 text-[12px] text-slate-400 mt-2 flex-wrap">
                  <span className="flex items-center gap-1"><Building2 size={12} /> {c.organ_name ?? "—"}</span>
                  <span className="font-medium text-slate-500">{fmt(c.valor)}</span>
                </div>
                <div className="flex items-center justify-between gap-3 mt-3 pt-3 border-t border-slate-50">
                  <div className="flex items-center gap-2 min-w-0">
                    <Award size={14} className="text-amber-500 shrink-0" />
                    <span className="text-xs text-slate-500 truncate">
                      Incumbente: <span className="font-medium text-slate-700">{c.supplier_name ?? "—"}</span>
                      {c.supplier_document && <span className="text-slate-400 font-mono"> · {c.supplier_document}</span>}
                    </span>
                  </div>
                  {url && (
                    <a href={url} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-proc-600 hover:text-proc-700 font-medium flex items-center gap-1 shrink-0">
                      <Globe size={12} /> PNCP
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
