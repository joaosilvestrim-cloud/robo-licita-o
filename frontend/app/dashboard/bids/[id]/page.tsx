"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, ExternalLink, BookmarkPlus, FileText, Building2,
  Calendar, DollarSign, Tag, Phone, Mail, AlertCircle,
  Package, Download, Globe, CheckCircle, Clock, XCircle,
} from "lucide-react";

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

// ─── extrai cnpj/tipo/ano/seq do external_id ─────────────────────────────────
// Formato: "44477909000100-1-000303/2026"
function parseExternalId(externalId: string) {
  const m = externalId.match(/^(\d+)-(\d+)-0*(\d+)\/(\d+)$/);
  if (!m) return null;
  return { cnpj: m[1], tipo: m[2], seq: m[3], ano: m[4] };
}

function pncpPortalUrl(parsed: ReturnType<typeof parseExternalId>) {
  if (!parsed) return null;
  return `https://pncp.gov.br/app/editais/${parsed.cnpj}/${parsed.tipo}/${parsed.ano}/${parsed.seq}`;
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

    // Itens/lotes
    fetch(`${PNCP_B}/orgaos/${cnpj}/compras/${ano}/${seq}/itens?pagina=1&tamanhoPagina=50`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (Array.isArray(d)) setItems(d); })
      .catch(() => {});

    // Arquivos/documentos
    fetch(`${PNCP_B}/orgaos/${cnpj}/compras/${ano}/${seq}/arquivos`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (Array.isArray(d)) setFiles(d); })
      .catch(() => {});
  }, [bid?.external_id]);

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
    <div className="min-h-screen bg-slate-50 overflow-auto">
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
                        {item.numeroItem ?? item.item ?? i + 1}
                      </td>
                      <td className="py-2.5 px-3 text-slate-700 max-w-sm">
                        <div className="line-clamp-2">{item.descricao ?? item.materialServico?.descricao ?? "—"}</div>
                        {item.materialServico?.codigo && (
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{item.materialServico.codigo}</div>
                        )}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap text-slate-600 text-xs">
                        {item.quantidade ?? "—"} {item.unidadeMedida ?? ""}
                      </td>
                      <td className="py-2.5 px-3 text-right whitespace-nowrap text-slate-700 text-xs">
                        {fmt(item.valorUnitarioEstimado)}
                      </td>
                      <td className="py-2.5 px-3 text-right whitespace-nowrap font-medium text-slate-900 text-xs">
                        {fmt(item.valorTotal ?? (item.valorUnitarioEstimado && item.quantidade
                          ? item.valorUnitarioEstimado * item.quantidade : null))}
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
