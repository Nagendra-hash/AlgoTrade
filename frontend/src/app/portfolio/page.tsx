"use client";
// Path: frontend/src/app/portfolio/page.tsx
import { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { SentimentBadge } from "@/components/sentiment/SentimentBadge";
import { usePortfolioSummary } from "@/hooks/usePortfolio";
import { useBrokerStatus } from "@/hooks/useBroker";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatCompact, formatPercent, getPnLColor, getPnLBg, cn } from "@/lib/utils";
import {
  Briefcase, TrendingUp, TrendingDown, Wallet,
  Loader2, AlertCircle, CheckCircle2, RefreshCw,
  ExternalLink, Shield,
} from "lucide-react";

interface Holding {
  symbol:         string;
  exchange:       string;
  quantity:       number;
  average_price:  number;
  ltp:            number;
  current_value:  number;
  invested_value: number;
  pnl:            number;
  pnl_pct:        number;
  change_pct:     number;
  sector?:        string;
  is_real?:       boolean;
}

interface HoldingsResponse {
  holdings:   Holding[];
  source:     "angel_one" | "sample";
  is_real:    boolean;
  message?:   string;
  client_id?: string;
  fetched_at: string;
}

function useHoldingsReal() {
  return useQuery<HoldingsResponse>({
    queryKey: ["holdings-real"],
    queryFn: () => api.get("/portfolio/holdings").then((r) => r.data),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export default function PortfolioPage() {
  const [sortBy,  setSortBy]  = useState<"pnl"|"value"|"pct">("value");
  const [sortDir, setSortDir] = useState<"asc"|"desc">("desc");

  const { data: holdingsResp, isLoading, refetch, isFetching } = useHoldingsReal();
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary();
  const { data: brokerStatus } = useBrokerStatus();

  const holdings = holdingsResp?.holdings ?? [];
  const isReal   = (holdingsResp?.is_real ?? false) && !!holdingsResp?.client_id;
  const source   = holdingsResp?.source   ?? "sample";

  const angelConnected = (brokerStatus ?? []).some(
    (b) => b.broker === "angel_one" && b.is_connected
  );

  const sorted = [...holdings].sort((a, b) => {
    const key = sortBy === "pnl" ? "pnl" : sortBy === "pct" ? "pnl_pct" : "current_value";
    const aVal = a[key as keyof typeof a];
    const bVal = b[key as keyof typeof b];
    if (typeof aVal !== "number" || typeof bVal !== "number") return 0;
    return sortDir === "desc" ? bVal - aVal : aVal - bVal;
  });

  const toggleSort = (k: typeof sortBy) => {
    if (sortBy === k) setSortDir((d) => d === "desc" ? "asc" : "desc");
    else { setSortBy(k); setSortDir("desc"); }
  };

  const stats = [
    {
      label: "Portfolio Value",
      value: formatCompact(summary?.current_value ?? 0),
      icon: Briefcase,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
      sub: isReal ? "Live from Angel One" : angelConnected ? "Awaiting data" : "Not connected",
    },
    {
      label: "Total Invested",
      value: formatCompact(summary?.total_invested ?? 0),
      icon: Wallet,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
    },
    {
      label: "Total P&L",
      value: `${(summary?.total_pnl ?? 0) >= 0 ? "+" : ""}${formatCompact(Math.abs(summary?.total_pnl ?? 0))}`,
      icon: (summary?.total_pnl ?? 0) >= 0 ? TrendingUp : TrendingDown,
      color: getPnLColor(summary?.total_pnl ?? 0),
      bg: getPnLBg(summary?.total_pnl ?? 0),
    },
    {
      label: "Returns",
      value: formatPercent(summary?.total_pnl_pct ?? 0),
      icon: TrendingUp,
      color: getPnLColor(summary?.total_pnl_pct ?? 0),
      bg: getPnLBg(summary?.total_pnl_pct ?? 0),
    },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white">Portfolio</h2>
            <p className="text-gray-400 text-sm mt-0.5">
              {isReal
                ? `Live data from Angel One · ${holdingsResp?.client_id ?? ""}`
                : angelConnected
                  ? "Broker connected — waiting for live holdings"
                  : "Broker not connected — connect Angel One in Settings for live data"}
            </p>
          </div>
          <button onClick={() => refetch()} disabled={isFetching}
            className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-gray-400 hover:text-white text-sm transition-all">
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
            Refresh
          </button>
        </div>

        {/* Source banner */}
        {isReal ? (
          <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/20 rounded-xl px-4 py-3">
            <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />
            <p className="text-green-400 text-sm font-medium">
              Showing real portfolio data from Angel One ({holdingsResp?.client_id})
            </p>
            <span className="ml-auto text-green-300/60 text-xs">
              Updated {holdingsResp?.fetched_at
                ? new Date(holdingsResp.fetched_at).toLocaleTimeString("en-IN")
                : "just now"}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-3 bg-yellow-500/10 border border-yellow-500/20 rounded-xl px-4 py-3">
            <AlertCircle className="h-4 w-4 text-yellow-400 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-yellow-400 text-sm">
                Showing sample data.{" "}
                <a href="/broker-settings" className="underline font-semibold hover:text-yellow-300">
                  Connect Angel One in Settings
                </a>{" "}
                to see your real holdings.
              </p>
              {angelConnected && (
                <p className="text-yellow-300/70 text-xs mt-1">
                  Your Angel One is connected but the backend couldn&apos;t fetch your holdings.
                  Try reconnecting or check the server logs.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.label} className={cn("bg-gray-900 border border-gray-800 rounded-2xl p-5", summaryLoading && "animate-pulse")}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-gray-400 text-xs font-medium">{s.label}</span>
                  <div className={cn("h-8 w-8 rounded-lg flex items-center justify-center", s.bg)}>
                    <Icon className={cn("h-4 w-4", s.color)} />
                  </div>
                </div>
                <p className={cn("text-2xl font-black", s.color)}>{s.value}</p>
                {s.sub && <p className="text-gray-600 text-xs mt-1">{s.sub}</p>}
              </div>
            );
          })}
        </div>

        {/* Holdings table */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between p-5 border-b border-gray-800 flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <h3 className="text-white font-bold text-lg">
                Holdings ({holdings.length})
              </h3>
              {isReal && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-green-500/10 border border-green-500/20 rounded-full">
                  <div className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-green-400 text-xs font-semibold">Live</span>
                </div>
              )}
            </div>
            <div className="flex gap-2">
              {(["P&L", "Value", "P&L %"] as const).map((label, i) => {
                const key = (["pnl", "value", "pct"] as const)[i];
                return (
                  <button key={key} onClick={() => toggleSort(key)}
                    className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                      sortBy === key ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white")}>
                    {label} {sortBy === key ? (sortDir === "desc" ? "↓" : "↑") : ""}
                  </button>
                );
              })}
            </div>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-7 w-7 text-blue-400 animate-spin" />
            </div>
          ) : holdings.length === 0 ? (
            <div className="text-center py-14">
              <Briefcase className="h-10 w-10 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-400 font-medium">No holdings found</p>
              <p className="text-gray-600 text-sm mt-1">
                {isReal
                  ? "Your Angel One account has no holdings, or session expired."
                  : "Connect Angel One in Settings to see your portfolio."}
              </p>
              {!isReal && (
                <a href="/broker-settings"
                  className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-sm font-semibold transition-all">
                  <ExternalLink className="h-4 w-4" /> Go to Settings
                </a>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-800">
                    {["Symbol","Qty","Avg Price","LTP","Invested","Cur Value","P&L","P&L %","Sentiment"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((h, i) => (
                    <tr key={h.symbol + i}
                      className={cn("border-b border-gray-800/50 hover:bg-gray-800/40 transition-colors",
                        i === sorted.length - 1 && "border-0")}>
                      <td className="px-4 py-4">
                        <p className="text-white font-bold text-sm">{h.symbol}</p>
                        <p className="text-gray-500 text-xs">{h.exchange}{h.sector ? ` · ${h.sector}` : ""}</p>
                      </td>
                      <td className="px-4 py-4 text-gray-300 text-sm">{h.quantity}</td>
                      <td className="px-4 py-4 text-gray-300 text-sm">₹{h.average_price?.toLocaleString("en-IN")}</td>
                      <td className="px-4 py-4">
                        <p className="text-white font-semibold text-sm">₹{h.ltp?.toLocaleString("en-IN")}</p>
                        <p className={cn("text-xs font-medium", getPnLColor(h.change_pct))}>
                          {h.change_pct >= 0 ? "+" : ""}{h.change_pct?.toFixed(2)}%
                        </p>
                      </td>
                      <td className="px-4 py-4 text-gray-400 text-sm">₹{h.invested_value?.toLocaleString("en-IN")}</td>
                      <td className="px-4 py-4 text-white font-semibold text-sm">₹{h.current_value?.toLocaleString("en-IN")}</td>
                      <td className={cn("px-4 py-4 text-sm font-bold", getPnLColor(h.pnl))}>
                        {h.pnl >= 0 ? "+" : ""}₹{Math.abs(h.pnl)?.toLocaleString("en-IN")}
                      </td>
                      <td className="px-4 py-4">
                        <span className={cn("text-xs font-bold px-2 py-1 rounded-lg border", getPnLBg(h.pnl_pct), getPnLColor(h.pnl_pct))}>
                          {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct?.toFixed(2)}%
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <SentimentBadge symbol={h.symbol} size="sm" showTooltip />
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t border-gray-700">
                  <tr className="bg-gray-800/50">
                    <td className="px-4 py-4 text-white font-black text-sm" colSpan={4}>TOTAL</td>
                    <td className="px-4 py-4 text-gray-300 font-bold text-sm">
                      ₹{(summary?.total_invested ?? 0).toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-4 text-white font-black text-sm">
                      ₹{(summary?.current_value ?? 0).toLocaleString("en-IN")}
                    </td>
                    <td className={cn("px-4 py-4 text-sm font-black", getPnLColor(summary?.total_pnl ?? 0))}>
                      {(summary?.total_pnl ?? 0) >= 0 ? "+" : ""}₹{Math.abs(summary?.total_pnl ?? 0).toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-4">
                      <span className={cn("text-xs font-black px-2 py-1 rounded-lg border",
                        getPnLBg(summary?.total_pnl_pct ?? 0), getPnLColor(summary?.total_pnl_pct ?? 0))}>
                        {(summary?.total_pnl_pct ?? 0) >= 0 ? "+" : ""}{summary?.total_pnl_pct?.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-4" />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
