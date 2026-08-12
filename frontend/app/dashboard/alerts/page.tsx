"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Bell, Star, Trash2, Eye, ChevronLeft, ChevronRight, ExternalLink, CheckCheck, XCircle, Loader2 } from "lucide-react";
import BidDrawer from "../../components/BidDrawer";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}

function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR");
}

const STATUS_FILTER = [
  { value: "", label: "Todos" },
  { value: "novo", label: "Novos" },
  { value: "visto", label: "Vistos" },
  { value: "favorito", label: "Favoritos" },
  { value: "descartado", label: "Descartados" },
];

export default function AlertsPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [alerts, setAlerts]   = useState<any[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [status, setStatus]   = useState("novo");
  const [loading, setLoading] = useState(true);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [selectedBidId, setSelectedBidId] = useState<number | null>(null);
  const router = useRouter();

  async function openBidDrawer(alert: any) {
    if (alert.status === "novo") {
      await action(alert.id, "mark-viewed");
    }
    setSelectedBidId(alert.bid_id);
  }

  async function trackBid(bidId: number) {
    const res = await fetch(`${API}/api/tracking/${bidId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: "{}",
    });
    const d = await res.json().catch(() => ({}));
    alert(res.ok ? "Licitação adicionada ao acompanhamento!" : (d.detail ?? "Erro."));
  }
  const limit = 20;
  const pages = Math.ceil(total / limit);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (status) params.set("status", status);
    try {
      const res = await fetch(`${API}/api/alerts?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setAlerts(data.data ?? []);
      setTotal(data.total ?? 0);
    } catch {}
    setLoading(false);
  }, [page, status, token]);

  useEffect(() => { load(); }, [load]);

  async function action(alertId: number, endpoint: string) {
    await fetch(`${API}/api/alerts/${alertId}/${endpoint}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
    });
    load();
  }

  async function markAllViewed() {
    setBulkLoading(true);
    await fetch(`${API}/api/alerts/bulk/mark-all-viewed`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setBulkLoading(false);
    load();
  }

  async function discardAll() {
    const label = status === "novo" ? "novos" : status === "visto" ? "vistos" : "visíveis";
    if (!confirm(`Descartar todos os alertas ${label}? Favoritos serão preservados.`)) return;
    setBulkLoading(true);
    const params = status && status !== "descartado" && status !== "favorito" ? `?status=${status}` : "";
    await fetch(`${API}/api/alerts/bulk/discard-all${params}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    setBulkLoading(false);
    load();
  }

  async function deleteDiscarded() {
    if (!confirm("Remover permanentemente todos os alertas descartados? Esta ação não pode ser desfeita.")) return;
    setBulkLoading(true);
    await fetch(`${API}/api/alerts/bulk/discarded`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    setBulkLoading(false);
    load();
  }

  async function deleteAll() {
    if (!confirm("APAGAR permanentemente todos os alertas? Favoritos serão preservados. Esta ação não pode ser desfeita.")) return;
    setBulkLoading(true);
    await fetch(`${API}/api/alerts/bulk/all?keep_favorites=true`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    setBulkLoading(false);
    load();
  }

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Alertas</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {total} alerta{total !== 1 ? "s" : ""} no filtro atual
          </p>
        </div>

        {/* Ações em massa */}
        <div className="flex items-center gap-2 flex-wrap">
          {status === "novo" && total > 0 && (
            <button onClick={markAllViewed} disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-proc-50 border border-proc-200 text-proc-700 rounded-lg text-xs font-medium hover:bg-proc-100 transition disabled:opacity-60">
              <CheckCheck size={13} /> Marcar todos como vistos
            </button>
          )}
          {(status === "novo" || status === "visto" || status === "") && total > 0 && (
            <button onClick={discardAll} disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg text-xs font-medium hover:bg-amber-100 transition disabled:opacity-60">
              <XCircle size={13} /> Descartar todos
            </button>
          )}
          {status === "descartado" && total > 0 && (
            <button onClick={deleteDiscarded} disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs font-medium hover:bg-red-100 transition disabled:opacity-60">
              <Trash2 size={13} /> Excluir descartados
            </button>
          )}
          {status === "" && (
            <button onClick={deleteAll} disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs font-medium hover:bg-red-100 transition disabled:opacity-60">
              <Trash2 size={13} /> Limpar tudo
            </button>
          )}
          {bulkLoading && <Loader2 size={14} className="animate-spin text-slate-400" />}
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit mb-6">
        {STATUS_FILTER.map(f => (
          <button key={f.value} onClick={() => { setStatus(f.value); setPage(1); }}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
              status === f.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-16 text-center">
          <Bell size={36} className="mx-auto mb-3 text-slate-300" />
          <p className="text-slate-500">Nenhum alerta encontrado.</p>
          <p className="text-slate-400 text-sm mt-1">Configure um perfil para começar a receber alertas.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a: any) => (
            <div key={a.id}
              className={`bg-white rounded-2xl shadow-card border p-5 transition hover:shadow-card-hover ${
                a.status === "novo" ? "border-proc-200" : "border-slate-100"
              }`}>
              <div className="flex items-start gap-4">
                {/* Score badge — clicável para íntegra */}
                <button
                  onClick={() => openBidDrawer(a)}
                  className={`shrink-0 w-14 h-14 rounded-xl flex flex-col items-center justify-center hover:ring-2 hover:ring-offset-1 hover:ring-proc-300 transition ${
                    (a.match_score ?? 0) >= 0.8 ? "bg-emerald-100 text-emerald-700" :
                    (a.match_score ?? 0) >= 0.6 ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"
                  }`}
                  title="Ver licitação na íntegra"
                >
                  <div className="text-lg font-bold">{Math.round((a.match_score ?? 0) * 100)}</div>
                  <div className="text-[10px] font-medium">score</div>
                </button>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    {/* Título clicável */}
                    <button
                      className="text-left font-medium text-slate-900 leading-snug line-clamp-2 hover:text-proc-700 transition"
                      onClick={() => openBidDrawer(a)}
                    >
                      {a.bid_title}
                    </button>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {a.status === "novo" && (
                        <span className="bg-proc-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">NOVO</span>
                      )}
                      {a.status === "favorito" && (
                        <Star size={14} className="text-amber-400 fill-amber-400" />
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-slate-500">
                    {a.bid_state && <span>{a.bid_state}{a.bid_city ? ` · ${a.bid_city}` : ""}</span>}
                    {a.bid_estimated_value && <span className="font-medium text-slate-700">{fmt(a.bid_estimated_value)}</span>}
                    {a.bid_closing_date && <span>Encerra: {fmtDate(a.bid_closing_date)}</span>}
                    {a.bid_source && <span className="uppercase tracking-wide">{a.bid_source}</span>}
                  </div>

                  {/* Match reasons */}
                  {a.match_reasons?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {a.match_reasons.map((r: string) => (
                        <span key={r} className="bg-proc-50 text-proc-700 text-xs px-2 py-0.5 rounded-lg">{r}</span>
                      ))}
                    </div>
                  )}

                  {/* Botão íntegra */}
                  <button
                    onClick={() => openBidDrawer(a)}
                    className="mt-2.5 flex items-center gap-1.5 text-xs text-proc-600 hover:text-proc-800 font-medium transition"
                  >
                    <ExternalLink size={12} /> Ver edital na íntegra
                  </button>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <button onClick={() => action(a.id, "mark-viewed")} title="Marcar como visto"
                    className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition">
                    <Eye size={15} />
                  </button>
                  <button onClick={() => action(a.id, "favorite")} title="Favoritar"
                    className={`p-2 rounded-lg hover:bg-amber-50 transition ${
                      a.status === "favorito" ? "text-amber-400" : "text-slate-400 hover:text-amber-500"
                    }`}>
                    <Star size={15} className={a.status === "favorito" ? "fill-amber-400" : ""} />
                  </button>
                  <button onClick={() => action(a.id, "discard")} title="Descartar"
                    className="p-2 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition">
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </div>
          ))}

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-500">Página {page} de {pages}</span>
              <div className="flex gap-1">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="p-1.5 rounded-lg hover:bg-white disabled:opacity-40 transition">
                  <ChevronLeft size={16} />
                </button>
                <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                  className="p-1.5 rounded-lg hover:bg-white disabled:opacity-40 transition">
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Drawer lateral com detalhes da licitação */}
      <BidDrawer
        bidId={selectedBidId}
        token={token}
        onClose={() => setSelectedBidId(null)}
        onTrack={trackBid}
      />
    </div>
  );
}
