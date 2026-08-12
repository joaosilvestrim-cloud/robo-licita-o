"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, FileSearch, Search, Loader2, CheckCircle, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
type Mode = "login" | "register";

function fmtCnpj(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 14);
  return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}

const inp = "w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400 bg-white";

export default function LoginPage() {
  const router = useRouter();

  // ── Login state ──
  const [email, setEmail]     = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]   = useState(false);

  // ── Register state ──
  const [cnpjInput, setCnpjInput] = useState("");
  const [cnpjLoading, setCnpjLoading] = useState(false);
  const [cnpjData, setCnpjData] = useState<any>(null);
  const [cnpjError, setCnpjError] = useState("");
  const [showAddress, setShowAddress] = useState(false);

  const [regName, setRegName]     = useState("");
  const [regEmail, setRegEmail]   = useState("");
  const [regPw, setRegPw]         = useState("");
  const [showRegPw, setShowRegPw] = useState(false);

  const [mode, setMode] = useState<Mode>("login");
  const [error, setError]   = useState("");
  const [loading, setLoading] = useState(false);

  // ── CNPJ lookup ──
  async function lookupCnpj() {
    const digits = cnpjInput.replace(/\D/g, "");
    if (digits.length !== 14) { setCnpjError("CNPJ deve ter 14 dígitos."); return; }
    setCnpjLoading(true); setCnpjError(""); setCnpjData(null);
    try {
      const res = await fetch(`${API}/api/cnpj/${digits}`);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setCnpjError(d.detail ?? "CNPJ não encontrado na Receita Federal.");
      } else {
        const d = await res.json();
        setCnpjData(d);
        setRegEmail(d.email || regEmail);
      }
    } catch {
      setCnpjError("Erro de conexão. Tente novamente.");
    }
    setCnpjLoading(false);
  }

  // ── Login ──
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password }).toString(),
      });
      if (!res.ok) { setError("Credenciais inválidas."); return; }
      const d = await res.json();
      localStorage.setItem("proc_token",       d.access_token);
      localStorage.setItem("proc_user_id",     String(d.user_id));
      localStorage.setItem("proc_user_name",   d.user_name);
      localStorage.setItem("proc_tenant_id",   String(d.tenant_id));
      localStorage.setItem("proc_tenant_name", d.tenant_name);
      router.push("/dashboard");
    } catch { setError("Erro de conexão."); }
    finally { setLoading(false); }
  }

  // ── Register ──
  async function register(e: React.FormEvent) {
    e.preventDefault();
    if (!cnpjData) { setError("Consulte o CNPJ antes de continuar."); return; }
    setLoading(true); setError("");
    try {
      const digits = cnpjInput.replace(/\D/g, "");
      const body = {
        tenant_name: cnpjData.razao_social || regName,
        document: digits,
        document_type: "cnpj",
        name: regName,
        email: regEmail,
        password: regPw,
        razao_social: cnpjData.razao_social,
        nome_fantasia: cnpjData.nome_fantasia,
        cnae_code: cnpjData.cnae_code,
        cnae_description: cnpjData.cnae_description,
        natureza_juridica: cnpjData.natureza_juridica,
        situacao_cadastral: cnpjData.situacao_cadastral,
        capital_social: cnpjData.capital_social,
        data_abertura: cnpjData.data_abertura,
        porte: cnpjData.porte,
        logradouro: cnpjData.logradouro,
        numero: cnpjData.numero,
        complemento: cnpjData.complemento,
        bairro: cnpjData.bairro,
        municipio: cnpjData.municipio,
        uf_address: cnpjData.uf,
        cep: cnpjData.cep,
      };
      const res = await fetch(`${API}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail ?? "Erro ao criar conta."); return;
      }
      // auto-login
      const login = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: regEmail, password: regPw }).toString(),
      });
      const d = await login.json();
      localStorage.setItem("proc_token",       d.access_token);
      localStorage.setItem("proc_user_id",     String(d.user_id));
      localStorage.setItem("proc_user_name",   d.user_name);
      localStorage.setItem("proc_tenant_id",   String(d.tenant_id));
      localStorage.setItem("proc_tenant_name", d.tenant_name);
      router.push("/dashboard");
    } catch { setError("Erro de conexão."); }
    finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen flex bg-slate-100">
      {/* Left panel */}
      <div className="hidden lg:flex flex-col justify-between w-96 bg-proc-900 p-10 text-white">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-proc-500 flex items-center justify-center shadow">
            <FileSearch size={18} />
          </div>
          <div>
            <div className="font-bold text-lg leading-tight">Licita</div>
            <div className="text-xs text-white/40 leading-tight">by Acrasystem</div>
          </div>
        </div>
        <div>
          <h2 className="text-3xl font-bold leading-tight mb-4">
            Monitore licitações<br />em todo o Brasil
          </h2>
          <p className="text-white/60 text-sm leading-relaxed mb-6">
            Acompanhe licitações federais, estaduais e municipais com alertas personalizados, mapa de calor e agente IA que encontra oportunidades para sua empresa.
          </p>
          <div className="space-y-2.5 text-sm text-white/70">
            {["PNCP integrado — dados em tempo real", "Mapa de calor por estado e cidade", "Alertas por perfil + score de relevância", "Agente Hermes Licita para auxiliar sua busca"].map(f => (
              <div key={f} className="flex items-center gap-2.5">
                <CheckCircle size={14} className="text-proc-300 shrink-0" />
                {f}
              </div>
            ))}
          </div>
        </div>
        <div className="text-xs text-white/20">© 2024 Acrasystem · licita.nanuck.com.br</div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-start justify-center p-8 overflow-y-auto">
        <div className="w-full max-w-md py-8">
          <div className="mb-7">
            <h1 className="text-2xl font-bold text-slate-900">
              {mode === "login" ? "Entrar na plataforma" : "Criar sua conta"}
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              {mode === "login" ? "Acesse suas licitações monitoradas" : "Cadastro gratuito — consulte o CNPJ para começar"}
            </p>
          </div>

          {/* Toggle */}
          <div className="flex bg-slate-200 rounded-xl p-1 mb-6">
            {(["login", "register"] as Mode[]).map(m => (
              <button key={m} onClick={() => { setMode(m); setError(""); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition ${mode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
                {m === "login" ? "Entrar" : "Cadastrar empresa"}
              </button>
            ))}
          </div>

          {/* ── LOGIN FORM ── */}
          {mode === "login" && (
            <form onSubmit={login} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">Email</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="seu@email.com" className={inp} required />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">Senha</label>
                <div className="relative">
                  <input type={showPw ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" className={`${inp} pr-10`} required />
                  <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <div className="text-right mt-1">
                  <a href="/forgot-password" className="text-xs text-proc-600 hover:text-proc-800 font-medium">Esqueci minha senha</a>
                </div>
              </div>
              {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex items-center gap-2"><AlertCircle size={15} />{error}</div>}
              <button type="submit" disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl font-semibold text-sm transition disabled:opacity-60">
                {loading ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Aguarde…</> : "Entrar"}
              </button>
            </form>
          )}

          {/* ── REGISTER FORM ── */}
          {mode === "register" && (
            <form onSubmit={register} className="space-y-5">

              {/* CNPJ lookup */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">CNPJ da empresa</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={cnpjInput}
                    onChange={e => { setCnpjInput(fmtCnpj(e.target.value)); setCnpjData(null); setCnpjError(""); }}
                    placeholder="00.000.000/0000-00"
                    maxLength={18}
                    className={`${inp} flex-1`}
                    onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); lookupCnpj(); } }}
                  />
                  <button type="button" onClick={lookupCnpj} disabled={cnpjLoading || cnpjInput.replace(/\D/g, "").length !== 14}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl text-sm font-medium transition disabled:opacity-50 shrink-0">
                    {cnpjLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                    {cnpjLoading ? "…" : "Consultar"}
                  </button>
                </div>
                {cnpjError && <p className="text-red-600 text-xs mt-1.5 flex items-center gap-1"><AlertCircle size={12} />{cnpjError}</p>}
              </div>

              {/* Dados da Receita */}
              {cnpjData && (
                <div className="bg-proc-50 border border-proc-200 rounded-2xl p-4 space-y-3">
                  <div className="flex items-start gap-2">
                    <CheckCircle size={16} className="text-proc-500 mt-0.5 shrink-0" />
                    <div className="flex-1">
                      <div className="font-semibold text-proc-900 text-sm">{cnpjData.razao_social}</div>
                      {cnpjData.nome_fantasia && <div className="text-xs text-proc-700">"{cnpjData.nome_fantasia}"</div>}
                    </div>
                    {cnpjData.situacao_cadastral && (
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cnpjData.situacao_cadastral.toLowerCase().includes("ativa") ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                        {cnpjData.situacao_cadastral}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600">
                    {cnpjData.cnae_principal && (
                      <div className="col-span-2"><span className="text-slate-400">CNAE:</span> {cnpjData.cnae_principal}</div>
                    )}
                    {cnpjData.natureza_juridica && (
                      <div className="col-span-2"><span className="text-slate-400">Natureza:</span> {cnpjData.natureza_juridica}</div>
                    )}
                    {cnpjData.porte && <div><span className="text-slate-400">Porte:</span> {cnpjData.porte}</div>}
                    {cnpjData.data_abertura && <div><span className="text-slate-400">Abertura:</span> {cnpjData.data_abertura}</div>}
                    {cnpjData.capital_social && <div><span className="text-slate-400">Capital:</span> {new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL",notation:"compact"}).format(cnpjData.capital_social)}</div>}
                  </div>

                  {/* Endereço recolhível */}
                  {cnpjData.logradouro && (
                    <button type="button" onClick={() => setShowAddress(v => !v)}
                      className="flex items-center gap-1 text-xs text-proc-600 hover:text-proc-800 font-medium">
                      {showAddress ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      {showAddress ? "Ocultar endereço" : "Ver endereço"}
                    </button>
                  )}
                  {showAddress && cnpjData.logradouro && (
                    <div className="text-xs text-slate-600 bg-white rounded-lg p-2.5 border border-slate-100">
                      {cnpjData.logradouro}{cnpjData.numero ? `, ${cnpjData.numero}` : ""}
                      {cnpjData.complemento ? ` — ${cnpjData.complemento}` : ""}<br />
                      {cnpjData.bairro ? `${cnpjData.bairro} — ` : ""}{cnpjData.municipio}/{cnpjData.uf}
                      {cnpjData.cep ? ` · CEP ${cnpjData.cep}` : ""}
                    </div>
                  )}
                </div>
              )}

              {/* Dados do usuário */}
              <div className="border-t border-slate-200 pt-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">Seu nome completo</label>
                  <input type="text" value={regName} onChange={e => setRegName(e.target.value)} placeholder="Nome do responsável" className={inp} required />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">E-mail de acesso</label>
                  <input type="email" value={regEmail} onChange={e => setRegEmail(e.target.value)} placeholder="seu@empresa.com.br" className={inp} required />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">Senha</label>
                  <div className="relative">
                    <input type={showRegPw ? "text" : "password"} value={regPw} onChange={e => setRegPw(e.target.value)} placeholder="Mínimo 6 caracteres" className={`${inp} pr-10`} required minLength={6} />
                    <button type="button" onClick={() => setShowRegPw(!showRegPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      {showRegPw ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex items-center gap-2"><AlertCircle size={15} />{error}</div>}

              <button type="submit" disabled={loading || !cnpjData || !regName || !regEmail || !regPw}
                className="w-full flex justify-center items-center gap-2 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl font-semibold text-sm transition disabled:opacity-50">
                {loading ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Criando conta…</> : "Criar conta gratuita"}
              </button>

              {!cnpjData && (
                <p className="text-xs text-slate-400 text-center">Consulte o CNPJ acima para habilitar o cadastro</p>
              )}
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
