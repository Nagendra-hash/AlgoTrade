"use client";
// Path: frontend/src/components/layout/Topbar.tsx
import { Menu, Sun, Moon, Power, PowerOff, ExternalLink } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { AlertBell } from "@/components/alerts/AlertBell";
import { useAuthStore } from "@/store/authStore";
import { useMarketStatus } from "@/hooks/useMarket";
import { useBrokerStatus } from "@/hooks/useBroker";
import { cn } from "@/lib/utils";

interface Props { onMobileMenuOpen: () => void; title?: string; }

export function Topbar({ onMobileMenuOpen, title = "Dashboard" }: Props) {
  const { theme, setTheme } = useTheme();
  const { user } = useAuthStore();
  const { data: status } = useMarketStatus();
  const { data: brokerStatuses } = useBrokerStatus();

  const connectedBroker = Array.isArray(brokerStatuses)
    ? brokerStatuses.find((b) => b.is_connected)
    : null;

  return (
    <header className="h-14 border-b border-gray-800 bg-gray-950/80 backdrop-blur-md flex items-center gap-4 px-4 flex-shrink-0 sticky top-0 z-40">
      <button onClick={onMobileMenuOpen} className="lg:hidden text-gray-400 hover:text-white">
        <Menu className="h-5 w-5" />
      </button>
      <h1 className="text-lg font-bold text-white hidden sm:block">{title}</h1>
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        {/* Broker connection status */}
        <Link
          href="/settings"
          className={cn(
            "hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all",
            connectedBroker
              ? "bg-orange-500/10 border-orange-500/20 text-orange-400 hover:bg-orange-500/15"
              : "bg-gray-800/50 border-gray-700 text-gray-500 hover:text-gray-300 hover:bg-gray-800"
          )}
          title={connectedBroker ? `${connectedBroker.broker} connected as ${connectedBroker.client_id}` : "Connect a broker in Settings"}
        >
          {connectedBroker
            ? <><Power className="h-3.5 w-3.5 text-orange-400" /><span>Angel One</span></>
            : <><PowerOff className="h-3.5 w-3.5" /><span>Disconnected</span><ExternalLink className="h-3 w-3 opacity-50" /></>
          }
        </Link>

        {status && (
          <div className={cn("hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold",
            status.is_open ? "bg-green-500/10 border-green-500/20 text-green-400" : "bg-red-500/10 border-red-500/20 text-red-400")}>
            <div className={cn("h-2 w-2 rounded-full", status.is_open ? "bg-green-400 animate-pulse" : "bg-red-400")} />
            NSE {status.status}
          </div>
        )}
        <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="h-9 w-9 flex items-center justify-center bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-gray-400 hover:text-white transition-all">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        {user && <AlertBell userId={user.id} />}
      </div>
    </header>
  );
}
