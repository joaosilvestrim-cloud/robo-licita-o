"use client";
import { useEffect, useState } from "react";
import { Plus, Edit2, Trash2, PlayCircle, Target, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

const EMPTY_FORM = {
  name: "",
  preferred_spheres: "",
  preferred_states: "",
  preferred_cities: "",
  preferred_branches: "",
  preferred_categories: "",
  min_estimated_value: "",
  max_estimated_value: "",
  exclude_modalities: "",
  require_sme_reservation: false,
  only_with_deadline: false,
  alert_days_before: 7,
  keywords: "",
  exclude_keywords: "",
};

// Field fora do componente pai para evitar remount a cada keystroke
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}

const inp = "w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400 bg-white";

export default function ProfilesPage() {
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const [modal, setModal]       = useState(false);
  const [editing, setEditing]   = useState<any>(null);
  const [form, setForm]         = useState({ ...EMPTY_FORM });
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting]   = useState(false);
  const [saving, setSaving]     = useState(false);

  async function load() {
    const res = await fetch(`${API}/api/profiles`, { headers: { Authorization: `Bearer ${token}` } });
    setProfiles(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function set(field: string, value: any) {
    setForm(f => ({ ...f, [field]: value }));
  }

  function openCreate() {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setTestResult(null);
    setModal(true);
  }

  function openEdit(p: any) {
    setEditing(p);
    setForm({
      name: p.name ?? "",
      preferred_spheres: p.preferred_spheres ?? "",
      preferred_states: p.preferred_states ?? "",
      preferred_cities: p.preferred_cities ?? "",
      preferred_branches: p.preferred_branches ?? "",
      preferred_categories: p.preferred_categories ?? "",
      min_estimated_value: p.min_estimated_value ?? "",
      max_estimated_value: p.max_estimated_value ?? "",
      exclude_modalities: p.exclude_modalities ?? "",
      require_sme_reservation: p.require_sme_reservation ?? false,
      only_with_deadline: p.only_with_deadline ?? false,
      alert_days_before: p.alert_days_before ?? 7,
      keywords: p.keywords ?? "",
      exclude_keywords: p.exclude_keywords ?? "",
    });
    setTestResult(null);
    setModal(true);
  }

  async function save() {
    setSaving(true);
    const body = {
      ...form,
      min_estimated_value: form.min_estimated_value ? parseFloat(String(form.min_estimated_value)) : null,
      max_estimated_value: form.max_estimated_value ? parseFloat(String(form.max_estimated_value)) : null,
      alert_days_before: Number(form.alert_days_before),
    };
    const url    = editing ? `${API}/api/profiles/${editing.id}` : `${API}/api/profiles`;
    const method = editing ? "PATCH" : "POST";
    await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setModal(false);
    load();
    setSaving(false);
  }

  async function deleteProfile(id: number) {
    if (!confirm("Excluir este perfil?")) return;
    await fetch(`${API}/api/profiles/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    load();
  }

  async function testProfile() {
    if (!editing) return;
    setTesting(true);
    const res = await fetch(`${API}/api/profiles/${editing.id}/test?limit=5`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    setTestResult(await res.json());
    setTesting(false);
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Perfis de Alerta</h1>
          <p className="text-slate-500 text-sm mt-0.5">Configure quais licitações você quer monitorar</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition">
          <Plus size={16} /> Novo perfil
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" />
        </div>
      ) : profiles.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-16 text-center">
          <Target size={40} className="mx-auto mb-3 text-slate-300" />
          <p className="text-slate-600 font-medium mb-1">Nenhum perfil configurado</p>
          <p className="text-slate-400 text-sm mb-5">Crie um perfil para receber alertas de licitações relevantes.</p>
          <button onClick={openCreate}
            className="px-5 py-2.5 bg-proc-500 text-white rounded-xl text-sm font-medium hover:bg-proc-600 transition">
            Criar primeiro perfil
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {profiles.map((p: any) => (
            <div key={p.id} className="bg-white rounded-2xl shadow-card border border-slate-100 p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-slate-900">{p.name}</h3>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
                    {p.preferred_spheres && <span>Esferas: <b>{p.preferred_spheres}</b></span>}
                    {p.preferred_states  && <span>Estados: <b>{p.preferred_states.toUpperCase()}</b></span>}
                    {p.preferred_branches && <span>Ramos: <b>{p.preferred_branches}</b></span>}
                    {p.keywords          && <span>Keywords: <b>{p.keywords}</b></span>}
                    {p.min_estimated_value && <span>Mín: R${Number(p.min_estimated_value).toLocaleString("pt-BR")}</span>}
                    {p.max_estimated_value && <span>Máx: R${Number(p.max_estimated_value).toLocaleString("pt-BR")}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button onClick={() => openEdit(p)}
                    className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition">
                    <Edit2 size={15} />
                  </button>
                  <button onClick={() => deleteProfile(p.id)}
                    className="p-2 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition">
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
              <h2 className="font-semibold text-slate-900">{editing ? "Editar perfil" : "Novo perfil"}</h2>
              <button onClick={() => setModal(false)} className="text-slate-400 hover:text-slate-600">
                <X size={20} />
              </button>
            </div>

            <div className="px-6 py-5 space-y-4">
              <Field label="Nome do perfil">
                <input
                  type="text"
                  value={form.name}
                  onChange={e => set("name", e.target.value)}
                  placeholder="Ex: TI no Estado de SP"
                  className={inp}
                />
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Esferas" hint="federal, estadual, municipal — ou * para todas">
                  <input
                    type="text"
                    value={form.preferred_spheres}
                    onChange={e => set("preferred_spheres", e.target.value)}
                    placeholder="* (todas) ou federal,estadual"
                    className={inp}
                  />
                </Field>
                <Field label="Estados (UF)" hint="Separados por vírgula — ou * para todos">
                  <input
                    type="text"
                    value={form.preferred_states}
                    onChange={e => set("preferred_states", e.target.value)}
                    placeholder="* (todos) ou SP,RJ,MG"
                    className={inp}
                  />
                </Field>
              </div>

              <Field label="Cidades" hint="Separadas por vírgula — ou * para todas">
                <input
                  type="text"
                  value={form.preferred_cities}
                  onChange={e => set("preferred_cities", e.target.value)}
                  placeholder="* (todas) ou São Paulo,Campinas"
                  className={inp}
                />
              </Field>

              <Field label="Ramos / Segmentos" hint="Ex: TI,Construção,Saúde — ou * para todos">
                <input
                  type="text"
                  value={form.preferred_branches}
                  onChange={e => set("preferred_branches", e.target.value)}
                  placeholder="* (todos) ou TI,Construção"
                  className={inp}
                />
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Valor mínimo estimado (R$)">
                  <input
                    type="number"
                    value={form.min_estimated_value}
                    onChange={e => set("min_estimated_value", e.target.value)}
                    placeholder="0"
                    min={0}
                    className={inp}
                  />
                </Field>
                <Field label="Valor máximo estimado (R$)">
                  <input
                    type="number"
                    value={form.max_estimated_value}
                    onChange={e => set("max_estimated_value", e.target.value)}
                    placeholder="Sem limite"
                    min={0}
                    className={inp}
                  />
                </Field>
              </div>

              <Field label="Palavras-chave" hint="A licitação deve conter pelo menos uma — separadas por vírgula — ou * para qualquer">
                <input
                  type="text"
                  value={form.keywords}
                  onChange={e => set("keywords", e.target.value)}
                  placeholder="sistema,software,dados,tecnologia"
                  className={inp}
                />
              </Field>

              <Field label="Excluir se contiver estas palavras">
                <input
                  type="text"
                  value={form.exclude_keywords}
                  onChange={e => set("exclude_keywords", e.target.value)}
                  placeholder="limpeza,vigilância,alimentação"
                  className={inp}
                />
              </Field>

              <Field label="Excluir modalidades">
                <input
                  type="text"
                  value={form.exclude_modalities}
                  onChange={e => set("exclude_modalities", e.target.value)}
                  placeholder="dispensa,inexigibilidade"
                  className={inp}
                />
              </Field>

              <Field label="Alertar X dias antes do encerramento">
                <input
                  type="number"
                  value={form.alert_days_before}
                  onChange={e => set("alert_days_before", e.target.value)}
                  min={1}
                  max={60}
                  className={inp}
                />
              </Field>

              {/* Flags */}
              <div className="space-y-2.5 bg-slate-50 border border-slate-100 rounded-xl p-3">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.only_with_deadline}
                    onChange={e => set("only_with_deadline", e.target.checked)}
                    className="w-4 h-4 mt-0.5 text-proc-500 rounded accent-proc-500 shrink-0"
                  />
                  <div>
                    <span className="text-sm font-medium text-slate-700">Apenas licitações com prazo definido</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Exclui Dispensas e Inexigibilidades sem data de encerramento (contratação direta).
                    </p>
                  </div>
                </label>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.require_sme_reservation}
                    onChange={e => set("require_sme_reservation", e.target.checked)}
                    className="w-4 h-4 mt-0.5 text-proc-500 rounded accent-proc-500 shrink-0"
                  />
                  <div>
                    <span className="text-sm font-medium text-slate-700">Priorizar licitações com reserva ME/EPP</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Reduz o score de licitações abertas à ampla concorrência.
                    </p>
                  </div>
                </label>
              </div>

              {/* Test result */}
              {testResult && (
                <div className="bg-proc-50 border border-proc-200 rounded-xl p-4">
                  <p className="text-sm font-semibold text-proc-900 mb-2">
                    {testResult.total_matches} licitações correspondem a este perfil
                  </p>
                  {testResult.sample?.length === 0 && (
                    <p className="text-xs text-proc-700">Nenhuma licitação aberta no momento com estes critérios.</p>
                  )}
                  {testResult.sample?.map((m: any) => (
                    <div key={m.bid_id} className="mb-2 pb-2 border-b border-proc-100 last:border-0 last:mb-0">
                      <p className="text-xs font-medium text-slate-800 line-clamp-2">{m.title}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Score {Math.round(m.score * 100)}% · {m.reasons?.join(" · ")}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 sticky bottom-0 bg-white">
              {editing ? (
                <button onClick={testProfile} disabled={testing}
                  className="flex items-center gap-2 px-4 py-2 border border-proc-300 text-proc-700 rounded-xl text-sm font-medium hover:bg-proc-50 transition disabled:opacity-60">
                  <PlayCircle size={15} />
                  {testing ? "Testando…" : "Testar regras"}
                </button>
              ) : <div />}
              <div className="flex gap-2">
                <button onClick={() => setModal(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 rounded-xl text-sm hover:bg-slate-50 transition">
                  Cancelar
                </button>
                <button onClick={save} disabled={saving || !form.name}
                  className="px-5 py-2 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition disabled:opacity-60">
                  {saving ? "Salvando…" : "Salvar perfil"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
