"use client";
import { useEffect, useState } from "react";
import { BarChart2, TrendingUp, Award, Target } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "R$ 0";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}

export default function ReportsPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [dash, setDash]   = useState<any>(null);
  const [track, setTrack] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [dashRes, trackRes] = await Promise.all([
        fetch(`${API}/api/dashboard`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/tracking?limit=100`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setDash(await dashRes.json());
      const td = await trackRes.json();
      setTrack(td.data ?? []);
      setLoading(false);
    }
    if (token) load();
  }, [token]);

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
    </div>
  );

  const won = track.filter(t => t.won === true);
  const participated = track.filter(t => t.participated);
  const successRate = participated.length ? Math.round((won.length / participated.length) * 100) : 0;
  const totalContractValue = won.reduce((s, t) => s + (t.contract_value ?? t.bid_estimated_value ?? 0), 0);

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Relatórios</h1>
        <p className="text-slate-500 text-sm mt-0.5">Análise de desempenho e oportunidades</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Participações", value: participated.length, icon: Target, color: "text-proc-500", bg: "bg-proc-50" },
          { label: "Contratos ganhos", value: won.length, icon: Award, color: "text-emerald-500", bg: "bg-emerald-50" },
          { label: "Taxa de sucesso", value: `${successRate}%`, icon: TrendingUp, color: "text-violet-500", bg: "bg-violet-50" },
          { label: "Valor em contratos", value: fmt(totalContractValue), icon: BarChart2, color: "text-amber-500", bg: "bg-amber-50" },
        ].map(k => (
          <div key={k.label} className="bg-white rounded-2xl shadow-card border border-slate-100 p-5">
            <div className={`w-10 h-10 rounded-xl ${k.bg} flex items-center justify-center mb-3`}>
              <k.icon size={20} className={k.color} />
            </div>
            <div className="text-2xl font-bold text-slate-900">{k.value}</div>
            <div className="text-xs text-slate-500 mt-1">{k.label}</div>
          </div>
        ))}
      </div>

      <div className="grid xl:grid-cols-2 gap-6">
        {/* Distribuição mercado */}
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
          <h2 className="font-semibold text-slate-900 mb-4">Mercado disponível por esfera</h2>
          {Object.keys(dash?.spheres_distribution ?? {}).length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">Nenhum dado disponível.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(dash.spheres_distribution).map(([sphere, count]: [string, any]) => {
                const total = dash.total_bids_open || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={sphere} className="flex items-center gap-3">
                    <span className="text-sm text-slate-600 w-20 capitalize">{sphere}</span>
                    <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-proc-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-sm font-medium text-slate-700 w-16 text-right">{count} ({pct}%)</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Histórico de ganhos */}
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6">
          <h2 className="font-semibold text-slate-900 mb-4">Contratos ganhos</h2>
          {won.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">Nenhum contrato ganho registrado ainda.</p>
          ) : (
            <div className="space-y-3">
              {won.slice(0, 8).map((t: any) => (
                <div key={t.id} className="flex items-start gap-3">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 shrink-0 mt-1.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-700 truncate">{t.bid_title}</p>
                    <p className="text-xs text-slate-400">
                      {t.bid_state}
                      {t.contract_value ? ` · ${fmt(t.contract_value)}` : ""}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top oportunidades por ramo */}
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-6 xl:col-span-2">
          <h2 className="font-semibold text-slate-900 mb-4">Top ramos — oportunidades abertas</h2>
          {(dash?.branches_top_5 ?? []).length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">Nenhum dado disponível. Sincronize licitações primeiro.</p>
          ) : (
            <div className="grid md:grid-cols-5 gap-4">
              {dash.branches_top_5.map((b: any, i: number) => (
                <div key={b.branch} className="bg-slate-50 rounded-xl p-4 text-center">
                  <div className="text-2xl font-bold text-proc-500 mb-1">{b.count}</div>
                  <div className="text-xs font-medium text-slate-700 mb-1">{b.branch}</div>
                  <div className="text-[11px] text-slate-400">
                    {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(b.value)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
