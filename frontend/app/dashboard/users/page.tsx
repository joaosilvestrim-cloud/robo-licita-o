"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  UserPlus, KeyRound, ShieldCheck, ShieldOff, Loader2, X,
  Shield, Eye, User as UserIcon, Mail, Check, AlertCircle,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

type Usr = { id: number; name: string; email: string; role: string; active: boolean; created_at: string };

const ROLES: Record<string, { label: string; desc: string; icon: any; cls: string }> = {
  admin:  { label: "Admin",   desc: "Gerencia usuários e vê tudo",      icon: Shield,      cls: "bg-proc-50 text-proc-700 border-proc-200" },
  full:   { label: "Completo", desc: "Vê tudo da empresa",              icon: Eye,         cls: "bg-dgreen-400/10 text-dgreen-600 border-dgreen-400/30" },
  simple: { label: "Simples", desc: "Só os próprios perfis e interações", icon: UserIcon,  cls: "bg-slate-100 text-slate-600 border-slate-200" },
};

export default function UsersPage() {
  const router = useRouter();
  const token = typeof window !== "undefined" ? localStorage.getItem("proc_token") ?? "" : "";
  const myRole = typeof window !== "undefined" ? localStorage.getItem("proc_user_role") ?? "" : "";
  const myId = typeof window !== "undefined" ? Number(localStorage.getItem("proc_user_id") ?? 0) : 0;

  const [users, setUsers]     = useState<Usr[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState<{ ok: boolean; text: string } | null>(null);

  // form
  const [name, setName]     = useState("");
  const [email, setEmail]   = useState("");
  const [pw, setPw]         = useState("");
  const [role, setRole]     = useState("simple");

  // reset password inline
  const [resetId, setResetId] = useState<number | null>(null);
  const [resetPw, setResetPw] = useState("");

  const flash = (ok: boolean, text: string) => { setMsg({ ok, text }); setTimeout(() => setMsg(null), 3500); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/users`, { headers: { Authorization: `Bearer ${token}` } });
      const d = await res.json();
      if (Array.isArray(d)) setUsers(d);
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => {
    if (myRole && myRole !== "admin") return;   // não-admin: mostra bloqueio
    load();
  }, [load, myRole]);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/users`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password: pw, role }),
      });
      const d = await res.json().catch(() => ({}));
      if (res.ok) {
        flash(true, "Usuário criado.");
        setName(""); setEmail(""); setPw(""); setRole("simple"); setShowForm(false);
        load();
      } else {
        flash(false, d.detail ?? "Erro ao criar usuário.");
      }
    } catch { flash(false, "Erro de conexão."); }
    setSaving(false);
  }

  async function patchUser(id: number, body: any, okText: string) {
    try {
      const res = await fetch(`${API}/api/users/${id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await res.json().catch(() => ({}));
      if (res.ok) { flash(true, okText); load(); }
      else flash(false, d.detail ?? "Erro.");
    } catch { flash(false, "Erro de conexão."); }
  }

  async function doResetPassword(id: number) {
    if (resetPw.length < 6) { flash(false, "A senha precisa de 6+ caracteres."); return; }
    await patchUser(id, { password: resetPw }, "Senha redefinida.");
    setResetId(null); setResetPw("");
  }

  // Bloqueio para não-admins
  if (myRole && myRole !== "admin") {
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-3 text-slate-400 bg-slate-50">
        <ShieldOff size={40} className="opacity-30" />
        <p className="text-sm">Área restrita ao Admin da empresa.</p>
      </div>
    );
  }

  return (
    <div className="h-screen overflow-y-auto bg-slate-50">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-white border-b border-slate-100 px-8 py-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Usuários</h1>
          <p className="text-slate-400 text-xs mt-0.5">
            {users.length} {users.length === 1 ? "usuário" : "usuários"} na empresa · defina senha e perfil de acesso
          </p>
        </div>
        <button
          onClick={() => setShowForm(s => !s)}
          className="flex items-center gap-2 text-white px-4 py-2 rounded-xl text-sm font-semibold dd-gradient shadow"
        >
          <UserPlus size={16} /> Novo usuário
        </button>
      </div>

      {msg && (
        <div className={`mx-8 mt-4 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm ${msg.ok ? "bg-dgreen-400/10 text-dgreen-600" : "bg-red-50 text-red-600"}`}>
          {msg.ok ? <Check size={15} /> : <AlertCircle size={15} />} {msg.text}
        </div>
      )}

      <div className="max-w-4xl mx-auto px-8 py-6 space-y-5">
        {/* Formulário de criação */}
        {showForm && (
          <form onSubmit={createUser} className="bg-white rounded-2xl border border-slate-100 shadow-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-800 text-sm">Novo usuário</h2>
              <button type="button" onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <div className="grid md:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Nome</label>
                <input value={name} onChange={e => setName(e.target.value)} required
                  className="w-full mt-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400" />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">E-mail</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                  className="w-full mt-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400" />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Senha</label>
                <input type="text" value={pw} onChange={e => setPw(e.target.value)} required minLength={6}
                  placeholder="mín. 6 caracteres"
                  className="w-full mt-1 border border-slate-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-proc-400" />
              </div>
              <div>
                <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Perfil de acesso</label>
                <select value={role} onChange={e => setRole(e.target.value)}
                  className="w-full mt-1 border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-proc-400">
                  <option value="simple">Simples — só os próprios dados</option>
                  <option value="full">Completo — vê tudo da empresa</option>
                  <option value="admin">Admin — gerencia usuários</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 rounded-xl text-sm text-slate-600 hover:bg-slate-100">Cancelar</button>
              <button type="submit" disabled={saving} className="flex items-center gap-2 text-white px-4 py-2 rounded-xl text-sm font-semibold dd-gradient disabled:opacity-60">
                {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Criar
              </button>
            </div>
          </form>
        )}

        {/* Lista */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-card overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16"><Loader2 size={22} className="animate-spin text-proc-400" /></div>
          ) : users.length === 0 ? (
            <div className="text-center py-16 text-slate-400 text-sm">Nenhum usuário ainda.</div>
          ) : users.map(u => {
            const r = ROLES[u.role] ?? ROLES.simple;
            const RoleIcon = r.icon;
            return (
              <div key={u.id} className="border-b border-slate-50 last:border-0">
                <div className="flex items-center gap-4 px-6 py-4">
                  <div className="w-10 h-10 rounded-full bg-proc-500 text-white flex items-center justify-center font-bold text-sm shrink-0">
                    {u.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-800 text-sm truncate">{u.name}</span>
                      {u.id === myId && <span className="text-[10px] text-proc-500 font-semibold">(você)</span>}
                      {!u.active && <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-400 font-semibold uppercase">Inativo</span>}
                    </div>
                    <div className="text-xs text-slate-400 flex items-center gap-1 mt-0.5"><Mail size={11} /> {u.email}</div>
                  </div>

                  {/* Perfil (select) */}
                  <select
                    value={u.role}
                    disabled={u.id === myId}
                    onChange={e => patchUser(u.id, { role: e.target.value }, "Perfil atualizado.")}
                    className={`text-xs font-medium border rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-proc-400 ${r.cls} disabled:opacity-60`}
                    title={r.desc}
                  >
                    <option value="simple">Simples</option>
                    <option value="full">Completo</option>
                    <option value="admin">Admin</option>
                  </select>

                  {/* Ações */}
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => { setResetId(resetId === u.id ? null : u.id); setResetPw(""); }}
                      title="Redefinir senha"
                      className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-proc-600">
                      <KeyRound size={15} />
                    </button>
                    {u.id !== myId && (
                      u.active ? (
                        <button onClick={() => patchUser(u.id, { active: false }, "Usuário desativado.")}
                          title="Desativar" className="p-2 rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-500">
                          <ShieldOff size={15} />
                        </button>
                      ) : (
                        <button onClick={() => patchUser(u.id, { active: true }, "Usuário reativado.")}
                          title="Reativar" className="p-2 rounded-lg text-slate-400 hover:bg-dgreen-400/10 hover:text-dgreen-600">
                          <ShieldCheck size={15} />
                        </button>
                      )
                    )}
                  </div>
                </div>

                {/* Linha de redefinir senha */}
                {resetId === u.id && (
                  <div className="px-6 pb-4 -mt-1 flex items-center gap-2">
                    <KeyRound size={14} className="text-proc-400 shrink-0" />
                    <input
                      type="text" value={resetPw} onChange={e => setResetPw(e.target.value)}
                      placeholder="Nova senha (mín. 6)" autoFocus
                      className="flex-1 border border-slate-200 rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-proc-400"
                    />
                    <button onClick={() => doResetPassword(u.id)}
                      className="text-white px-3 py-1.5 rounded-lg text-xs font-semibold dd-gradient">Salvar senha</button>
                    <button onClick={() => { setResetId(null); setResetPw(""); }}
                      className="px-2 py-1.5 rounded-lg text-xs text-slate-500 hover:bg-slate-100">Cancelar</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-xs text-slate-400 px-1">
          <strong>Perfis:</strong> Admin gerencia usuários e vê tudo · Completo vê tudo da empresa · Simples vê só os próprios perfis e interações.
        </p>
      </div>
    </div>
  );
}
