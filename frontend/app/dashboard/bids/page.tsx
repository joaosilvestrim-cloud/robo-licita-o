"use client";
import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { Search, FileSearch, ExternalLink, BookmarkPlus, ChevronLeft, ChevronRight, X, MapPin, ArrowUp, ArrowDown, ArrowUpDown, Cpu } from "lucide-react";
import BidDrawer from "../../components/BidDrawer";
import { useRouter } from "next/navigation";

const BrazilMap = dynamic(() => import("./BrazilMap"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full border-r border-slate-800" style={{ background: "#0a1f34" }}>
      <span className="w-7 h-7 border-4 border-cyan-500/30 border-t-cyan-300 rounded-full animate-spin" />
    </div>
  ),
});

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}
function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR");
}

function deadlineBadge(closingDate: string | null | undefined) {
  if (!closingDate) return { label: "sem prazo", cls: "bg-slate-100 text-slate-500" };
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(closingDate + "T00:00:00");
  const days = Math.ceil((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (days < 0)  return { label: `${Math.abs(days)}d atrás`, cls: "bg-red-100 text-red-600" };
  if (days === 0) return { label: "hoje", cls: "bg-red-100 text-red-700 font-semibold" };
  if (days <= 3) return { label: `${days}d`,  cls: "bg-amber-100 text-amber-700 font-semibold" };
  if (days <= 7) return { label: `${days}d`,  cls: "bg-amber-50 text-amber-700" };
  if (days <= 30) return { label: `${days}d`, cls: "bg-emerald-50 text-emerald-700" };
  return { label: `${days}d`, cls: "bg-slate-50 text-slate-500" };
}

const SOURCE_ICONS: Record<string, string> = {
  pncp:         "🏛️",
  comprasnet:   "🇧🇷",
  licitacoes_e: "🏦",
  bec_sp:       "🏙️",
  dou:          "📰",
};
const SOURCE_LABELS: Record<string, string> = {
  pncp:         "PNCP",
  comprasnet:   "ComprasNet",
  licitacoes_e: "Licitações-e",
  bec_sp:       "BEC/SP",
  dou:          "DOU/QD",
};

const STATUS_OPTIONS = [
  { value: "aberta",     label: "Aberta",       color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
  { value: "andamento",  label: "Em andamento",  color: "bg-blue-100 text-blue-700 border-blue-200" },
  { value: "programada", label: "Programada",    color: "bg-amber-100 text-amber-700 border-amber-200" },
  { value: "encerrada",  label: "Encerrada",     color: "bg-slate-100 text-slate-600 border-slate-200" },
  { value: "cancelada",  label: "Cancelada",     color: "bg-red-100 text-red-600 border-red-200" },
];
const STATUS_BADGE: Record<string, string> = {
  aberta: "bg-emerald-100 text-emerald-700",
  andamento: "bg-blue-100 text-blue-700",
  encerrada: "bg-slate-200 text-slate-500",
  cancelada: "bg-red-100 text-red-600",
  programada: "bg-amber-100 text-amber-700",
};
// Faixa colorida na lateral da linha, por categoria de status
const STATUS_STRIPE: Record<string, string> = {
  aberta: "border-l-emerald-400",
  andamento: "border-l-blue-400",
  programada: "border-l-amber-400",
  encerrada: "border-l-slate-300",
  cancelada: "border-l-red-300",
};
const SPHERE_LABELS: Record<string, string> = {
  federal: "Federal", estadual: "Estadual", municipal: "Municipal",
};

export default function BidsPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";

  const [bids, setBids]       = useState<any[]>([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [loading, setLoading] = useState(true);
  const [showMap, setShowMap]     = useState(true);
  const [selectedBidId, setSelectedBidId] = useState<number | null>(null);
  const router = useRouter();

  // Filters
  const [q, setQ]                   = useState("");
  const [sphere, setSphere]         = useState("");
  const [state, setState]           = useState("");
  const [city, setCity]             = useState("");
  const [sortBy, setSortBy]         = useState("closing_date");
  const [sortDir, setSortDir]       = useState<"asc" | "desc">("asc");
  const [selectedStatus, setSelectedStatus] = useState<Set<string>>(new Set(["aberta"]));
  const [onlyOpenForProposals, setOnlyOpenForProposals] = useState(true);
  const [itMode, setItMode]         = useState(false);
  const [modality, setModality]     = useState("");
  const [minValue, setMinValue]     = useState("");
  const [maxValue, setMaxValue]     = useState("");
  const [daysBefore, setDaysBefore] = useState("");

  function clearAllFilters() {
    setQ(""); setSphere(""); setState(""); setCity("");
    setModality(""); setMinValue(""); setMaxValue(""); setDaysBefore("");
    setSelectedStatus(new Set(["aberta"])); setOnlyOpenForProposals(true);
    setPage(1);
  }

  const limit = 20;
  const pages = Math.ceil(total / limit);

  function toggleStatus(val: string) {
    const adding = !selectedStatus.has(val);
    setSelectedStatus(prev => {
      const next = new Set(prev);
      next.has(val) ? next.delete(val) : next.add(val);
      return next;
    });
    // Ao incluir um status não-aberto, libera o filtro de prazo para elas aparecerem
    if (adding && val !== "aberta") setOnlyOpenForProposals(false);
    setPage(1);
  }

  function handleMapStateSelect(code: string | null) {
    setState(code ?? "");
    setCity("");
    setPage(1);
  }

  function handleMapCitySelect(cityName: string | null) {
    setCity(cityName ?? "");
    setPage(1);
  }

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), limit: String(limit), sort_by: sortBy, sort_dir: sortDir });
    const clean = (v: string) => v.trim() === "*" ? "" : v.trim();
    if (clean(q))      params.set("q", clean(q));
    if (clean(sphere)) params.set("sphere", clean(sphere));
    if (clean(state))  params.set("state", clean(state).toUpperCase());
    if (clean(city))   params.set("city", clean(city));
    if (clean(modality)) params.set("modality", clean(modality));
    if (minValue)      params.set("min_value", minValue);
    if (maxValue)      params.set("max_value", maxValue);
    if (daysBefore)    params.set("days_before_closing", daysBefore);
    if (selectedStatus.size === 1) params.set("status", [...selectedStatus][0]);
    if (onlyOpenForProposals) params.set("only_open_for_proposals", "true");

    try {
      const endpoint = itMode ? "/api/bids/ti" : "/api/bids";
      const res = await fetch(`${API}${endpoint}?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      let items: any[] = data.data ?? [];
      if (selectedStatus.size > 1) {
        items = items.filter(b => selectedStatus.has(b.status));
      }
      setBids(items);
      setTotal(data.total ?? 0);
    } catch {}
    setLoading(false);
  }, [page, q, sphere, state, city, modality, minValue, maxValue, daysBefore, sortBy, sortDir, selectedStatus, onlyOpenForProposals, itMode, token]);

  function toggleSort(col: string) {
    if (sortBy === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
    setPage(1);
  }

  function SortIcon({ col }: { col: string }) {
    if (sortBy !== col) {
      return <ArrowUpDown size={11} className="text-slate-300 group-hover:text-slate-500" />;
    }
    return sortDir === "asc"
      ? <ArrowUp size={11} className="text-proc-500" />
      : <ArrowDown size={11} className="text-proc-500" />;
  }

  // debounce: espera 300ms de "silêncio" antes de buscar (evita 1 request por tecla)
  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  async function startTracking(bidId: number, silent = false) {
    const res = await fetch(`${API}/api/tracking/${bidId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: "{}",
    });
    const d = await res.json().catch(() => ({}));
    if (!silent) alert(res.ok ? "Licitação adicionada ao acompanhamento!" : (d.detail ?? "Erro ao adicionar."));
  }

  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* ── Mapa (esquerda) ── */}
      {showMap && (
        <div className="w-[360px] xl:w-[400px] shrink-0 flex flex-col h-full">
          <BrazilMap
            token={token}
            selectedState={state || null}
            selectedCity={city || null}
            onStateSelect={handleMapStateSelect}
            onCitySelect={handleMapCitySelect}
          />
        </div>
      )}

      {/* ── Tabela (direita) ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-3 border-b border-slate-100 bg-white shrink-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowMap(m => !m)}
                className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 transition text-slate-500"
                title={showMap ? "Ocultar mapa" : "Mostrar mapa"}
              >
                <MapPin size={15} className={showMap ? "text-proc-500" : ""} />
              </button>
              <div>
                <h1 className="text-xl font-bold text-slate-900">
                  {itMode ? "Licitações de TI & Dados" : "Licitações"}
                </h1>
                <p className="text-slate-400 text-xs">
                  {total.toLocaleString("pt-BR")} encontradas
                  {itMode ? " · ranqueadas por relevância" : ""}
                  {state ? ` · ${state}` : ""}
                  {city ? ` · ${city}` : ""}
                </p>
              </div>
            </div>

            <button
              onClick={() => { setItMode(m => !m); setPage(1); }}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                itMode ? "text-white shadow dd-gradient" : "border border-proc-200 text-proc-700 hover:bg-proc-50"
              }`}
              title="Só licitações de TI & Dados, ranqueadas por relevância"
            >
              <Cpu size={15} /> TI &amp; Dados
            </button>
          </div>

          {/* Filtros */}
          <div className="space-y-2 mt-3">
            {/* Linha 1: busca + esfera + UF + cidade (ordenação via cabeçalhos da tabela) */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="relative col-span-2 md:col-span-1">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text" value={q}
                  onChange={e => { setQ(e.target.value); setPage(1); }}
                  placeholder="Palavra-chave, órgão…"
                  className="w-full pl-8 pr-2 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-proc-400"
                />
              </div>

              <select value={sphere} onChange={e => { setSphere(e.target.value); setPage(1); }}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-proc-400 bg-white">
                <option value="">Todas esferas</option>
                <option value="federal">Federal</option>
                <option value="estadual">Estadual</option>
                <option value="municipal">Municipal</option>
              </select>

              <div className="relative">
                <input
                  type="text" value={state}
                  onChange={e => { setState(e.target.value.toUpperCase().slice(0, 2)); setPage(1); }}
                  placeholder="UF (SP, RJ…)"
                  maxLength={2}
                  className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-proc-400"
                />
                {state && (
                  <button onClick={() => { setState(""); setPage(1); }}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                    <X size={11} />
                  </button>
                )}
              </div>

              <div className="relative">
                <input
                  type="text" value={city}
                  onChange={e => { setCity(e.target.value); setPage(1); }}
                  placeholder="Cidade…"
                  className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-proc-400"
                />
                {city && (
                  <button onClick={() => { setCity(""); setPage(1); }}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                    <X size={11} />
                  </button>
                )}
              </div>

            </div>

            {/* Linha 1b: modalidade, faixa de valor, prazo */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <select value={modality} onChange={e => { setModality(e.target.value); setPage(1); }}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-proc-400">
                <option value="">Todas modalidades</option>
                <option value="pregao">Pregão</option>
                <option value="concorrencia">Concorrência</option>
                <option value="dispensa">Dispensa</option>
                <option value="inexigibilidade">Inexigibilidade</option>
                <option value="dialogo_competitivo">Diálogo Competitivo</option>
                <option value="leilao">Leilão</option>
              </select>
              <input type="number" value={minValue} min="0" step="1000"
                onChange={e => { setMinValue(e.target.value); setPage(1); }}
                placeholder="Valor mín. (R$)"
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-proc-400" />
              <input type="number" value={maxValue} min="0" step="1000"
                onChange={e => { setMaxValue(e.target.value); setPage(1); }}
                placeholder="Valor máx. (R$)"
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-proc-400" />
              <select value={daysBefore} onChange={e => { setDaysBefore(e.target.value); setPage(1); }}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-proc-400">
                <option value="">Qualquer prazo</option>
                <option value="3">Vence em até 3 dias</option>
                <option value="7">Vence em até 7 dias</option>
                <option value="15">Vence em até 15 dias</option>
                <option value="30">Vence em até 30 dias</option>
              </select>
            </div>

            {/* Linha 2: status flags */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Status:</span>
              {STATUS_OPTIONS.map(opt => {
                const active = selectedStatus.has(opt.value);
                return (
                  <button key={opt.value} onClick={() => toggleStatus(opt.value)}
                    className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border transition ${
                      active ? opt.color + " ring-1 ring-offset-1 ring-proc-300" : "bg-white border-slate-200 text-slate-400 hover:border-slate-300"
                    }`}>
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />}
                    {opt.label}
                  </button>
                );
              })}
              <button onClick={clearAllFilters}
                className="text-[10px] text-slate-400 hover:text-proc-600 flex items-center gap-0.5 transition ml-1">
                <X size={10} /> Limpar filtros
              </button>

              {/* Toggle "ainda dá tempo" */}
              <label className="ml-auto flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={onlyOpenForProposals}
                  onChange={e => { setOnlyOpenForProposals(e.target.checked); setPage(1); }}
                  className="w-3.5 h-3.5 rounded accent-proc-500"
                />
                <span className="text-[11px] text-slate-600 font-medium">
                  Apenas com prazo em aberto
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Tabela */}
        <div className="flex-1 overflow-auto">
          <div className="bg-white">
            {loading && bids.length === 0 ? (
              <div className="flex items-center justify-center py-20">
                <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
              </div>
            ) : bids.length === 0 ? (
              <div className="text-center py-20 text-slate-400">
                <FileSearch size={40} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm font-medium text-slate-500">Nenhuma licitação encontrada.</p>
                <p className="text-xs mt-1 text-slate-400">Ajuste os filtros ou sincronize no Dashboard.</p>
              </div>
            ) : (
              <table className={`w-full text-sm ${loading ? "opacity-50 transition-opacity" : "transition-opacity"}`}>
                <thead className="sticky top-0 bg-slate-50 z-10">
                  <tr className="border-b border-slate-100">
                    <th className="text-left px-4 py-2.5">
                      <button onClick={() => toggleSort("title")}
                        className="group flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 uppercase tracking-wide transition">
                        Objeto <SortIcon col="title" />
                      </button>
                    </th>
                    <th className="text-left px-3 py-2.5">
                      <button onClick={() => toggleSort("state")}
                        className="group flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 uppercase tracking-wide transition">
                        Esfera / UF <SortIcon col="state" />
                      </button>
                    </th>
                    <th className="text-left px-3 py-2.5 hidden xl:table-cell">
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Órgão</span>
                    </th>
                    <th className="text-right px-3 py-2.5">
                      <button onClick={() => toggleSort("estimated_value")}
                        className="group flex items-center gap-1.5 ml-auto text-xs font-semibold text-slate-500 hover:text-slate-800 uppercase tracking-wide transition">
                        Valor <SortIcon col="estimated_value" />
                      </button>
                    </th>
                    <th className="text-left px-3 py-2.5">
                      <button onClick={() => toggleSort("closing_date")}
                        className="group flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 uppercase tracking-wide transition">
                        Encerra <SortIcon col="closing_date" />
                      </button>
                    </th>
                    <th className="text-left px-3 py-2.5">
                      <button onClick={() => toggleSort("status")}
                        className="group flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 uppercase tracking-wide transition">
                        Status <SortIcon col="status" />
                      </button>
                    </th>
                    <th className="px-3 py-2.5 w-16" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {bids.map((bid: any) => (
                    <tr
                      key={bid.id}
                      className={`transition group cursor-pointer ${
                        bid.status === "encerrada" || bid.status === "cancelada"
                          ? "bg-slate-50/80 hover:bg-slate-100"
                          : "hover:bg-slate-50"
                      }`}
                      onClick={() => setSelectedBidId(bid.id)}
                      onDoubleClick={() => router.push(`/dashboard/bids/${bid.id}`)}
                      title="Clique para prévia · Duplo clique para íntegra"
                    >
                      <td className={`px-4 py-3 max-w-[240px] border-l-4 ${STATUS_STRIPE[bid.status] ?? "border-l-transparent"}`}>
                        <div className={`font-medium line-clamp-2 text-xs leading-snug ${
                          bid.status === "encerrada" || bid.status === "cancelada" ? "text-slate-400" : "text-slate-900"
                        }`} title={bid.title}>
                          {bid.title}
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {bid.source && (
                            <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-500 border border-slate-200">
                              {SOURCE_ICONS[bid.source] ?? "📋"} {SOURCE_LABELS[bid.source] ?? bid.source}
                            </span>
                          )}
                          {bid.branch_name && <span className="text-[11px] text-slate-400">{bid.branch_name}</span>}
                        </div>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <div className="text-xs font-medium text-slate-600">{SPHERE_LABELS[bid.sphere] ?? bid.sphere ?? "—"}</div>
                        <div className="text-[11px] text-slate-400">
                          {bid.state ?? "—"}
                          {bid.city ? ` · ${bid.city}` : ""}
                        </div>
                      </td>
                      <td className="px-3 py-3 max-w-[150px] hidden xl:table-cell">
                        <div className="text-[11px] text-slate-500 line-clamp-2" title={bid.organ_name}>{bid.organ_name ?? "—"}</div>
                      </td>
                      <td className="px-3 py-3 text-right whitespace-nowrap">
                        <span className="text-xs font-semibold text-slate-900">{fmt(bid.estimated_value)}</span>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <div className="text-[11px] text-slate-500">{fmtDate(bid.closing_date)}</div>
                        {(() => {
                          const b = deadlineBadge(bid.closing_date);
                          return (
                            <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded-full text-[10px] ${b.cls}`}>
                              {b.label}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ${STATUS_BADGE[bid.status] ?? "bg-slate-100 text-slate-600"}`}>
                          {STATUS_OPTIONS.find(o => o.value === bid.status)?.label ?? bid.status}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                          {bid.edital_url && (
                            <a href={bid.edital_url} target="_blank" rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              className="text-slate-400 hover:text-proc-500 transition" title="Ver edital">
                              <ExternalLink size={14} />
                            </a>
                          )}
                          <button
                            onClick={e => { e.stopPropagation(); startTracking(bid.id); }}
                            className="text-slate-400 hover:text-proc-500 transition" title="Acompanhar">
                            <BookmarkPlus size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Paginação */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-5 py-2.5 border-t border-slate-100 bg-white shrink-0">
            <span className="text-xs text-slate-500">
              Página {page} de {pages} · {total.toLocaleString("pt-BR")} resultados
            </span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-40 transition">
                <ChevronLeft size={15} />
              </button>
              <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                className="p-1.5 rounded-lg hover:bg-slate-100 disabled:opacity-40 transition">
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Drawer de detalhes */}
      <BidDrawer
        bidId={selectedBidId}
        token={token}
        onClose={() => setSelectedBidId(null)}
        onTrack={id => startTracking(id, true)}
      />
    </div>
  );
}
