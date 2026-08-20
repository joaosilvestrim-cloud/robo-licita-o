"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, FileSearch, Bell, BookmarkCheck,
  LogOut, ChevronRight, BarChart2, Target, Building2, Database, Users, Sparkles, FileClock, Sprout,
} from "lucide-react";
import ChatWidget from "../components/ChatWidget";
import { Logo } from "../components/Logo";

const navGroups = [
  { title: null, items: [
    { href: "/dashboard",          label: "Dashboard", icon: LayoutDashboard, exact: true },
    { href: "/dashboard/for-you",  label: "Pra você",  icon: Sparkles },
  ]},
  { title: "Oportunidades", items: [
    { href: "/dashboard/bids",      label: "Licitações", icon: FileSearch },
    { href: "/dashboard/contracts", label: "Recontratação", icon: FileClock },
    { href: "/dashboard/funding",   label: "Fomento",    icon: Sprout },
    { href: "/dashboard/alerts",    label: "Alertas",    icon: Bell },
  ]},
  { title: "Minha gestão", items: [
    { href: "/dashboard/profiles", label: "Meus Perfis",   icon: Target },
    { href: "/dashboard/tracking", label: "Acompanhando",  icon: BookmarkCheck },
    { href: "/dashboard/reports",  label: "Relatórios",    icon: BarChart2 },
  ]},
  { title: "Conta", items: [
    { href: "/dashboard/company",  label: "Minha Empresa",   icon: Building2 },
    { href: "/dashboard/sources",  label: "Fontes de Dados", icon: Database },
  ]},
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const [userName, setUserName]       = useState("Usuário");
  const [tenantName, setTenantName]   = useState("");
  const [role, setRole]               = useState("");
  const [newAlerts, setNewAlerts]     = useState(0);

  useEffect(() => {
    const token = localStorage.getItem("proc_token");
    if (!token) { router.replace("/login"); return; }
    setUserName(localStorage.getItem("proc_user_name") || "Usuário");
    setTenantName(localStorage.getItem("proc_tenant_name") || "");
    setRole(localStorage.getItem("proc_user_role") || "");

    const api = process.env.NEXT_PUBLIC_API_URL ?? "";

    // Nome da empresa/perfil sempre fresco (evita cache antigo no localStorage)
    fetch(`${api}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return;
        setTenantName(d.tenant_name || "");
        setUserName(d.name || "Usuário");
        setRole(d.role || "");
        localStorage.setItem("proc_tenant_name", d.tenant_name || "");
        localStorage.setItem("proc_user_role", d.role || "");
        localStorage.setItem("proc_user_name", d.name || "");
      })
      .catch(() => {});

    // Busca contagem de alertas novos
    fetch(`${api}/api/alerts/summary`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => setNewAlerts(d.novos ?? 0))
      .catch(() => {});
  }, [router]);

  function logout() {
    ["proc_token", "proc_user_id", "proc_user_name", "proc_tenant_id", "proc_tenant_name"].forEach(k =>
      localStorage.removeItem(k)
    );
    router.push("/login");
  }

  const initial = userName.charAt(0).toUpperCase();

  // Área de Usuários só para o Admin da empresa (entra no grupo "Conta")
  const groups = navGroups.map(g =>
    g.title === "Conta" && role === "admin"
      ? { ...g, items: [...g.items, { href: "/dashboard/users", label: "Usuários", icon: Users }] }
      : g
  );

  function isActive(item: { href: string; exact?: boolean }) {
    return item.exact ? pathname === item.href : pathname.startsWith(item.href);
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-60 fixed top-0 left-0 h-full bg-proc-900 flex flex-col z-40">
        {/* Brand */}
        <div className="px-5 pt-6 pb-5 border-b border-white/10">
          <div className="flex items-center gap-2.5 mb-3">
            <Logo size={32} />
            <div>
              <div className="font-bold text-white text-sm leading-tight">Sonar</div>
              <div className="text-[11px] text-white/40 leading-tight">por Drive Data</div>
            </div>
          </div>
          {tenantName && (
            <div className="bg-white/5 rounded-lg px-3 py-2">
              <div className="text-[11px] text-white/40">Empresa</div>
              <div className="text-xs text-white font-medium truncate">{tenantName}</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
          {groups.map((group, gi) => (
            <div key={gi} className={gi > 0 ? "mt-5" : ""}>
              {group.title && (
                <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-white/25">
                  {group.title}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map(item => {
                  const active = isActive(item);
                  return (
                    <Link key={item.href} href={item.href}
                      className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all duration-200 group ${
                        active
                          ? "text-white font-semibold bg-white/[0.07]"
                          : "text-white/55 hover:text-white hover:bg-white/[0.04] hover:translate-x-0.5"
                      }`}>
                      {active && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-1 rounded-r-full dd-gradient" />
                      )}
                      <item.icon
                        size={17}
                        className={`shrink-0 transition-transform duration-200 ${
                          active ? "text-proc-300" : "text-white/45 group-hover:text-white/85 group-hover:scale-110"
                        }`}
                      />
                      <span className="flex-1">{item.label}</span>
                      {item.label === "Alertas" && newAlerts > 0 && (
                        <span className="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center dd-pop">
                          {newAlerts}
                        </span>
                      )}
                      {active && <ChevronRight size={14} className="text-white/40" />}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* User */}
        <div className="px-3 pb-4 pt-3 border-t border-white/10">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition cursor-default">
            <div className="w-7 h-7 rounded-full bg-proc-500 flex items-center justify-center text-xs font-bold text-white shrink-0">
              {initial}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-white truncate">{userName}</div>
            </div>
            <button onClick={logout} title="Sair"
              className="text-white/40 hover:text-white transition">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main — rola por padrão; páginas com layout próprio (bids/detalhe) usam h-screen internamente */}
      <main className="ml-60 flex-1 h-screen overflow-y-auto">
        <div key={pathname} className="dd-page">{children}</div>
      </main>

      <ChatWidget />
    </div>
  );
}
