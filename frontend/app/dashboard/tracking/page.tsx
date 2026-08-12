"use client";
import { useEffect, useState, useCallback } from "react";
import { BookmarkCheck, CheckCircle, XCircle, Clock, ExternalLink } from "lucide-react";
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

export default function TrackingPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<"all" | "won" | "lost">("all");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [selectedBidId, setSelectedBidId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "50" });
    if (filter === "won") params.set("won", "true");
    if (filter === "lost") params.set("won", "false");
    try {
      const res = await fetch(`${API}/api/tracking?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setItems(data.data ?? []);
      setTotal(data.total ?? 0);
    } catch {}
    setLoading(false);
  }, [filter, token]);

  useEffect(() => { load(); }, [load]);

  async function markResult(bidId: number, won: boolean) {
    await fetch(`${API}/api/tracking/${bidId}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ won, participated: true }),
    });
    load();
  }

  async function stopTracking(bidId: number) {
    if (!confirm("Parar de acompanhar esta licitação?")) return;
    await fetch(`${API}/api/tracking/${bidId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    load();
  }

  async function saveNotes(bidId: number) {
    await fetch(`${API}/api/tracking/${bidId}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    });
    setEditing(null);
    load();
  }

  const won = items.filter(i => i.won === true).length;
  const participated = items.filter(i => i.participated).length;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Acompanhamento</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {total} licitações · {participated} participadas · {won} ganhas
        </p>
      </div>

      {/* Filter */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit mb-6">
        {[
          { key: "all", label: "Todas" },
          { key: "won", label: "Ganhas" },
          { key: "lost", label: "Perdidas" },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key as any)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
              filter === f.key ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-16 text-center">
          <BookmarkCheck size={40} className="mx-auto mb-3 text-slate-300" />
          <p className="text-slate-500">Nenhuma licitação em acompanhamento.</p>
          <p className="text-slate-400 text-sm mt-1">Clique no ícone de marcar nas licitações para acompanhar.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item: any) => (
            <div key={item.id} className={`bg-white rounded-2xl shadow-card border p-5 ${
              item.won === true ? "border-emerald-200" : item.won === false ? "border-red-100" : "border-slate-100"
            }`}>
              <div className="flex items-start gap-4">
                {/* Status icon */}
                <div className="shrink-0 mt-0.5">
                  {item.won === true ? (
                    <CheckCircle size={22} className="text-emerald-500" />
                  ) : item.won === false ? (
                    <XCircle size={22} className="text-red-400" />
                  ) : (
                    <Clock size={22} className="text-slate-300" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <button
                    className="text-left font-medium text-slate-900 line-clamp-1 hover:text-proc-700 transition"
                    onClick={() => setSelectedBidId(item.bid_id)}
                    title="Ver detalhes da licitação"
                  >
                    {item.bid_title}
                  </button>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-slate-500">
                    {item.bid_state && <span>{item.bid_state}</span>}
                    {item.bid_estimated_value && <span>{fmt(item.bid_estimated_value)}</span>}
                    {item.bid_closing_date && <span>Encerramento: {fmtDate(item.bid_closing_date)}</span>}
                    {item.proposal_value && <span className="text-proc-700">Proposta: {fmt(item.proposal_value)}</span>}
                    {item.contract_value && <span className="text-emerald-700 font-medium">Contrato: {fmt(item.contract_value)}</span>}
                  </div>

                  <button
                    onClick={() => setSelectedBidId(item.bid_id)}
                    className="mt-2 flex items-center gap-1.5 text-xs text-proc-600 hover:text-proc-800 font-medium transition"
                  >
                    <ExternalLink size={12} /> Ver detalhes da licitação
                  </button>

                  {/* Notes */}
                  {editing === item.bid_id ? (
                    <div className="mt-3 flex gap-2">
                      <input type="text" value={notes} onChange={e => setNotes(e.target.value)}
                        placeholder="Adicionar nota…"
                        className="flex-1 border border-slate-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-proc-400" />
                      <button onClick={() => saveNotes(item.bid_id)}
                        className="px-3 py-1.5 bg-proc-500 text-white text-xs rounded-lg hover:bg-proc-600 transition">
                        Salvar
                      </button>
                      <button onClick={() => setEditing(null)}
                        className="px-3 py-1.5 border border-slate-200 text-slate-500 text-xs rounded-lg hover:bg-slate-50 transition">
                        Cancelar
                      </button>
                    </div>
                  ) : item.notes ? (
                    <p className="mt-2 text-xs text-slate-500 italic cursor-pointer hover:text-slate-700"
                      onClick={() => { setEditing(item.bid_id); setNotes(item.notes); }}>
                      "{item.notes}"
                    </p>
                  ) : (
                    <button onClick={() => { setEditing(item.bid_id); setNotes(""); }}
                      className="mt-2 text-xs text-slate-400 hover:text-proc-500 transition">
                      + Adicionar nota
                    </button>
                  )}
                </div>

                {/* Actions */}
                {item.won === null && (
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button onClick={() => markResult(item.bid_id, true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-medium hover:bg-emerald-100 transition">
                      <CheckCircle size={13} /> Ganhei
                    </button>
                    <button onClick={() => markResult(item.bid_id, false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs font-medium hover:bg-red-100 transition">
                      <XCircle size={13} /> Perdi
                    </button>
                    <button onClick={() => stopTracking(item.bid_id)}
                      className="px-2 py-1.5 text-slate-400 hover:text-red-500 text-xs rounded-lg hover:bg-slate-50 transition">
                      Parar
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Drawer lateral com detalhes da licitação */}
      <BidDrawer
        bidId={selectedBidId}
        token={token}
        onClose={() => setSelectedBidId(null)}
        onTrack={() => {}}
      />
    </div>
  );
}
