"use client";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, CheckCircle, AlertCircle, Lock } from "lucide-react";
import { Logo } from "../components/Logo";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

function ResetForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const token        = searchParams.get("token") ?? "";

  const [password, setPassword]   = useState("");
  const [confirm,  setConfirm]    = useState("");
  const [showPw,   setShowPw]     = useState(false);
  const [loading,  setLoading]    = useState(false);
  const [done,     setDone]       = useState(false);
  const [error,    setError]      = useState("");

  useEffect(() => {
    if (!token) setError("Link inválido. Solicite um novo link de redefinição.");
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError("As senhas não coincidem."); return; }
    if (password.length < 6)  { setError("A senha deve ter pelo menos 6 caracteres."); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Erro ao redefinir senha."); return; }
      setDone(true);
      setTimeout(() => router.push("/login"), 3000);
    } catch { setError("Erro de conexão."); }
    finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8">
          <Logo size={36} />
          <div>
            <div className="font-bold text-slate-900 leading-tight">Drive Data</div>
            <div className="text-[11px] text-slate-400">Licitações</div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-card border border-slate-100 p-8">
          {done ? (
            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto mb-4">
                <CheckCircle size={28} className="text-emerald-500" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 mb-2">Senha redefinida!</h1>
              <p className="text-slate-500 text-sm">Redirecionando para o login em instantes…</p>
              <Link href="/login" className="mt-4 inline-block text-sm text-proc-600 hover:underline font-medium">
                Ir para o login agora
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <div className="w-10 h-10 rounded-xl bg-proc-50 flex items-center justify-center mb-3">
                  <Lock size={18} className="text-proc-500" />
                </div>
                <h1 className="text-xl font-bold text-slate-900">Nova senha</h1>
                <p className="text-slate-500 text-sm mt-1">Escolha uma senha forte para sua conta.</p>
              </div>

              {error && !token ? (
                <div className="text-center space-y-3">
                  <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
                    {error}
                  </div>
                  <Link href="/forgot-password" className="text-sm text-proc-600 hover:underline font-medium">
                    Solicitar novo link
                  </Link>
                </div>
              ) : (
                <form onSubmit={submit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">Nova senha</label>
                    <div className="relative">
                      <input
                        type={showPw ? "text" : "password"}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="Mínimo 6 caracteres"
                        className="w-full border border-slate-200 rounded-xl px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400"
                        required minLength={6}
                      />
                      <button type="button" onClick={() => setShowPw(!showPw)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                        {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wide">Confirmar senha</label>
                    <input
                      type={showPw ? "text" : "password"}
                      value={confirm}
                      onChange={e => setConfirm(e.target.value)}
                      placeholder="Repita a nova senha"
                      className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-proc-400"
                      required
                    />
                    {confirm && password !== confirm && (
                      <p className="text-red-500 text-xs mt-1">As senhas não coincidem.</p>
                    )}
                  </div>

                  {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex items-center gap-2">
                      <AlertCircle size={15} /> {error}
                    </div>
                  )}

                  <button type="submit"
                    disabled={loading || !password || password !== confirm}
                    className="w-full flex justify-center items-center gap-2 py-2.5 bg-proc-500 hover:bg-proc-600 text-white rounded-xl font-semibold text-sm transition disabled:opacity-60">
                    {loading
                      ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />Salvando…</>
                      : "Salvar nova senha"}
                  </button>
                </form>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><span className="w-8 h-8 border-4 border-proc-200 border-t-proc-500 rounded-full animate-spin" /></div>}>
      <ResetForm />
    </Suspense>
  );
}
