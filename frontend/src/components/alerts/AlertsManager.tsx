"use client";
// Path: frontend/src/components/alerts/AlertsManager.tsx
import { useState, useMemo } from "react";
import { Plus, Search, Bell, BellOff, CheckCircle2, RefreshCw, Loader2 } from "lucide-react";
import { useAlerts } from "@/hooks/useAlerts";
import { AlertCard } from "./AlertCard";
import { CreateAlertModal } from "./CreateAlertModal";
import { cn } from "@/lib/utils";
import type { Alert } from "@/types";

const TABS = [
  { id: "all",       label: "All",       icon: Bell },
  { id: "active",    label: "Active",    icon: Bell },
  { id: "triggered", label: "Triggered", icon: CheckCircle2 },
  { id: "paused",    label: "Paused",    icon: BellOff },
];

interface AlertsManagerProps {
  onSymbolClick?: (symbol: string) => void;
}

export function AlertsManager({ onSymbolClick }: AlertsManagerProps) {
  const [tab, setTab]       = useState("all");
  const [search, setSearch] = useState("");
  const [modal, setModal]   = useState(false);
  const [editAlert, setEdit]= useState<Alert | null>(null);

  const { data, isLoading, refetch, isFetching } = useAlerts(tab !== "all" ? tab : undefined);

  const filtered = useMemo(() => {
    if (!data?.alerts) return [];
    if (!search.trim()) return data.alerts;
    const q = search.trim().toUpperCase();
    return data.alerts.filter((a) =>
      a.symbol.includes(q) ||
      (a.name ?? "").toUpperCase().includes(q) ||
      (a.news_sources ?? []).some((src: string) => src.toUpperCase().includes(q)) ||
      a.condition.toUpperCase().includes(q)
    );
  }, [data?.alerts, search]);

  const counts = { all: data?.total ?? 0, active: data?.active ?? 0, triggered: data?.triggered ?? 0, paused: data?.paused ?? 0 };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-shrink-0">
        <div>
          <h2 className="text-white font-bold text-xl">Price Alerts</h2>
          <p className="text-gray-400 text-sm mt-0.5">Get notified on price moves</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} disabled={isFetching}
            className="h-9 w-9 flex items-center justify-center bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-gray-400 hover:text-white transition-all">
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          </button>
          <button onClick={() => { setEdit(null); setModal(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-orange-500/20">
            <Plus className="h-4 w-4" /> New Alert
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-4 flex-shrink-0">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search symbol or name..."
          className="w-full pl-10 pr-4 py-2.5 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 bg-gray-800/50 p-1 rounded-xl flex-shrink-0">
        {TABS.map((t) => {
          const Icon = t.icon;
          const count = counts[t.id as keyof typeof counts];
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={cn("flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-semibold transition-all",
                tab === t.id ? "bg-gray-900 text-white shadow" : "text-gray-500 hover:text-gray-300")}>
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{t.label}</span>
              {count > 0 && (
                <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none",
                  tab === t.id ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-400")}>{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-48"><Loader2 className="h-7 w-7 text-blue-400 animate-spin" /></div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-52 text-center px-6">
            <div className="h-14 w-14 rounded-2xl bg-gray-800 flex items-center justify-center mb-4">
              <Bell className="h-7 w-7 text-gray-600" />
            </div>
            <p className="text-gray-400 font-medium">{search ? `No results for "${search}"` : "No alerts yet"}</p>
            {!search && (
              <button onClick={() => { setEdit(null); setModal(true); }}
                className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-sm font-semibold transition-all mt-4">
                <Plus className="h-4 w-4" /> Create Alert
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3 pb-4">
            {filtered.map((a) => (
              <AlertCard
                key={a.id}
                alert={a}
                onEdit={(alert) => { setEdit(alert); setModal(true); }}
                onSymbolClick={onSymbolClick}
              />
            ))}
          </div>
        )}
      </div>

      <CreateAlertModal open={modal} onClose={() => { setModal(false); setEdit(null); }} editAlert={editAlert} />
    </div>
  );
}
