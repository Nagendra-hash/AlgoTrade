"use client";
// Path: frontend/src/components/layout/Sidebar.tsx
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard, TrendingUp, Briefcase, ShoppingCart,
  Sparkles, BarChart2, Bell, MessageSquare, Settings,
  LogOut, ChevronLeft, ChevronRight, Store, Shield, X, Zap, Globe,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";

const NAV = [
  { group: "Main",      items: [
    { label: "Dashboard",  href: "/dashboard",   icon: LayoutDashboard },
    { label: "Market",     href: "/market",      icon: TrendingUp },
    { label: "Portfolio",  href: "/portfolio",   icon: Briefcase },
    { label: "Orders",     href: "/orders",      icon: ShoppingCart },
  ]},
  { group: "AI Tools",  items: [
    { label: "AI Strategy",href: "/strategy",    icon: Sparkles,      badge: "AI" },
    { label: "Backtest",   href: "/backtest",    icon: BarChart2 },
    { label: "AI Chat",    href: "/ai-chat",     icon: MessageSquare, badge: "AI" },
    { label: "Auto Trade", href: "/auto-trade",  icon: Zap },
  ]},
  { group: "Tools",     items: [
    { label: "Alerts & News", href: "/alerts",   icon: Bell },
    { label: "Geo Monitor",   href: "/geo-monitor", icon: Globe, badge: "NEW" },
    { label: "Marketplace",   href: "/marketplace", icon: Store },
    { label: "Risk Manager",  href: "/risk",     icon: Shield },
  ]},
];

interface Props { isMobileOpen: boolean; onMobileClose: () => void; }

export function Sidebar({ isMobileOpen, onMobileClose }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  const handleLogout = () => { logout(); window.location.href = "/login"; };

  const content = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className={cn("flex items-center gap-3 px-4 py-5 border-b border-gray-800", collapsed ? "justify-center" : "justify-between")}>
        <div className="flex items-center gap-2 min-w-0">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="h-4 w-4 text-white" />
          </div>
          {!collapsed && <span className="font-black text-lg bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent truncate">TradeAI</span>}
        </div>
        <button onClick={() => setCollapsed(!collapsed)} className="hidden lg:flex text-gray-500 hover:text-white">
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-6">
        {NAV.map((group) => (
          <div key={group.group}>
            {!collapsed && <p className="text-xs text-gray-600 font-semibold uppercase tracking-widest px-3 mb-2">{group.group}</p>}
            <ul className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <li key={item.href}>
                    <Link href={item.href} onClick={onMobileClose}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group",
                        active ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "text-gray-400 hover:text-white hover:bg-gray-800",
                        collapsed && "justify-center px-2"
                      )} title={collapsed ? item.label : undefined}>
                      <Icon className={cn("h-4 w-4 flex-shrink-0", active ? "text-blue-400" : "text-gray-500 group-hover:text-white")} />
                      {!collapsed && (
                        <>
                          <span className="flex-1">{item.label}</span>
                          {"badge" in item && item.badge && (
                            <span className="bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[10px] px-1.5 py-0 rounded-full font-bold">{item.badge}</span>
                          )}
                        </>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-800 p-3 space-y-1">
        <Link href="/settings" className={cn("flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-all", collapsed && "justify-center")}>
          <Settings className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span>Settings</span>}
        </Link>
        <button onClick={handleLogout} className={cn("w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all", collapsed && "justify-center")}>
          <LogOut className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
        {!collapsed && user && (
          <div className="flex items-center gap-3 px-3 py-3 mt-2 bg-gray-800/50 rounded-lg">
            <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {user.username?.[0]?.toUpperCase() ?? "U"}
            </div>
            <div className="min-w-0">
              <p className="text-white text-sm font-semibold truncate">{user.username}</p>
              <p className="text-gray-500 text-xs truncate">{user.email}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      <aside className={cn("hidden lg:flex flex-col h-screen bg-gray-900 border-r border-gray-800 transition-all duration-300 flex-shrink-0", collapsed ? "w-16" : "w-64")}>
        {content}
      </aside>
      {isMobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onMobileClose} />
          <aside className="relative w-72 bg-gray-900 border-r border-gray-800 h-full flex flex-col z-10">
            <button onClick={onMobileClose} className="absolute top-4 right-4 text-gray-400 hover:text-white"><X className="h-5 w-5" /></button>
            {content}
          </aside>
        </div>
      )}
    </>
  );
}
