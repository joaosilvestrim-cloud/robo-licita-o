"use client";
import { useEffect, useState } from "react";
import { FileSearch, Bell, BookmarkCheck, TrendingUp, AlertCircle, RefreshCw, Search, Cpu } from "lucide-react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}

function useAuth() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("proc_token") ?? "";
}

export default function DashboardPage() {
  const token = useAuth();
  const [data, setData]     = useState<any>(null);
  const [tiBids, setTiBids] = useState<any[]>([]);
  const [tiTotal, setTiTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing]   = useState(false);
  const [kwInput, setKwInput]   = useState("");
  const [kwLoading, setKwLoading] = useState(false);
  const [kwMsg, setKwMsg]       = useState("");

  async function load() {
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const [dRes, tiRes] = await Promise.all([
        fetch(`${API}/api/dashboard`, { headers }),
        fetch(`${API}/api/bids/ti?limit=5`, { headers }),
      ]);
      setData(await dRes.json());
      const ti = await tiRes.json().catch(() => ({}));
      setTiBids(ti.data ?? []);
      setTiTotal(ti.total ?? 0);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { if (token) load(); }, [token]);

  async function triggerSync() {
    setSyncing(true);
    await fetch(`${API}/api/sync`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setTimeout(() => { setSyncing(false); load(); }, 5000);
  }

  async function searchKeyword(e: React.FormEvent) {
    e.preventDefault();
    const kw = kwInput.trim();
    if (!kw) return;
    setKwLoading(true);
    setKwMsg("");
    await fetch(`${API}/api/sync/keyword`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: kw, max_pages: 8 }),
    });
    setKwMsg(`Buscando "${kw}" no PNCP — aguarde alguns segundos e atualize a tela.`);
    setKwLoading(false);
    setTimeout(() => { setKwMsg(""); load(); }, 8000);
  }

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
    </div>
  );

  const kpis = [
    {
      label: "Abertas para proposta",
      value: data?.total_bids_open ?? 0,
      sub: `${data?.total_bids_coming_7d ?? 0} vencem em 7 dias · ${data?.total_bids_no_deadline ?? 0} sem prazo`,
      icon: FileSearch, color: "text-proc-500", bg: "bg-proc-50",
    },
    {
      label: "Valor total estimado",
      value: fmt(data?.total_estimated_value ?? 0),
      sub: `Média: ${fmt(data?.average_value ?? 0)}`,
      icon: TrendingUp, color: "text-emerald-500", bg: "bg-emerald-50",
    },
    {
      label: "Alertas novos",
      value: data?.new_alerts ?? 0,
      sub: "não visualizados",
      icon: Bell, color: "text-amber-500", bg: "bg-amber-50",
      href: "/dashboard/alerts",
    },
    {
      label: "Em acompanhamento",
      value: data?.tracking?.total ?? 0,
      sub: `${data?.tracking?.won ?? 0} ganhas (${Math.round((data?.tracking?.success_rate ?? 0) * 100)}%)`,
      icon: BookmarkCheck, color: "text-violet-500", bg: "bg-violet-50",
      href: "/dashboard/tracking",
    },
  ];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">Panorama de licitações públicas</p>
        </div>
        <button onClick={triggerSync} disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition disabled:opacity-60">
          <RefreshCw size={15} className={syncing ? "animate-spin" : ""} />
          {syncing ? "Sincronizando…" : "Sincronizar agora"}
        </button>
      </div>

      {/* Busca por keyword no PNCP */}
      <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-4 mb-6">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Busca avançada no PNCP (full-text nos editais)
        </p>
        <form onSubmit={searchKeyword} className="flex gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={kwInput}
              onChange={e => setKwInput(e.target.value)}
              placeholder='Ex: "Power BI", "análise de dados", "dashboard", "business intelligence"…'
              className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-proc-400"
            />
          </div>
          <button type="submit" disabled={kwLoading || !kwInput.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-proc-600 hover:bg-proc-700 text-white rounded-xl text-sm font-medium transition disabled:opacity-60 whitespace-nowrap">
            {kwLoading
              ? <><span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Buscando…</>
              : <><Search size={14} /> Buscar no PNCP</>}
          </button>
        </form>
        {kwMsg && (
          <p className="text-xs text-proc-700 bg-proc-50 rounded-lg px-3 py-2 mt-2">{kwMsg}</p>
        )}
        <p className="text-[11px] text-slate-400 mt-1.5">
          Pesquisa dentro do texto dos editais — encontra licitações que mencionam o termo mas não aparecem no sync diário por data.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {kpis.map(k => (
          <div key={k.label} className={`bg-white rounded-2xl shadow-card p-5 border border-slate-100 ${k.href ? "cursor-pointer hover:shadow-card-hover transition" : ""}`}
            onClick={() => k.href && (window.location.href = k.href)}>
            <div className={`w-10 h-10 rounded-xl ${k.bg} flex items-center justify-center mb-3`}>
              <k.icon size={20} className={k.color} />
            </div>
            <div className="text-2xl font-bold text-slate-900">{k.value}</div>
            <div className="text-xs text-slate-500 mt-1">{k.label}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Oportunidades de TI & Dados (foco Drive Data) */}
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Cpu size={17} className="text-proc-500" />
              <h2 className="font-semibold text-slate-900">Oportunidades de TI &amp; Dados</h2>
            </div>
            {tiTotal > 0 && (
              <span className="text-[11px] font-semibold text-white dd-gradient px-2.5 py-1 rounded-full">{tiTotal} abertas</span>
            )}
          </div>
          {tiBids.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">Nenhuma no momento.</p>
          ) : (
            <div className="space-y-0.5">
              {tiBids.map((b: any) => (
                <Link key={b.id} href={`/dashboard/bids/${b.id}`}
                  className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition group">
                  <div className="w-9 h-9 rounded-lg bg-proc-50 flex items-center justify-center shrink-0 text-proc-600 font-bold text-[11px]">
                    {b.state ?? "—"}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-700 truncate group-hover:text-proc-700">{b.title}</div>
                    <div className="text-[11px] text-slate-400 truncate">
                      {b.organ_name ?? "—"} · {b.estimated_value ? fmt(b.estimated_value) : "valor n/d"}
                    </div>
                  </div>
                  {typeof b.relevance === "number" && (
                    <span className="text-[10px] font-mono text-proc-500 shrink-0" title="relevância">rel {b.relevance}</span>
                  )}
                </Link>
              ))}
            </div>
          )}
          <Link href="/dashboard/bids"
            className="block text-center text-sm text-proc-600 hover:text-proc-700 font-medium mt-3 pt-3 border-t border-slate-50">
            Ver todas as licitações →
          </Link>
        </div>

        {/* Distribuição por esfera */}
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
          <h2 className="font-semibold text-slate-900 mb-4">Distribuição por esfera</h2>
          {Object.keys(data?.spheres_distribution ?? {}).length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">Nenhum dado disponível.</p>
          ) : (
            <div className="space-y-4">
              {Object.entries(data.spheres_distribution).map(([sphere, count]: [string, any]) => {
                const total = data.total_bids_open || 1;
                const pct = Math.round((count / total) * 100);
                const colors: Record<string, string> = {
                  federal: "bg-blue-500",
                  estadual: "bg-violet-500",
                  municipal: "bg-emerald-500",
                };
                return (
                  <div key={sphere}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-medium text-slate-700 capitalize">{sphere}</span>
                      <span className="text-sm font-semibold text-slate-900">{count} <span className="text-xs text-slate-400 font-normal">({pct}%)</span></span>
                    </div>
                    <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full ${colors[sphere] ?? "bg-slate-400"} rounded-full`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* CTA empty state */}
      {data?.total_bids_open === 0 && (
        <div className="mt-6 bg-proc-50 border border-proc-100 rounded-2xl p-8 text-center">
          <AlertCircle size={32} className="text-proc-400 mx-auto mb-3" />
          <h3 className="font-semibold text-proc-900 mb-1">Nenhuma licitação carregada</h3>
          <p className="text-proc-700 text-sm mb-4">Clique em "Sincronizar agora" para buscar licitações do PNCP.</p>
          <Link href="/dashboard/profiles"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-proc-500 text-white rounded-xl text-sm font-medium hover:bg-proc-600 transition">
            Configurar perfil de alertas
          </Link>
        </div>
      )}
    </div>
  );
}
