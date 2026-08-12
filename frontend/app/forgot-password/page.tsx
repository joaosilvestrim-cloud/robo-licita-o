"use client";
import { useState } from "react";
import Link from "next/link";
import { FileSearch, Mail, ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function ForgotPasswordPage() {
  const [email, setEmail]   = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent]     = useState(false);
  const [error, setError]   = useState("");
  const [devLink, setDevLink] = useState(""); // só aparece se SMTP não configurado

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Erro. Tente novamente."); return; }
      if (data.reset_link) setDevLink(data.reset_link); // modo dev sem SMTP
      setSent(true);
    } catch { setError("Erro de conexão."); }
    finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-xl bg-proc-500 flex items-center justify-center shadow">
            <FileSearch size={18} className="text-white" />
          </div>
          <div>
            <div className="font-bold text-slate-900 leading-tight">Licita</div>
            <div className="text-[11px] text-slate-400">by Acrasystem</div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-8">
          {sent ? (
            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
                <CheckCircle size={28} className="text-emerald-500" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 mb-2">Verifique seu e-mail</h1>
              <p className="text-slate-500 text-sm leading-relaxed">
                Se <strong>{email}</strong> estiver cadastrado, você receberá um link para redefinir sua senha em instantes.
              </p>
              {devLink && (
                <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-left">
                  <p className="text-xs font-semibold text-amber-700 mb-1">⚠ SMTP não configurado — link de desenvolvimento:</p>
                  <Link href={devLink} className="text-xs text-proc-600 break-all hover:underline">{devLink}</Link>
                </div>
              )}
              <Link href="/login" className="mt-6 flex items-center justify-center gap-2 text-sm text-proc-600 hover:text-proc-800 font-medium transition">
                <ArrowLeft size={14} /> Voltar ao login
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h1 className="text-xl font-bold text-slate-900">Esqueceu a senha?</h1>
                <p className="text-slate-500 text-sm mt-1">Informe seu e-mail e enviaremos o link de redefinição.</p>
              </div>

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">E-mail cadastrado</label>
                  <div className="relative">
                    <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="seu@email.com"
                      className="w-full pl-9 pr-3 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-proc-400 bg-white"
                      required
                    />
                  </div>
                </div>

                {error && (
                  <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex items-center gap-2">
                    <AlertCircle size={15} /> {error}
                  </div>
                )}

                <button type="submit" disabled={loading}
                  className="w-full flex justify-center items-center gap-2 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl font-semibold text-sm transition disabled:opacity-60">
                  {loading
                    ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Enviando…</>
                    : "Enviar link de redefinição"}
                </button>
              </form>

              <Link href="/login"
                className="mt-5 flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition">
                <ArrowLeft size={14} /> Voltar ao login
              </Link>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
