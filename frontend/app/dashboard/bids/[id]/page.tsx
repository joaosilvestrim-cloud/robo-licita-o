"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, ExternalLink, BookmarkPlus, FileText, Building2,
  Calendar, DollarSign, Tag, Phone, Mail, AlertCircle,
  Package, Download, Globe, CheckCircle, Clock, XCircle, Users, Trophy, Lock, ChevronRight, TrendingDown, Gavel, Info,
} from "lucide-react";

// situação do licitante no resultado (estilo "análise dos licitantes")
function SituBadge({ situacao, isWinner }: { situacao?: string; isWinner?: boolean }) {
  const s = (situacao || "").toLowerCase();
  const cls =
    isWinner || s.includes("vencedor")
      ? "bg-emerald-100 text-emerald-700"
      : s.includes("desclass") || s.includes("cancel") || s.includes("inabilit")
      ? "bg-red-100 text-red-700"
      : "bg-slate-100 text-slate-500";
  const label = isWinner && !s.includes("vencedor") ? "Vencedor" : (situacao || "—");
  return <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${cls}`}>{label}</span>;
}

const API     = process.env.NEXT_PUBLIC_API_URL ?? "";
const PNCP_B  = "https://pncp.gov.br/api/consulta/v1";

// ─── formatadores ────────────────────────────────────────────────────────────
function fmt(v: number | null | undefined) {
  if (!v) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}
function fmtCompact(v: number | null | undefined) {
  if (!v) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact" }).format(v);
}
function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  const s = d.includes("T") ? d : d + "T00:00:00";
  return new Date(s).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}

// ─── mapeamentos ─────────────────────────────────────────────────────────────
const STATUS_UI: Record<string, { label: string; icon: any; cls: string }> = {
  aberta:     { label: "Aberta",        icon: CheckCircle, cls: "bg-emerald-100 text-emerald-700" },
  andamento:  { label: "Em andamento",  icon: Clock,       cls: "bg-blue-100 text-blue-700" },
  encerrada:  { label: "Encerrada",     icon: XCircle,     cls: "bg-slate-100 text-slate-600" },
  cancelada:  { label: "Cancelada",     icon: XCircle,     cls: "bg-red-100 text-red-600" },
  programada: { label: "Programada",    icon: Clock,       cls: "bg-amber-100 text-amber-700" },
};
const SPHERE_LABEL: Record<string, string> = {
  federal: "Federal", estadual: "Estadual", municipal: "Municipal",
};
const MODALITY_LABEL: Record<string, string> = {
  pregao: "Pregão Eletrônico", concorrencia: "Concorrência",
  tomada_preco: "Tomada de Preços", convite: "Convite",
  dispensa: "Dispensa de Licitação", inexigibilidade: "Inexigibilidade",
  leilao: "Leilão", dialogo_competitivo: "Diálogo Competitivo",
};

// Modo de disputa (PNCP): como os fornecedores apresentam os preços + o cuidado estratégico
const DISPUTE_INFO: Record<string, { resumo: string; cuidado: string }> = {
  "aberto": {
    resumo: "Leilão ao contrário: lances visíveis e sucessivamente menores, com prorrogações previstas no edital.",
    cuidado: "Defina seu preço mínimo antes. É o mais transparente, mas a disputa por preço fica agressiva.",
  },
  "fechado": {
    resumo: "Cada empresa envia uma proposta sigilosa. As propostas abrem simultaneamente e vence a melhor pelo critério do edital.",
    cuidado: "Apresente seu melhor preço já de início. Não cabe em julgamento por menor preço/maior desconto (art. 56, Lei 14.133).",
  },
  "aberto-fechado": {
    resumo: "Primeiro a disputa aberta; depois os melhores classificados (faixa de ~10%) dão um lance final sigiloso.",
    cuidado: "Guarde margem para a rodada final. Não reduza demais na fase aberta (IN SEGES/ME 73/2022, art. 24).",
  },
  "fechado-aberto": {
    resumo: "Propostas iniciais sigilosas; classificam-se as melhores (faixa de ~10%) e só elas vão à fase aberta de lances.",
    cuidado: "Comece competitivo: se a proposta inicial vier alta, você nem avança para a disputa (art. 25).",
  },
  "dispensa com disputa": {
    resumo: "Contratação direta por dispensa, mas com disputa eletrônica de propostas para buscar o melhor preço.",
    cuidado: "Bom para a DriveData: contratos menores, processo rápido, porta de entrada em novos órgãos. Confira habilitação e prazo curto.",
  },
};

// ─── extrai cnpj/tipo/ano/seq do external_id ─────────────────────────────────
// Formato: "44477909000100-1-000303/2026"
function parseExternalId(externalId: string | null | undefined) {
  if (!externalId) return null;
  const m = externalId.match(/^(\d+)-(\d+)-0*(\d+)\/(\d+)$/);
  if (!m) return null;
  return { cnpj: m[1], tipo: m[2], seq: m[3], ano: m[4] };
}

function pncpPortalUrl(parsed: ReturnType<typeof parseExternalId>) {
  if (!parsed) return null;
  // Formato correto do PNCP: /editais/{cnpj}/{ano}/{sequencial} (sem o "tipo")
  return `https://pncp.gov.br/app/editais/${parsed.cnpj}/${parsed.ano}/${parsed.seq}`;
}

