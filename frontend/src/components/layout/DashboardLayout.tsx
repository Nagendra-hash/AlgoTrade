"use client";
import { useState, useEffect, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useAuthStore } from "@/store/authStore";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard":             "Dashboard",
  "/markets":               "Markets",
  "/watchlist":             "Watchlist",
  "/trading-opportunities": "Trading Opportunities",
  "/orders":                "Orders",
  "/positions":             "Positions",
  "/portfolio":             "Portfolio",
  "/alerts-news":           "Alerts & News",
  "/strategies":            "Strategies",
  "/ai-assistant":          "AI Assistant",
  "/ai-models":             "AI Models",
  "/broker-settings":       "Broker Settings",
};

interface Props { children: ReactNode; }

export function DashboardLayout({ children }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mounted,    setMounted]    = useState(false);
  const { isAuthenticated } = useAuthStore();
  const router   = useRouter();
  const pathname = usePathname();

  // Wait for client mount before checking auth (avoids hydration mismatch)
  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  // Show spinner until mounted
  if (!mounted) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Show spinner while redirecting
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const title = PAGE_TITLES[pathname] ?? "TradeAI";

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      <Sidebar isMobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Topbar onMobileMenuOpen={() => setMobileOpen(true)} title={title} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
