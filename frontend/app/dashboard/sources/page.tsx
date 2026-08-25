"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Database, RefreshCw, CheckCircle2, XCircle, Clock, ExternalLink, AlertCircle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Source {
  key: string;
  name: string;
  description: string;
  official_url: string;
  active: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_records: number | null;
}

const SOURCE_ICONS: Record<string, string> = {
  pncp:         "🏛️",
  comprasnet:   "🇧🇷",
  licitacoes_e: "🏦",
  bec_sp:       "🏙️",
  dou:          "📰",
};

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-slate-400 text-xs">nunca sincronizado</span>;
  if (status === "sucesso") return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
      <CheckCircle2 size={11} /> Sucesso
    </span>
  );
  if (status === "erro") return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
      <XCircle size={11} /> Erro
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
      <AlertCircle size={11} /> {status}
    </span>
  );
}

function fmtDateTime(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function timeAgo(dt: string | null): string {
  if (!dt) return "";
  const diff = Math.floor((Date.now() - new Date(dt).getTime()) / 1000);
  if (diff < 60)    return "agora mesmo";
  if (diff < 3600)  return `há ${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `há ${Math.floor(diff / 3600)}h`;
  return `há ${Math.floor(diff / 86400)}d`;
}

export default function SourcesPage() {
  const router = useRouter();
  const [sources, setSources]   = useState<Source[]>([]);
  const [loading, setLoading]   = useState(true);
  const [syncing, setSyncing]   = useState<string | null>(null);
  const [syncMsg, setSyncMsg]   = useState<string | null>(null);
  const [portals, setPortals]   = useState<any[]>([]);
  const [portalTotal, setPortalTotal] = useState(0);

  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/sources`, { headers: { Authorization: `Bearer ${token}` } });
      if (r.status === 401) { router.replace("/login"); return; }
      setSources(await r.json());
      fetch(`${API}/api/sources/portals`, { headers: { Authorization: `Bearer ${token}` } })
        .then(x => x.ok ? x.json() : null)
        .then(d => { if (d) { setPortals(d.portals ?? []); setPortalTotal(d.total ?? 0); } })
        .catch(() => {});
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function triggerSync(key: string) {
    setSyncing(key);
    setSyncMsg(null);
    try {
      const r = await fetch(`${API}/api/sync/${key}?days_back=3`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      setSyncMsg(d.message ?? "Sync iniciado");
      setTimeout(() => { setSyncMsg(null); load(); }, 4000);
    } finally {
      setSyncing(null);
    }
  }

  async function triggerAll() {
    setSyncing("all");
    setSyncMsg(null);
    try {
      const r = await fetch(`${API}/api/sync/all?days_back=3`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      setSyncMsg(d.message ?? "Sync completo iniciado");
      setTimeout(() => { setSyncMsg(null); load(); }, 5000);
    } finally {
      setSyncing(null);
    }
  }

  return (
    <div className="h-screen overflow-y-auto bg-slate-50">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-proc-900 flex items-center justify-center">
              <Database size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800">Fontes de Dados</h1>
              <p className="text-sm text-slate-500">Portais públicos integrados para coleta de licitações</p>
            </div>
          </div>
          <button
            onClick={triggerAll}
            disabled={syncing !== null}
            className="flex items-center gap-2 px-4 py-2 bg-proc-600 hover:bg-proc-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition"
          >
            <RefreshCw size={14} className={syncing === "all" ? "animate-spin" : ""} />
            Sincronizar Todas
          </button>
        </div>

        {syncMsg && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800 flex items-center gap-2">
            <Clock size={14} /> {syncMsg}
          </div>
        )}

        {/* Regra de coleta */}
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
          <span className="font-semibold">Regra de coleta:</span> apenas licitações com prazo de participação ainda em aberto
          são importadas. Editais encerrados são ignorados automaticamente.
        </div>

        {/* Tabela */}
        {loading ? (
          <div className="flex justify-center py-16">
            <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Fonte</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Última Coleta</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Registros</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sources.map(s => (
                  <tr key={s.key} className="hover:bg-slate-50 transition">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl leading-none">{SOURCE_ICONS[s.key] ?? "📋"}</span>
                        <div>
                          <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                            {s.name}
                            {!s.active && (
                              <span className="text-[10px] font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">inativo</span>
                            )}
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5 max-w-sm">{s.description}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={s.last_sync_status} />
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-slate-700">{fmtDateTime(s.last_sync_at)}</div>
                      {s.last_sync_at && (
                        <div className="text-xs text-slate-400 mt-0.5">{timeAgo(s.last_sync_at)}</div>
                      )}
                    </td>
                    <td className="px-4 py-4 text-right">
                      {s.last_sync_records !== null
                        ? <span className="font-mono font-semibold text-slate-700">{s.last_sync_records.toLocaleString("pt-BR")}</span>
                        : <span className="text-slate-400">—</span>
                      }
                    </td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <a href={s.official_url} target="_blank" rel="noreferrer"
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition" title="Acessar portal">
                          <ExternalLink size={14} />
                        </a>
                        {s.active && (
                          <button
                            onClick={() => triggerSync(s.key)}
                            disabled={syncing !== null}
                            className="p-1.5 rounded-lg text-proc-500 hover:text-proc-700 hover:bg-proc-50 disabled:opacity-40 transition"
                            title="Sincronizar agora"
                          >
                            <RefreshCw size={14} className={syncing === s.key ? "animate-spin" : ""} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Portais de origem — de qual sistema cada licitação veio (via PNCP) */}
        {portals.length > 0 && (
          <div className="mt-6 p-5 bg-white border border-slate-200 rounded-xl">
            <div className="flex items-center justify-between mb-1">
              <p className="text-sm font-semibold text-slate-700">Portais de origem</p>
              <span className="text-xs text-slate-400">{portalTotal.toLocaleString("pt-BR")} licitações · {portals.length} portais</span>
            </div>
            <p className="text-xs text-slate-400 mb-4 max-w-2xl">
              De qual sistema cada licitação foi publicada. Todos chegam a nós pelo <b>PNCP</b> (hub oficial da Lei 14.133),
              então cobrimos esses portais sem raspar cada um. Clique para filtrar as licitações do portal.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {portals.map(p => (
                <a key={p.portal}
                  href={`/dashboard/bids?portal=${encodeURIComponent(p.portal)}`}
                  className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-100 bg-slate-50/60 hover:border-proc-300 hover:bg-white transition">
                  <span className="text-xs font-medium text-slate-700 truncate">{p.portal}</span>
                  <span className="text-[11px] font-mono font-semibold text-slate-500 shrink-0">{p.count.toLocaleString("pt-BR")}</span>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
