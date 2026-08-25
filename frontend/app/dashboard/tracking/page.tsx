"use client";
import { useEffect, useState, useCallback } from "react";
import { BookmarkCheck, Clock, CalendarClock, MapPin, X, GripVertical } from "lucide-react";
import BidDrawer from "../../components/BidDrawer";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return null;
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}

const COLUMNS = [
  { key: "backlog",    label: "Backlog",    hint: "escolhidas, avaliando", dot: "bg-slate-400" },
  { key: "preparando", label: "Preparando", hint: "montando proposta",     dot: "bg-sky-400" },
  { key: "disputa",    label: "Em disputa", hint: "participando",          dot: "bg-indigo-400" },
  { key: "ganhou",     label: "Ganhou",     hint: "",                      dot: "bg-emerald-500" },
  { key: "perdeu",     label: "Perdeu",     hint: "",                      dot: "bg-red-400" },
];

function DueBadge({ days, due }: { days: number | null; due: string | null }) {
  if (days == null || !due) return null;
  const overdue = days < 0;
  const cls = overdue ? "bg-red-100 text-red-700" : days <= 3 ? "bg-amber-100 text-amber-700" : "bg-proc-50 text-proc-700";
  const label = overdue ? "atrasada" : days === 0 ? "hoje" : `em ${days}d`;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${cls}`}>
      <Clock size={10} /> {label}
    </span>
  );
}

export default function TrackingPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedBidId, setSelectedBidId] = useState<number | null>(null);
  const [agenda, setAgenda] = useState<any[]>([]);
  const [dragId, setDragId] = useState<number | null>(null);
  const [overCol, setOverCol] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/tracking?limit=100`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setItems(data.data ?? []);
      setTotal(data.total ?? 0);
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/tracking/agenda/upcoming?days=90`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.data) setAgenda(d.data); })
      .catch(() => {});
  }, [token, items]);

  function moveStage(item: any, stage: string) {
    if (item.stage === stage) return;
    const body: any = { stage };
    if (stage === "ganhou") { body.won = true; body.participated = true; }
    else if (stage === "perdeu") { body.won = false; body.participated = true; }
    else if (stage === "disputa") { body.participated = true; }
    setItems(prev => prev.map(i => i.bid_id === item.bid_id ? { ...i, stage, ...(body.won !== undefined ? { won: body.won } : {}) } : i));
    fetch(`${API}/api/tracking/${item.bid_id}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => {});
  }

  async function stopTracking(bidId: number) {
    if (!confirm("Remover esta licitação do quadro?")) return;
    setItems(prev => prev.filter(i => i.bid_id !== bidId));
    await fetch(`${API}/api/tracking/${bidId}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
  }

  const won = items.filter(i => i.stage === "ganhou").length;
  const active = items.filter(i => i.stage === "preparando" || i.stage === "disputa").length;

  return (
    <div className="p-8">
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <BookmarkCheck size={22} className="text-proc-500" /> Meus negócios
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {total} no quadro · {active} em andamento · {won} ganhas · arraste os cards entre as colunas
        </p>
      </div>

      {/* Agenda: próximos prazos */}
      {agenda.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-card overflow-hidden mb-6">
          <div className="bg-slate-900 px-5 py-2.5 flex items-center gap-2 text-white">
            <CalendarClock size={15} />
            <span className="text-sm font-semibold">Agenda de prazos</span>
            <span className="text-[11px] text-white/60 ml-1">marcos e tarefas a vencer</span>
          </div>
          <div className="divide-y divide-slate-50 max-h-52 overflow-y-auto">
            {agenda.slice(0, 10).map(a => (
              <div key={a.id} className="flex items-center gap-3 px-5 py-2">
                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${
                  a.overdue ? "bg-red-100 text-red-700" : a.days_left <= 3 ? "bg-amber-100 text-amber-700" : "bg-proc-50 text-proc-700"
                }`}>
                  {a.overdue ? "atrasada" : a.days_left === 0 ? "hoje" : `em ${a.days_left}d`}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-slate-800 truncate">{a.title}{a.on_agenda && <span className="ml-1.5 text-[9px] font-bold text-amber-600">MARCO</span>}</div>
                  <div className="text-[11px] text-slate-400 truncate">{a.bid_title}</div>
                </div>
                <span className="text-xs text-slate-400 whitespace-nowrap">{a.due_date?.split("-").reverse().join("/")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-16 text-center">
          <BookmarkCheck size={40} className="mx-auto mb-3 text-slate-300" />
          <p className="text-slate-500">Nenhuma licitação no quadro ainda.</p>
          <p className="text-slate-400 text-sm mt-1">Abra uma licitação e clique em <b>Adicionar aos meus negócios</b>.</p>
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {COLUMNS.map(col => {
            const colItems = items.filter(i => (i.stage || "backlog") === col.key);
            return (
              <div key={col.key}
                onDragOver={e => { e.preventDefault(); setOverCol(col.key); }}
                onDragLeave={() => setOverCol(c => c === col.key ? null : c)}
                onDrop={() => { const it = items.find(i => i.bid_id === dragId); if (it) moveStage(it, col.key); setDragId(null); setOverCol(null); }}
                className={`shrink-0 w-72 rounded-2xl border transition ${overCol === col.key ? "border-proc-300 bg-proc-50/40" : "border-slate-100 bg-slate-50/60"}`}>
                <div className="px-4 pt-3 pb-1 flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${col.dot}`} />
                  <span className="text-sm font-semibold text-slate-700">{col.label}</span>
                  <span className="text-xs text-slate-400">{colItems.length}</span>
                  {(() => {
                    const soma = colItems.reduce((s, i) => s + (i.bid_estimated_value || 0), 0);
                    return soma > 0 ? <span className="ml-auto text-[11px] text-slate-500 font-medium">{fmt(soma)}</span> : (col.hint ? <span className="ml-auto text-[10px] text-slate-400">{col.hint}</span> : null);
                  })()}
                </div>
                <div className="px-2 pb-3 space-y-2 min-h-[120px]">
                  {colItems.map(item => (
                    <div key={item.id}
                      draggable
                      onDragStart={() => setDragId(item.bid_id)}
                      onDragEnd={() => { setDragId(null); setOverCol(null); }}
                      className={`group bg-white rounded-xl border border-slate-100 shadow-sm p-3 cursor-grab active:cursor-grabbing hover:shadow-card transition ${dragId === item.bid_id ? "opacity-40" : ""}`}>
                      <div className="flex items-start gap-1.5">
                        <GripVertical size={13} className="text-slate-300 mt-0.5 shrink-0" />
                        <button onClick={() => setSelectedBidId(item.bid_id)}
                          className="text-left text-sm font-medium text-slate-800 line-clamp-2 hover:text-proc-700 flex-1">
                          {item.bid_title}
                        </button>
                        <button onClick={() => stopTracking(item.bid_id)}
                          className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 shrink-0" title="Remover">
                          <X size={14} />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap mt-2 pl-5">
                        {item.next_due && <DueBadge days={item.next_days} due={item.next_due} />}
                        {item.bid_state && <span className="text-[11px] text-slate-400 flex items-center gap-0.5"><MapPin size={10} /> {item.bid_state}</span>}
                        {fmt(item.bid_estimated_value) && <span className="text-[11px] text-slate-500 font-medium">{fmt(item.bid_estimated_value)}</span>}
                      </div>
                      {item.next_task && (
                        <div className="text-[11px] text-slate-400 mt-1 pl-5 truncate">→ {item.next_task}</div>
                      )}
                    </div>
                  ))}
                  {colItems.length === 0 && (
                    <div className="text-[11px] text-slate-300 text-center py-6 border border-dashed border-slate-200 rounded-xl">
                      arraste para cá
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <BidDrawer bidId={selectedBidId} token={token} onClose={() => setSelectedBidId(null)} onTrack={() => load()} />
    </div>
  );
}
