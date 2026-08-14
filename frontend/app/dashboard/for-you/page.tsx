"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, Clock, MapPin, Building2, ArrowRight, Loader2, Target } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "valor n/d";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}

// Badge de prazo com cor por urgência
function Prazo({ days }: { days: number | null }) {
  if (days == null) return <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-full bg-slate-100 text-slate-500"><Clock size={11} /> Sem prazo</span>;
  const base = "inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-full";
  if (days <= 2)  return <span className={`${base} bg-red-100 text-red-700`}><Clock size={11} /> Última chance · {days}d</span>;
  if (days <= 7)  return <span className={`${base} bg-amber-100 text-amber-700`}><Clock size={11} /> Vence em {days}d</span>;
  if (days <= 30) return <span className={`${base} bg-proc-50 text-proc-700`}><Clock size={11} /> {days}d restantes</span>;
  return <span className={`${base} bg-slate-100 text-slate-500`}><Clock size={11} /> {days}d restantes</span>;
}

export default function ForYouPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [hasProfile, setHasProfile] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/bids/for-you?limit=30`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setItems(d.data ?? []); setTotal(d.total ?? 0); setHasProfile(d.has_profile ?? true); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles size={22} className="text-proc-500" /> Pra você
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            As melhores oportunidades <strong>abertas</strong> pro seu perfil, por aderência e prazo.
            {total > 0 && <span className="text-slate-400"> · {total} encontradas</span>}
          </p>
        </div>
        <Link href="/dashboard/profiles" className="text-xs text-proc-600 hover:text-proc-700 font-medium flex items-center gap-1 mt-1">
          <Target size={13} /> Ajustar perfil
        </Link>
      </div>

      {!hasProfile && (
        <div className="mb-5 bg-proc-50 border border-proc-100 rounded-xl px-4 py-3 text-sm text-proc-800">
          Você ainda não tem um perfil. Mostrando oportunidades de <strong>TI &amp; Dados</strong>. Crie um perfil em
          <Link href="/dashboard/profiles" className="underline font-medium"> Meus Perfis</Link> para um feed sob medida.
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-proc-400" /></div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <Sparkles size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm font-medium text-slate-500">Nenhuma oportunidade aderente no momento.</p>
          <p className="text-xs mt-1">Adicione palavras-chave ao seu perfil ou sincronize no Dashboard.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((b, i) => (
            <Link key={b.id} href={`/dashboard/bids/${b.id}`}
              className="block bg-white rounded-2xl border border-slate-100 shadow-card p-5 hover:shadow-card-hover hover:border-proc-200 transition group">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl dd-gradient text-white flex items-center justify-center font-bold text-sm shrink-0">
                  {i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <Prazo days={b.days_left} />
                    {typeof b.relevance === "number" && (
                      <span className="text-[11px] font-mono text-proc-500 bg-proc-50 px-2 py-0.5 rounded-full">aderência {b.relevance}</span>
                    )}
                    {(b.matched ?? []).slice(0, 2).map((m: string) => (
                      <span key={m} className="text-[11px] text-dgreen-600 bg-dgreen-400/10 px-2 py-0.5 rounded-full">{m}</span>
                    ))}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800 leading-snug group-hover:text-proc-700 line-clamp-2">{b.title}</h3>
                  <div className="flex items-center gap-3 text-[12px] text-slate-400 mt-2 flex-wrap">
                    <span className="flex items-center gap-1"><Building2 size={12} /> {b.organ_name ?? "—"}</span>
                    <span className="flex items-center gap-1"><MapPin size={12} /> {b.state ?? "—"}{b.city ? ` · ${b.city}` : ""}</span>
                    <span className="font-medium text-slate-500">{fmt(b.estimated_value)}</span>
                  </div>
                </div>
                <ArrowRight size={18} className="text-slate-300 group-hover:text-proc-500 shrink-0 mt-1" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
