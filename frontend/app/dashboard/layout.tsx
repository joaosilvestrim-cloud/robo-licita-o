"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, FileSearch, Bell, BookmarkCheck,
  LogOut, ChevronRight, BarChart2, Target, Building2, Database,
} from "lucide-react";
import ChatWidget from "../components/ChatWidget";

const nav = [
  { href: "/dashboard",              label: "Dashboard",      icon: LayoutDashboard, exact: true },
  { href: "/dashboard/bids",         label: "Licitações",     icon: FileSearch },
  { href: "/dashboard/alerts",       label: "Alertas",        icon: Bell },
  { href: "/dashboard/profiles",     label: "Meus Perfis",    icon: Target },
  { href: "/dashboard/tracking",     label: "Acompanhando",   icon: BookmarkCheck },
  { href: "/dashboard/reports",      label: "Relatórios",     icon: BarChart2 },
  { href: "/dashboard/company",      label: "Minha Empresa",  icon: Building2 },
  { href: "/dashboard/sources",      label: "Fontes de Dados", icon: Database },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const [userName, setUserName]       = useState("Usuário");
  const [tenantName, setTenantName]   = useState("");
  const [newAlerts, setNewAlerts]     = useState(0);

  useEffect(() => {
    const token = localStorage.getItem("proc_token");
    if (!token) { router.replace("/login"); return; }
    setUserName(localStorage.getItem("proc_user_name") || "Usuário");
    setTenantName(localStorage.getItem("proc_tenant_name") || "");

    // Busca contagem de alertas novos
    const api = process.env.NEXT_PUBLIC_API_URL ?? "";
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
            <div className="w-8 h-8 rounded-lg bg-proc-500 flex items-center justify-center shadow">
              <FileSearch size={16} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-white text-sm leading-tight">Acrasystem</div>
              <div className="text-[11px] text-white/40 leading-tight">Licitações</div>
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
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {nav.map(item => {
            const active = isActive(item);
            return (
              <Link key={item.href} href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition group ${
                  active
                    ? "bg-proc-500 text-white font-medium"
                    : "text-white/60 hover:text-white hover:bg-white/5"
                }`}>
                <item.icon size={16} className={active ? "text-white" : "text-white/50 group-hover:text-white/80"} />
                <span className="flex-1">{item.label}</span>
                {item.label === "Alertas" && newAlerts > 0 && (
                  <span className="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center">
                    {newAlerts}
                  </span>
                )}
                {active && <ChevronRight size={14} className="opacity-60" />}
              </Link>
            );
          })}
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

      {/* Main */}
      <main className="ml-60 flex-1 h-screen overflow-hidden">
        {children}
      </main>

      <ChatWidget />
    </div>
  );
}
