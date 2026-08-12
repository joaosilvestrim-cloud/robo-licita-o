"use client";
import { useEffect, useState } from "react";
import {
  Building2, MapPin, Tag, Calendar, DollarSign, Users, Shield,
  Plus, Trash2, Star, Search, X, AlertCircle, CheckCircle,
  ChevronDown, ChevronUp, Loader2, Phone, Mail, Briefcase,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function fmt(v: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
}
function fmtCnpj(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 14);
  return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}
function fmtDate(d: string | null | undefined) {
  if (!d) return null;
  try { return new Date(d + "T00:00:00").toLocaleDateString("pt-BR"); } catch { return d; }
}

// ── Cartão CNPJ visual ────────────────────────────────────────────────────────
function CnpjCard({ company, onDelete, onSetPrimary }: {
  company: any;
  onDelete?: () => void;
  onSetPrimary?: () => void;
}) {
  const [showSocios, setShowSocios]   = useState(false);
  const [showCnaeSec, setShowCnaeSec] = useState(false);
  const ativa = (company.situacao_cadastral || "").toLowerCase().includes("ativa");

  return (
    <div className={`bg-white rounded-2xl border shadow-card overflow-hidden ${company.is_primary ? "border-proc-300 ring-2 ring-proc-100" : "border-slate-100"}`}>
      {/* Header do cartão */}
      <div className={`px-5 py-4 ${company.is_primary ? "bg-proc-900" : "bg-slate-800"}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {company.is_primary && (
                <span className="text-[10px] bg-proc-400/30 text-proc-200 font-bold px-2 py-0.5 rounded-full uppercase tracking-widest">
                  Principal
                </span>
              )}
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide ${ativa ? "bg-emerald-400/20 text-emerald-300" : "bg-amber-400/20 text-amber-300"}`}>
                {company.situacao_cadastral || "—"}
              </span>
              {company.tipo && (
                <span className="text-[10px] bg-white/10 text-white/60 px-2 py-0.5 rounded-full">{company.tipo}</span>
              )}
            </div>
            <h2 className="text-base font-bold text-white leading-snug">{company.razao_social}</h2>
            {company.nome_fantasia && (
              <p className="text-sm text-white/50 mt-0.5">"{company.nome_fantasia}"</p>
            )}
            <p className="text-sm font-mono text-white/70 mt-1">{company.cnpj}</p>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            {!company.is_primary && onSetPrimary && (
              <button onClick={onSetPrimary}
                className="text-[10px] flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 text-white rounded-lg transition">
                <Star size={10} /> Tornar principal
              </button>
            )}
            {!company.is_primary && onDelete && (
              <button onClick={onDelete}
                className="text-[10px] flex items-center gap-1 px-2 py-1 bg-red-500/20 hover:bg-red-500/40 text-red-300 rounded-lg transition">
                <Trash2 size={10} /> Remover
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Corpo do cartão */}
      <div className="p-5 space-y-5">
        {/* Dados básicos */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {company.natureza_juridica && (
            <div className="col-span-2 md:col-span-1">
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Natureza Jurídica</div>
              <div className="text-sm text-slate-800 mt-0.5">{company.natureza_juridica}</div>
            </div>
          )}
          {company.porte && (
            <div>
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Porte</div>
              <div className="text-sm text-slate-800 mt-0.5">{company.porte}</div>
            </div>
          )}
          {company.data_abertura && (
            <div>
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Abertura</div>
              <div className="text-sm text-slate-800 mt-0.5">{fmtDate(company.data_abertura)}</div>
            </div>
          )}
          {company.capital_social != null && (
            <div>
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Capital Social</div>
              <div className="text-sm font-semibold text-slate-800 mt-0.5">{fmt(company.capital_social)}</div>
            </div>
          )}
          {company.regime_tributario && (
            <div>
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Regime</div>
              <div className="text-sm text-slate-800 mt-0.5">{company.regime_tributario}</div>
            </div>
          )}
          {(company.opcao_simples != null || company.opcao_mei != null) && (
            <div>
              <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Regime especial</div>
              <div className="text-sm text-slate-800 mt-0.5">
                {company.opcao_simples ? "Simples Nacional" : company.opcao_mei ? "MEI" : "Não optante"}
              </div>
            </div>
          )}
        </div>

        {/* CNAE principal */}
        {company.cnae_principal && (
          <div className="bg-proc-50 border border-proc-100 rounded-xl p-3">
            <div className="text-[10px] font-semibold text-proc-600 uppercase tracking-wide mb-1">Atividade Principal (CNAE)</div>
            <div className="text-sm text-proc-900 font-medium">{company.cnae_principal}</div>
          </div>
        )}

        {/* CNAEs secundários */}
        {company.cnaes_secundarios?.length > 0 && (
          <div>
            <button onClick={() => setShowCnaeSec(v => !v)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 font-medium transition">
              {showCnaeSec ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              {company.cnaes_secundarios.length} Atividade(s) secundária(s)
            </button>
            {showCnaeSec && (
              <div className="mt-2 space-y-1">
                {company.cnaes_secundarios.map((c: any) => (
                  <div key={c.codigo} className="text-xs text-slate-600 py-1 border-b border-slate-50 last:border-0">
                    <span className="font-mono text-slate-400 mr-2">{c.codigo}</span>{c.descricao}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Endereço */}
        {company.logradouro && (
          <div className="flex items-start gap-2.5">
            <MapPin size={14} className="text-slate-400 mt-0.5 shrink-0" />
            <div className="text-sm text-slate-700 leading-relaxed">
              {[company.tipo_logradouro, company.logradouro].filter(Boolean).join(" ")}
              {company.numero ? `, ${company.numero}` : ""}
              {company.complemento ? ` — ${company.complemento}` : ""}
              <br />
              {company.bairro ? `${company.bairro} — ` : ""}
              {company.municipio}/{company.uf}
              {company.cep ? ` · CEP ${company.cep}` : ""}
            </div>
          </div>
        )}

        {/* Contato */}
        {(company.telefone || company.email) && (
          <div className="flex flex-wrap gap-4">
            {company.telefone && (
              <div className="flex items-center gap-1.5 text-sm text-slate-600">
                <Phone size={13} className="text-slate-400" /> {company.telefone}
              </div>
            )}
            {company.email && (
              <div className="flex items-center gap-1.5 text-sm text-slate-600">
                <Mail size={13} className="text-slate-400" />
                <a href={`mailto:${company.email}`} className="hover:text-proc-600">{company.email}</a>
              </div>
            )}
          </div>
        )}

        {/* Quadro Societário */}
        {company.socios?.length > 0 && (
          <div>
            <button onClick={() => setShowSocios(v => !v)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 font-medium transition">
              {showSocios ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
              <Users size={13} />
              {company.socios.length} Sócio(s) / Quadro Societário
            </button>
            {showSocios && (
              <div className="mt-2 divide-y divide-slate-50">
                {company.socios.map((s: any, i: number) => (
                  <div key={i} className="py-2.5">
                    <div className="text-sm font-medium text-slate-800">{s.nome}</div>
                    <div className="flex flex-wrap gap-x-4 text-xs text-slate-500 mt-0.5">
                      {s.qualificacao && <span>{s.qualificacao}</span>}
                      {s.faixa_etaria && <span>{s.faixa_etaria}</span>}
                      {s.data_entrada && <span>Entrada: {fmtDate(s.data_entrada)}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Data situação cadastral */}
        {company.data_situacao_cadastral && (
          <p className="text-[11px] text-slate-400">
            Situação em {fmtDate(company.data_situacao_cadastral)} · Fonte: Receita Federal / BrasilAPI
          </p>
        )}
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────
export default function CompanyPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";

  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [importing, setImporting] = useState(false);
  const [tenantInfo, setTenantInfo] = useState<any>(null);

  // Modal adicionar CNPJ
  const [modal, setModal]         = useState(false);
  const [cnpjInput, setCnpjInput] = useState("");
  const [cnpjData, setCnpjData]   = useState<any>(null);
  const [cnpjLoading, setCnpjLoading] = useState(false);
  const [cnpjError, setCnpjError] = useState("");
  const [adding, setAdding]       = useState(false);
  const [addError, setAddError]   = useState("");

  async function load() {
    setLoading(true);
    try {
      const [resC, resT] = await Promise.all([
        fetch(`${API}/api/companies`,       { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/api/auth/me/tenant`,  { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      const data = await resC.json();
      const ten  = await resT.json();
      setCompanies(Array.isArray(data) ? data : []);
      setTenantInfo(ten);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function importFromTenant() {
    setImporting(true);
    try {
      const res = await fetch(`${API}/api/companies/import-from-tenant`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const d = await res.json();
        alert(d.detail ?? "Erro ao importar.");
      } else {
        load();
      }
    } catch { alert("Erro de conexão."); }
    setImporting(false);
  }

  async function lookupCnpj() {
    const digits = cnpjInput.replace(/\D/g, "");
    if (digits.length !== 14) { setCnpjError("CNPJ deve ter 14 dígitos."); return; }
    setCnpjLoading(true); setCnpjError(""); setCnpjData(null);
    try {
      const res = await fetch(`${API}/api/cnpj/${digits}`);
      if (!res.ok) { const d = await res.json(); setCnpjError(d.detail ?? "CNPJ não encontrado."); }
      else setCnpjData(await res.json());
    } catch { setCnpjError("Erro de conexão."); }
    setCnpjLoading(false);
  }

  async function addCompany() {
    const digits = cnpjInput.replace(/\D/g, "");
    setAdding(true); setAddError("");
    try {
      const res = await fetch(`${API}/api/companies`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ cnpj_digits: digits }),
      });
      const data = await res.json();
      if (!res.ok) { setAddError(data.detail ?? "Erro ao adicionar."); setAdding(false); return; }
      setModal(false); setCnpjInput(""); setCnpjData(null);
      load();
    } catch { setAddError("Erro de conexão."); }
    setAdding(false);
  }

  async function removeCompany(id: number) {
    if (!confirm("Remover este CNPJ da sua conta?")) return;
    await fetch(`${API}/api/companies/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    load();
  }

  async function setPrimary(id: number) {
    await fetch(`${API}/api/companies/${id}/set-primary`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
    });
    load();
  }

  return (
    <div className="p-8 overflow-auto h-full">
      <div className="max-w-3xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Minha Empresa</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {companies.length > 0
                ? `${companies.length} CNPJ${companies.length > 1 ? "s" : ""} cadastrado${companies.length > 1 ? "s" : ""}`
                : "Nenhum CNPJ cadastrado"}
            </p>
          </div>
          <button onClick={() => { setModal(true); setCnpjInput(""); setCnpjData(null); setAddError(""); }}
            className="flex items-center gap-2 px-4 py-2 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition">
            <Plus size={15} /> Adicionar CNPJ
          </button>
        </div>

        {/* Lista de empresas */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
          </div>
        ) : companies.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-100 shadow-card p-12 text-center">
            <Building2 size={40} className="mx-auto mb-3 text-slate-300" />
            <p className="text-slate-600 font-medium mb-1">Nenhum CNPJ cadastrado</p>
            <p className="text-slate-400 text-sm mb-5">Adicione o CNPJ da sua empresa para visualizar os dados completos do Cartão CNPJ.</p>

            {tenantInfo?.document_type === "cnpj" && tenantInfo?.document && (
              <div className="max-w-md mx-auto mb-5 p-4 bg-proc-50 border border-proc-200 rounded-xl text-left">
                <p className="text-sm font-semibold text-proc-900 mb-1">
                  Importar CNPJ do cadastro?
                </p>
                <p className="text-xs text-proc-700 mb-3">
                  Detectamos o CNPJ <strong className="font-mono">{tenantInfo.document}</strong> no seu cadastro.
                  Clique para importar os dados completos da Receita Federal.
                </p>
                <button onClick={importFromTenant} disabled={importing}
                  className="w-full px-4 py-2 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition disabled:opacity-60 flex items-center justify-center gap-2">
                  {importing
                    ? <><Loader2 size={14} className="animate-spin" /> Importando…</>
                    : <><CheckCircle size={14} /> Importar do cadastro</>}
                </button>
              </div>
            )}

            <button onClick={() => setModal(true)}
              className="px-5 py-2.5 bg-slate-700 text-white rounded-xl text-sm font-medium hover:bg-slate-800 transition">
              Adicionar outro CNPJ
            </button>
          </div>
        ) : (
          <div className="space-y-5">
            {companies.map(c => (
              <CnpjCard
                key={c.id}
                company={c}
                onDelete={() => removeCompany(c.id)}
                onSetPrimary={() => setPrimary(c.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Modal adicionar CNPJ */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
              <h2 className="font-semibold text-slate-900">Adicionar CNPJ</h2>
              <button onClick={() => setModal(false)} className="text-slate-400 hover:text-slate-600">
                <X size={20} />
              </button>
            </div>

            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">CNPJ</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={cnpjInput}
                    onChange={e => { setCnpjInput(fmtCnpj(e.target.value)); setCnpjData(null); setCnpjError(""); }}
                    placeholder="00.000.000/0000-00"
                    maxLength={18}
                    className="flex-1 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400"
                    onKeyDown={e => e.key === "Enter" && lookupCnpj()}
                  />
                  <button onClick={lookupCnpj} disabled={cnpjLoading || cnpjInput.replace(/\D/g, "").length !== 14}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium disabled:opacity-50 transition">
                    {cnpjLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                    Consultar
                  </button>
                </div>
                {cnpjError && <p className="text-red-600 text-xs mt-1.5 flex items-center gap-1"><AlertCircle size={12} />{cnpjError}</p>}
              </div>

              {/* Preview do cartão */}
              {cnpjData && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                  <div className="flex items-start gap-2">
                    <CheckCircle size={16} className="text-proc-500 mt-0.5 shrink-0" />
                    <div>
                      <div className="font-semibold text-slate-900 text-sm">{cnpjData.razao_social}</div>
                      {cnpjData.nome_fantasia && <div className="text-xs text-slate-500">"{cnpjData.nome_fantasia}"</div>}
                      <div className="font-mono text-xs text-slate-400 mt-0.5">{cnpjData.cnpj}</div>
                    </div>
                    <span className={`ml-auto shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full ${(cnpjData.situacao_cadastral || "").toLowerCase().includes("ativa") ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                      {cnpjData.situacao_cadastral}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600">
                    {cnpjData.cnae_principal && <div className="col-span-2"><span className="text-slate-400">CNAE:</span> {cnpjData.cnae_principal}</div>}
                    {cnpjData.porte && <div><span className="text-slate-400">Porte:</span> {cnpjData.porte}</div>}
                    {cnpjData.natureza_juridica && <div><span className="text-slate-400">Natureza:</span> {cnpjData.natureza_juridica}</div>}
                    {cnpjData.municipio && <div><span className="text-slate-400">Município:</span> {cnpjData.municipio}/{cnpjData.uf}</div>}
                    {cnpjData.socios?.length > 0 && <div className="col-span-2"><span className="text-slate-400">Sócios:</span> {cnpjData.socios.map((s: any) => s.nome).join(", ")}</div>}
                  </div>
                  {addError && <p className="text-red-600 text-xs flex items-center gap-1"><AlertCircle size={12} />{addError}</p>}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-100">
              <button onClick={() => setModal(false)}
                className="px-4 py-2 border border-slate-200 text-slate-600 rounded-xl text-sm hover:bg-slate-50 transition">
                Cancelar
              </button>
              <button onClick={addCompany} disabled={adding || !cnpjData}
                className="px-5 py-2 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition disabled:opacity-60">
                {adding ? "Adicionando…" : "Adicionar empresa"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