// ─── componentes auxiliares ──────────────────────────────────────────────────
function Section({ title, icon: Icon, children }: { title: string; icon?: any; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-card p-6">
      <h2 className="flex items-center gap-2 font-semibold text-slate-800 mb-4 text-sm uppercase tracking-wide">
        {Icon && <Icon size={15} className="text-proc-400" />}
        {title}
      </h2>
      {children}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">{label}</div>
      <div className={`text-sm text-slate-800 mt-0.5 ${mono ? "font-mono text-xs" : ""}`}>{value}</div>
    </div>
  );
}

// ─── página ──────────────────────────────────────────────────────────────────
export default function BidDetailPage() {
  const { id } = useParams();
  const router  = useRouter();
  const token   = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";

  const [bid,     setBid]     = useState<any>(null);
  const [detail,  setDetail]  = useState<any>(null);   // detalhe ao vivo do PNCP
  const [items,   setItems]   = useState<any[]>([]);   // itens/lotes
  const [files,   setFiles]   = useState<any[]>([]);   // documentos
  const [loading, setLoading] = useState(true);
  const [tracking, setTracking] = useState(false);
  const [elig, setElig] = useState<any>(null);   // análise de aderência (Candidatura Assistida)
  const [comp, setComp] = useState<any>(null);   // inteligência de concorrência (quem venceu)

  // 1) busca o bid do nosso DB
  useEffect(() => {
    if (!id || !token) return;
    fetch(`${API}/api/bids/${id}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setBid(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id, token]);

  // 2) depois que temos o external_id, busca ao vivo no PNCP
  useEffect(() => {
    if (!bid?.external_id) return;
    const parsed = parseExternalId(bid.external_id);
    if (!parsed) return;
    const { cnpj, ano, seq } = parsed;

    // Detalhe completo
    fetch(`${PNCP_B}/orgaos/${cnpj}/compras/${ano}/${seq}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && !d.status) setDetail(d); })
      .catch(() => {});

    // Itens/lotes (via backend: base correta do PNCP + sem CORS)
    fetch(`${API}/api/bids/${bid.id}/items`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.items) setItems(d.items); })
      .catch(() => {});

    // Arquivos/documentos do edital
    fetch(`${API}/api/bids/${bid.id}/files`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.files) setFiles(d.files); })
      .catch(() => {});
  }, [bid?.external_id, bid?.id, token]);

  // análise de aderência do perfil (Candidatura Assistida — Fase A)
  useEffect(() => {
    if (!bid?.id || !token) return;
    fetch(`${API}/api/bids/${bid.id}/eligibility`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => setElig(d))
      .catch(() => {});
  }, [bid?.id, token]);

  // inteligência de concorrência (quem venceu). Só chama o PNCP para encerradas —
  // abertas só mostram o aviso de sigilo, sem custo de rede.
  useEffect(() => {
    if (!bid?.id || !token) return;
    const isOpen = ["aberta", "andamento", "programada"].includes(bid.status);
    if (isOpen) { setComp({ has_result: false }); return; }
    fetch(`${API}/api/bids/${bid.id}/competitors`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => setComp(d))
      .catch(() => {});
  }, [bid?.id, bid?.status, token]);

  async function startTracking() {
    setTracking(true);
    const res = await fetch(`${API}/api/tracking/${bid.id}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: "{}",
    });
    const d = await res.json().catch(() => ({}));
    alert(res.ok ? "Adicionado ao acompanhamento!" : (d.detail ?? "Erro."));
    setTracking(false);
  }

  if (loading) return (
    <div className="flex items-center justify-center h-screen">
      <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
    </div>
  );

  if (!bid) return (
    <div className="flex flex-col items-center justify-center h-screen gap-3 text-slate-400">
      <AlertCircle size={40} className="opacity-30" />
      <p className="text-sm">Licitação não encontrada.</p>
      <button onClick={() => router.back()} className="text-proc-500 text-sm hover:underline">Voltar</button>
    </div>
  );

  const parsed    = parseExternalId(bid.external_id);
  const portalUrl = pncpPortalUrl(parsed);
  const statusUi  = STATUS_UI[bid.status] ?? { label: bid.status, icon: Clock, cls: "bg-slate-100 text-slate-600" };
  const StatusIcon = statusUi.icon;

  // Preferir dados ao vivo do PNCP quando disponíveis
  const title       = detail?.objetoCompra || bid.title;
  const description = detail?.informacaoComplementar || bid.description;
  const estValue    = detail?.valorTotalEstimado ?? bid.estimated_value;
  const maxValue    = detail?.valorTotalHomologado ?? bid.maximum_value;
  const openDate    = detail?.dataAberturaProposta     ? detail.dataAberturaProposta.split("T")[0] : bid.opening_date;
  const closeDate   = detail?.dataEncerramentoProposta ? detail.dataEncerramentoProposta.split("T")[0] : bid.closing_date;
  const pubDate     = detail?.dataPublicacaoPncp       ? detail.dataPublicacaoPncp.split("T")[0] : bid.publication_date;

  return (
    <div className="h-screen bg-slate-50 overflow-y-auto">
      {/* Topbar */}
      <div className="sticky top-0 z-30 bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
        <button onClick={() => router.back()}
          className="flex items-center gap-2 text-slate-500 hover:text-slate-800 text-sm transition">
          <ArrowLeft size={16} /> Voltar
        </button>
        <div className="flex items-center gap-2">
          {portalUrl && (
            <a href={portalUrl} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-1.5 border border-proc-200 text-proc-700 rounded-xl text-sm font-medium hover:bg-proc-50 transition">
              <Globe size={14} /> Ver no PNCP
            </a>
          )}
          {bid.edital_url && (
            <a href={bid.edital_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-1.5 border border-slate-200 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-50 transition">
              <FileText size={14} /> Edital
            </a>
          )}
          <button onClick={startTracking} disabled={tracking}
            className="flex items-center gap-2 px-4 py-1.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition disabled:opacity-60">
            <BookmarkPlus size={14} /> {tracking ? "Aguarde…" : "Acompanhar"}
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-5">

        {/* Hero */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-card p-7">
          <div className="flex items-start gap-3 mb-4 flex-wrap">
            <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${statusUi.cls}`}>
              <StatusIcon size={12} /> {statusUi.label}
            </span>
            {bid.modality && (
              <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                {MODALITY_LABEL[bid.modality] ?? bid.modality}
              </span>
            )}
            {bid.sphere && (
              <span className="px-3 py-1 rounded-full text-xs font-medium bg-proc-50 text-proc-700">
                {SPHERE_LABEL[bid.sphere] ?? bid.sphere}
              </span>
            )}
            {bid.dispute_mode && bid.dispute_mode.toLowerCase() !== "não se aplica" && (
              <span className="px-3 py-1 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
                Disputa: {bid.dispute_mode}
              </span>
            )}
            {bid.source && (
              <span className="px-2 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-400 uppercase tracking-widest ml-auto">
                {bid.source}
              </span>
            )}
          </div>

          <h1 className="text-xl font-bold text-slate-900 leading-snug mb-3">{title}</h1>

          {description && description !== title && (
            <p className="text-sm text-slate-500 leading-relaxed mb-4 bg-slate-50 rounded-xl p-4 border border-slate-100">
              {description}
            </p>
          )}

          {/* Modo de disputa: como os fornecedores apresentam os preços + estratégia */}
          {bid.dispute_mode && DISPUTE_INFO[bid.dispute_mode.toLowerCase()] && (
            <div className="mb-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
              <div className="flex items-center gap-2 mb-1.5">
                <Gavel size={15} className="text-indigo-600" />
                <span className="text-sm font-semibold text-indigo-900">Modo de disputa: {bid.dispute_mode}</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{DISPUTE_INFO[bid.dispute_mode.toLowerCase()].resumo}</p>
              <div className="flex items-start gap-1.5 mt-2 text-xs text-indigo-800">
                <Info size={13} className="shrink-0 mt-0.5" />
                <span><b>Estratégia:</b> {DISPUTE_INFO[bid.dispute_mode.toLowerCase()].cuidado}</span>
              </div>
            </div>
          )}

          {/* Valores em destaque */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
            {estValue != null && (
              <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4">
                <div className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wide">Valor Estimado</div>
                <div className="text-2xl font-bold text-emerald-800 mt-1">{fmtCompact(estValue)}</div>
                <div className="text-xs text-emerald-600 mt-0.5">{fmt(estValue)}</div>
              </div>
            )}
            {maxValue != null && (
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Valor Máximo</div>
                <div className="text-2xl font-bold text-slate-700 mt-1">{fmtCompact(maxValue)}</div>
                <div className="text-xs text-slate-400 mt-0.5">{fmt(maxValue)}</div>
              </div>
            )}
            {closeDate && (
              <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                <div className="text-[10px] font-semibold text-amber-600 uppercase tracking-wide">Encerramento</div>
                <div className="text-base font-bold text-amber-800 mt-1">{fmtDate(closeDate)}</div>
              </div>
            )}
          </div>
        </div>

        {/* Análise de aderência — Candidatura Assistida (Fase A) */}
        {elig && (() => {
          const V: Record<string, { label: string; cls: string; bar: string; Icon: any }> = {
            elegivel: { label: "Elegível — prepare a candidatura", cls: "text-emerald-700 bg-emerald-50 border-emerald-200", bar: "bg-emerald-500", Icon: CheckCircle },
            revisar:  { label: "Revisar — ajuste algum ponto",     cls: "text-amber-700 bg-amber-50 border-amber-200",       bar: "bg-amber-500",   Icon: AlertCircle },
            fora:     { label: "Fora do seu perfil",               cls: "text-slate-600 bg-slate-100 border-slate-200",      bar: "bg-slate-400",   Icon: XCircle },
          };
          const v = V[elig.verdict] ?? V.revisar;
          const VIcon = v.Icon;
          const cIcon = (s: string) => s === "ok"
            ? <CheckCircle size={15} className="text-emerald-500 shrink-0" />
            : s === "warn"
            ? <AlertCircle size={15} className="text-amber-500 shrink-0" />
            : <XCircle size={15} className="text-red-400 shrink-0" />;
          return (
            <div className="bg-white rounded-2xl border border-slate-100 shadow-card overflow-hidden">
              <div className="dd-gradient px-6 py-3 flex items-center gap-2 text-white">
                <Package size={16} />
                <span className="text-sm font-semibold">Análise de aderência</span>
                <span className="text-[11px] text-white/70 ml-1">Candidatura Assistida</span>
                {elig.matched_profile && (
                  <span className="text-[11px] bg-white/15 rounded-full px-2 py-0.5 ml-auto">perfil: {elig.matched_profile}</span>
                )}
              </div>
              <div className="p-6">
                <div className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-sm font-semibold border ${v.cls}`}>
                  <VIcon size={15} /> {v.label}
                </div>
                <div className="mt-4 grid sm:grid-cols-2 gap-x-6 gap-y-2.5">
                  {(elig.checks ?? []).map((c: any, i: number) => (
                    <div key={i} className="flex items-start gap-2.5 text-sm">
                      {cIcon(c.status)}
                      <div>
                        <span className="text-slate-700 font-medium">{c.label}</span>
                        <span className="text-slate-400"> · {c.detail}</span>
                      </div>
                    </div>
                  ))}
                </div>
                {elig.hint && <p className="text-xs text-slate-400 mt-4">{elig.hint}</p>}
                <div className="flex items-center gap-3 mt-5 pt-4 border-t border-slate-100">
                  <button
                    disabled
                    title="Geração de proposta e documentos — em breve (Fase B)"
                    className="flex items-center gap-2 text-white px-4 py-2 rounded-xl text-sm font-semibold dd-gradient opacity-60 cursor-not-allowed">
                    <FileText size={15} /> Preparar candidatura
                  </button>
                  <span className="text-xs text-slate-400">Geração de proposta e documentos chega na Fase B.</span>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Concorrência — quem venceu (dados públicos do PNCP após homologação) */}
        {comp && (() => {
          const isOpen = bid.status === "aberta" || bid.status === "andamento" || bid.status === "programada";
          return (
            <div className="bg-white rounded-2xl border border-slate-100 shadow-card overflow-hidden">
              <div className="bg-slate-900 px-6 py-3 flex items-center gap-2 text-white">
                <Users size={16} />
                <span className="text-sm font-semibold">Concorrência</span>
                <span className="text-[11px] text-white/60 ml-1">quem venceu · dados públicos do PNCP</span>
              </div>
              <div className="p-6">
                {isOpen ? (
                  <div className="flex items-start gap-3 text-sm text-slate-500">
                    <Lock size={16} className="text-slate-400 shrink-0 mt-0.5" />
                    <p>Propostas <b>sigilosas até a sessão</b> (por lei). O vencedor e os valores aparecem aqui <b>após a homologação</b>.</p>
                  </div>
                ) : comp.has_result ? (
                  <>
                    {/* benchmark de preço: estimado vs homologado */}
                    {(comp.estimated_total || comp.homologated_total) && (
                      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mb-4 pb-3 border-b border-slate-50 text-xs">
                        {comp.estimated_total ? <span className="text-slate-500">Estimado <b className="text-slate-700">{fmt(comp.estimated_total)}</b></span> : null}
                        {comp.homologated_total ? <span className="text-slate-500">Homologado <b className="text-emerald-700">{fmt(comp.homologated_total)}</b></span> : null}
                        {comp.estimated_total && comp.homologated_total ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold">
                            <TrendingDown size={12} /> {Math.round((1 - comp.homologated_total / comp.estimated_total) * 100)}% abaixo do estimado
                          </span>
                        ) : null}
                      </div>
                    )}

                    <div className="space-y-2">
                      {comp.winners.map((w: any, i: number) => (
                        <div key={w.document} className={`flex items-center gap-3 p-3 rounded-xl border ${i === 0 ? "bg-emerald-50 border-emerald-100" : "bg-slate-50 border-slate-100"}`}>
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${i === 0 ? "bg-emerald-500 text-white" : "bg-slate-200 text-slate-600"}`}>
                            {i === 0 ? <Trophy size={13} /> : <span className="text-xs font-bold">{i + 1}</span>}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-slate-800 truncate">{w.name}</div>
                            <div className="text-[11px] text-slate-400 font-mono">
                              CNPJ {w.document} · {w.items_won} {w.items_won === 1 ? "item" : "itens"}{w.porte ? ` · ${w.porte}` : ""}
                            </div>
                          </div>
                          <div className="text-sm font-semibold text-slate-900 shrink-0">{fmt(w.total_value)}</div>
                        </div>
                      ))}
                    </div>

                    {/* análise dos licitantes por item (ranking 1º/2º/3º com situação) */}
                    {comp.items?.length > 0 && (
                      <details className="mt-4 group">
                        <summary className="cursor-pointer list-none text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1 select-none">
                          <ChevronRight size={13} className="transition group-open:rotate-90" />
                          Análise dos licitantes por item ({comp.items.length})
                        </summary>
                        <div className="mt-3 space-y-2.5">
                          {comp.items.map((it: any) => (
                            <div key={it.numero} className="border border-slate-100 rounded-xl p-3">
                              <div className="flex items-center justify-between gap-2 mb-1.5">
                                <span className="text-xs font-semibold text-slate-700">Item {it.numero}</span>
                                {it.valor_estimado ? <span className="text-[11px] text-slate-400">estimado {fmt(it.valor_estimado)}</span> : null}
                              </div>
                              {it.descricao ? <p className="text-[11px] text-slate-500 line-clamp-2 mb-2">{it.descricao}</p> : null}
                              <div className="space-y-1">
                                {it.results.map((r: any, ri: number) => (
                                  <div key={r.document + ri} className="flex items-center gap-2 text-xs">
                                    <span className="w-5 text-slate-400 shrink-0 text-center">{r.ordem ? `${r.ordem}º` : "–"}</span>
                                    <SituBadge situacao={r.situacao} isWinner={r.is_winner} />
                                    <span className="flex-1 truncate text-slate-700">{r.name}</span>
                                    {r.desconto ? <span className="text-[10px] text-slate-400 shrink-0">-{Math.round(r.desconto)}%</span> : null}
                                    {r.valor_total > 0 ? <span className="font-medium text-slate-800 shrink-0">{fmt(r.valor_total)}</span> : null}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}

                    <p className="text-[11px] text-slate-400 mt-3">💡 Use como benchmark de preço e para mapear concorrentes recorrentes no seu nicho.</p>
                  </>
                ) : (
                  <p className="text-sm text-slate-500">Resultado ainda não publicado no PNCP para esta licitação.</p>
                )}
              </div>
            </div>
          );
        })()}

        <div className="grid md:grid-cols-2 gap-5">
          {/* Datas */}
          <Section title="Cronograma" icon={Calendar}>
            <div className="space-y-3">
              <Field label="Data de Publicação"  value={fmtDate(pubDate)} />
              <Field label="Abertura de Propostas" value={fmtDate(openDate)} />
              <Field label="Encerramento de Propostas" value={fmtDate(closeDate)} />
              <Field label="Última atualização"  value={fmtDate(bid.updated_at?.split("T")[0])} />
            </div>
          </Section>

          {/* Órgão */}
          <Section title="Órgão Contratante" icon={Building2}>
            <div className="space-y-3">
              <Field label="Nome"    value={bid.organ_name} />
              <Field label="CNPJ"    value={bid.organ_cnpj} mono />
              <Field label="Esfera"  value={SPHERE_LABEL[bid.sphere] ?? bid.sphere} />
              <Field label="Estado"  value={bid.state} />
              <Field label="Cidade"  value={bid.city} />
              {bid.city_code && <Field label="Código IBGE" value={bid.city_code} mono />}
            </div>
          </Section>

          {/* Classificação */}
          <Section title="Classificação" icon={Tag}>
            <div className="space-y-3">
              <Field label="Modalidade"  value={MODALITY_LABEL[bid.modality] ?? bid.modality} />
              <Field label="Ramo"        value={bid.branch_name} />
              <Field label="Categoria"   value={bid.category_name} />
              <Field label="Cód. categoria" value={bid.category_code} mono />
              <Field label="Tipo de objeto" value={bid.object_type} />
            </div>
          </Section>

          {/* Requisitos */}
          <Section title="Requisitos de Habilitação" icon={CheckCircle}>
            <div className="space-y-3">
              {bid.min_patrimony && <Field label="Patrimônio mínimo"   value={fmt(bid.min_patrimony)} />}
              {bid.min_revenue   && <Field label="Faturamento mínimo"  value={fmt(bid.min_revenue)} />}
              {bid.years_of_operation && <Field label="Tempo de operação" value={`${bid.years_of_operation} anos`} />}
              {!bid.min_patrimony && !bid.min_revenue && !bid.years_of_operation && (
                <p className="text-sm text-slate-400 italic">Não informado</p>
              )}
              {bid.requires_sme && (
                <div className="flex items-center gap-2 bg-proc-50 text-proc-700 rounded-lg px-3 py-2 text-xs font-medium">
                  <Tag size={12} /> Reservado para ME/EPP
                </div>
              )}
              {bid.requires_mei && (
                <div className="flex items-center gap-2 bg-proc-50 text-proc-700 rounded-lg px-3 py-2 text-xs font-medium">
                  <Tag size={12} /> Reservado para MEI
                </div>
              )}
            </div>
          </Section>

          {/* Contato */}
          {(bid.contact_name || bid.contact_email || bid.contact_phone) && (
            <Section title="Contato" icon={Phone}>
              <div className="space-y-3">
                <Field label="Responsável" value={bid.contact_name} />
                {bid.contact_email && (
                  <div>
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">E-mail</div>
                    <a href={`mailto:${bid.contact_email}`}
                      className="text-sm text-proc-600 hover:underline flex items-center gap-1 mt-0.5">
                      <Mail size={12} /> {bid.contact_email}
                    </a>
                  </div>
                )}
                <Field label="Telefone" value={bid.contact_phone} />
              </div>
            </Section>
          )}

          {/* Identificação */}
          <Section title="Identificação" icon={Tag}>
            <div className="space-y-3">
              <Field label="Número de controle PNCP" value={bid.external_id} mono />
              {parsed && <Field label="CNPJ do órgão" value={parsed.cnpj} mono />}
              {parsed && <Field label="Ano / Sequencial" value={`${parsed.ano} / ${parsed.seq}`} mono />}
              <Field label="Fonte de dados" value={bid.source?.toUpperCase()} />
            </div>
          </Section>
        </div>

        {/* Itens / Lotes */}
        {items.length > 0 && (
          <Section title={`Itens / Lotes (${items.length})`} icon={Package}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Nº</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Descrição</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Qtd</th>
                    <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Valor unit.</th>
                    <th className="text-right py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {items.map((item: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50 transition">
                      <td className="py-2.5 px-3 text-slate-500 text-xs whitespace-nowrap">
                        {item.numero ?? i + 1}
                      </td>
                      <td className="py-2.5 px-3 text-slate-700 max-w-sm">
                        <div className="line-clamp-2">{item.descricao || "—"}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5 flex gap-2">
                          {item.tipo && <span>{item.tipo}</span>}
                          {item.criterio && <span>· {item.criterio}</span>}
                          {item.beneficio && item.beneficio !== "Não se aplica" && <span className="text-emerald-600">· {item.beneficio}</span>}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap text-slate-600 text-xs">
                        {item.quantidade ?? "—"} {item.unidade ?? ""}
                      </td>
                      <td className="py-2.5 px-3 text-right whitespace-nowrap text-slate-700 text-xs">
                        {fmt(item.valor_unitario)}
                      </td>
                      <td className="py-2.5 px-3 text-right whitespace-nowrap font-medium text-slate-900 text-xs">
                        {fmt(item.valor_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        )}

        {/* Documentos */}
        {files.length > 0 && (
          <Section title={`Documentos (${files.length})`} icon={FileText}>
            <div className="space-y-2">
              {files.map((f: any, i: number) => (
                <a key={i}
                  href={f.url ?? f.uri ?? f.link ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 p-3 rounded-xl border border-slate-100 hover:bg-slate-50 hover:border-proc-200 transition group">
                  <div className="w-9 h-9 rounded-lg bg-proc-50 flex items-center justify-center shrink-0">
                    <Download size={16} className="text-proc-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-800 truncate group-hover:text-proc-700">
                      {f.titulo ?? f.nome ?? f.descricao ?? `Documento ${i + 1}`}
                    </div>
                    {f.tipo && <div className="text-xs text-slate-400">{f.tipo}</div>}
                  </div>
                  <ExternalLink size={14} className="text-slate-300 group-hover:text-proc-400 shrink-0" />
                </a>
              ))}
            </div>
          </Section>
        )}

        {/* Links externos */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-card p-6">
          <h2 className="font-semibold text-slate-800 mb-4 text-sm uppercase tracking-wide">Links externos</h2>
          <div className="flex flex-wrap gap-3">
            {portalUrl && (
              <a href={portalUrl} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-5 py-3 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition">
                <Globe size={16} /> Abrir no portal PNCP
              </a>
            )}
            {bid.edital_url && (
              <a href={bid.edital_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-5 py-3 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-medium transition">
                <FileText size={16} /> Ver edital / sistema de origem
              </a>
            )}
            {bid.details_url && bid.details_url !== bid.edital_url && (
              <a href={bid.details_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-5 py-3 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-medium transition">
                <ExternalLink size={16} /> Detalhes no sistema original
              </a>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
