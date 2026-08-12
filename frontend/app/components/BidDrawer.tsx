"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  X, ExternalLink, BookmarkPlus, Building2,
  FileText, Phone, Mail, Tag, AlertCircle, Maximize2, MapPin, DollarSign, Calendar,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number | null | undefined) {
  if (!v) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}
function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

const STATUS_COLOR: Record<string, string> = {
  aberta:     "bg-emerald-100 text-emerald-700",
  andamento:  "bg-blue-100 text-blue-700",
  encerrada:  "bg-slate-100 text-slate-600",
  cancelada:  "bg-red-100 text-red-600",
  programada: "bg-amber-100 text-amber-700",
};
const STATUS_LABEL: Record<string, string> = {
  aberta: "Aberta", andamento: "Em andamento", encerrada: "Encerrada",
  cancelada: "Cancelada", programada: "Programada",
};
const MODALITY_LABEL: Record<string, string> = {
  pregao: "Pregão", concorrencia: "Concorrência", tomada_preco: "Tomada de Preços",
  convite: "Convite", dispensa: "Dispensa", inexigibilidade: "Inexigibilidade",
  leilao: "Leilão", dialogo_competitivo: "Diálogo Competitivo",
};
const SPHERE_LABEL: Record<string, string> = {
  federal: "Federal", estadual: "Estadual", municipal: "Municipal",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{title}</h3>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function Row({ icon: Icon, label, value }: { icon: any; label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-2.5">
      <Icon size={13} className="text-slate-400 mt-0.5 shrink-0" />
      <div className="min-w-0">
        <div className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</div>
        <div className="text-sm text-slate-800 break-words">{value}</div>
      </div>
    </div>
  );
}

interface Props {
  bidId: number | null;
  token: string;
  onClose: () => void;
  onTrack: (bidId: number) => void;
}

export default function BidDrawer({ bidId, token, onClose, onTrack }: Props) {
  const [bid, setBid]       = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!bidId) { setBid(null); return; }
    setLoading(true);
    fetch(`${API}/api/bids/${bidId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => { setBid(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [bidId, token]);

  const open = !!bidId;

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 h-full w-[460px] max-w-full bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 shrink-0">
          <h2 className="font-semibold text-slate-900 text-sm">Prévia da Licitação</h2>
          <div className="flex items-center gap-2">
            {bid && (
              <button
                onClick={() => { router.push(`/dashboard/bids/${bid.id}`); onClose(); }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-proc-500 hover:bg-proc-600 text-white rounded-lg text-xs font-medium transition"
                title="Ver licitação na íntegra"
              >
                <Maximize2 size={13} /> Ver na íntegra
              </button>
            )}
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <span className="w-7 h-7 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
            </div>
          ) : !bid ? (
            <div className="flex items-center justify-center h-40 text-slate-400">
              <AlertCircle size={24} className="mr-2 opacity-40" />
              Dados não disponíveis
            </div>
          ) : (
            <div className="p-5 space-y-6">
              {/* Título e status */}
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <span className={`shrink-0 px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_COLOR[bid.status] ?? "bg-slate-100 text-slate-600"}`}>
                    {STATUS_LABEL[bid.status] ?? bid.status}
                  </span>
                  {bid.modality && (
                    <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                      {MODALITY_LABEL[bid.modality] ?? bid.modality}
                    </span>
                  )}
                </div>
                <h2 className="text-base font-semibold text-slate-900 leading-snug">{bid.title}</h2>
                {bid.description && bid.description !== bid.title && (
                  <p className="text-sm text-slate-500 mt-2 leading-relaxed">{bid.description}</p>
                )}
              </div>

              {/* Valores */}
              <Section title="Valores">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-3">
                    <div className="text-[10px] text-emerald-600 font-semibold uppercase tracking-wide mb-0.5">Valor estimado</div>
                    <div className="text-lg font-bold text-emerald-800">{fmt(bid.estimated_value)}</div>
                  </div>
                  {bid.maximum_value && (
                    <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                      <div className="text-[10px] text-slate-500 font-semibold uppercase tracking-wide mb-0.5">Valor máximo</div>
                      <div className="text-lg font-bold text-slate-700">{fmt(bid.maximum_value)}</div>
                    </div>
                  )}
                </div>
              </Section>

              {/* Datas */}
              <Section title="Datas">
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "Publicação", date: bid.publication_date },
                    { label: "Abertura", date: bid.opening_date },
                    { label: "Encerramento", date: bid.closing_date },
                  ].map(({ label, date }) => date && (
                    <div key={label} className="bg-slate-50 rounded-xl p-2.5 text-center">
                      <div className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</div>
                      <div className="text-xs font-semibold text-slate-700 mt-0.5">{fmtDate(date)}</div>
                    </div>
                  ))}
                </div>
              </Section>

              {/* Localização */}
              <Section title="Órgão e Localização">
                <Row icon={Building2} label="Órgão" value={bid.organ_name} />
                {bid.organ_cnpj && <Row icon={Tag} label="CNPJ" value={bid.organ_cnpj} />}
                <Row
                  icon={MapPin}
                  label="Localização"
                  value={[
                    SPHERE_LABEL[bid.sphere] ?? bid.sphere,
                    bid.state,
                    bid.city,
                  ].filter(Boolean).join(" · ")}
                />
              </Section>

              {/* Requisitos */}
              {(bid.min_patrimony || bid.min_revenue || bid.years_of_operation || bid.requires_sme || bid.requires_mei) && (
                <Section title="Requisitos">
                  {bid.min_patrimony && <Row icon={DollarSign} label="Patrimônio mínimo" value={fmt(bid.min_patrimony)} />}
                  {bid.min_revenue && <Row icon={DollarSign} label="Faturamento mínimo" value={fmt(bid.min_revenue)} />}
                  {bid.years_of_operation && <Row icon={Calendar} label="Tempo de operação" value={`${bid.years_of_operation} anos`} />}
                  {bid.requires_sme && (
                    <div className="flex items-center gap-2 text-xs text-proc-700 bg-proc-50 rounded-lg px-3 py-2">
                      <Tag size={12} /> Reservado para ME/EPP
                    </div>
                  )}
                  {bid.requires_mei && (
                    <div className="flex items-center gap-2 text-xs text-proc-700 bg-proc-50 rounded-lg px-3 py-2">
                      <Tag size={12} /> Reservado para MEI
                    </div>
                  )}
                </Section>
              )}

              {/* Contato */}
              {(bid.contact_name || bid.contact_email || bid.contact_phone) && (
                <Section title="Contato">
                  <Row icon={Building2} label="Responsável" value={bid.contact_name} />
                  <Row icon={Mail} label="E-mail" value={bid.contact_email} />
                  <Row icon={Phone} label="Telefone" value={bid.contact_phone} />
                </Section>
              )}

              {/* Categoria */}
              {(bid.category_name || bid.branch_name) && (
                <Section title="Classificação">
                  {bid.branch_name && <Row icon={Tag} label="Ramo" value={bid.branch_name} />}
                  {bid.category_name && <Row icon={Tag} label="Categoria" value={`${bid.category_code ? bid.category_code + " — " : ""}${bid.category_name}`} />}
                </Section>
              )}

              {/* Fonte */}
              <div className="pt-2 text-[11px] text-slate-400 border-t border-slate-100">
                Fonte: <span className="uppercase font-medium">{bid.source}</span>
                {bid.last_scraped && ` · Atualizado em ${fmtDate(bid.last_scraped?.split("T")[0])}`}
              </div>
            </div>
          )}
        </div>

        {/* Footer com ações */}
        {bid && (
          <div className="shrink-0 px-5 py-4 border-t border-slate-100 space-y-2">
            <button
              onClick={() => { router.push(`/dashboard/bids/${bid.id}`); onClose(); }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-semibold transition"
            >
              <Maximize2 size={15} /> Ver licitação na íntegra
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={() => { onTrack(bid.id); onClose(); }}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 border border-slate-200 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-50 transition"
              >
                <BookmarkPlus size={14} /> Acompanhar
              </button>
              {bid.edital_url && (
                <a href={bid.edital_url} target="_blank" rel="noopener noreferrer"
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 border border-slate-200 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-50 transition">
                  <FileText size={14} /> Edital
                </a>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
