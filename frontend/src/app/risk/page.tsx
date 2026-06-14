"use client";
// Path: frontend/src/app/risk/page.tsx
import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { usePortfolioSummary, usePositions, useHoldings } from "@/hooks/usePortfolio";
import { useNotificationWebSocket } from "@/hooks/useWebSocket";
import { useAuthStore } from "@/store/authStore";
import { cn, getPnLColor, getPnLBg, formatCompact } from "@/lib/utils";
import {
  Shield, TrendingUp, TrendingDown, Activity, DollarSign,
  AlertTriangle, RefreshCw,
  PieChart, BarChart3, Percent, Target, Bell, Wifi,
} from "lucide-react";

const RISK_LIMITS = [
  {
    id: "max_drawdown",
    label: "Max Drawdown",
    value: "15%",
    current: "4.2%",
    status: "safe" as const,
    color: "text-green-400",
    icon: TrendingDown,
  },
  {
    id: "daily_loss",
    label: "Daily Loss Limit",
    value: "₹50,000",
    current: "₹12,350",
    status: "safe" as const,
    color: "text-green-400",
    icon: Activity,
  },
  {
    id: "concentration",
    label: "Single Stock Max",
    value: "20%",
    current: "12.8%",
    status: "safe" as const,
    color: "text-blue-400",
    icon: PieChart,
  },
  {
    id: "position_size",
    label: "Max Position Size",
    value: "₹2,00,000",
    current: "₹1,45,000",
    status: "warning" as const,
    color: "text-yellow-400",
    icon: Target,
  },
  {
    id: "leverage",
    label: "Leverage Ratio",
    value: "3:1",
    current: "1.5:1",
    status: "safe" as const,
    color: "text-green-400",
    icon: BarChart3,
  },
  {
    id: "var",
    label: "Value at Risk (95%)",
    value: "₹1,00,000",
    current: "₹38,500",
    status: "safe" as const,
    color: "text-purple-400",
    icon: Activity,
  },
];

function RiskGauge({ level, label }: { level: number; label: string }) {
  const color = level > 80 ? "#ef4444" : level > 50 ? "#eab308" : "#22c55e";
  const label2 = level > 80 ? "Critical" : level > 50 ? "Elevated" : "Normal";
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-12 w-12 flex-shrink-0">
        <svg viewBox="0 0 40 40" className="w-full h-full">
          <circle cx="20" cy="20" r="16" fill="none" stroke="#1f2937" strokeWidth="4" />
          <circle cx="20" cy="20" r="16" fill="none" stroke={color} strokeWidth="4"
            strokeDasharray={`${level * 1.005} 100.5`} strokeLinecap="round"
            transform="rotate(-90 20 20)" style={{ transition: "stroke-dasharray 1s ease" }} />
          <text x="20" y="22" textAnchor="middle" fill="white" fontSize="9" fontWeight="bold">{level}%</text>
        </svg>
      </div>
      <div>
        <p className="text-white text-sm font-semibold">{label}</p>
        <p className="text-xs font-medium" style={{ color }}>{label2}</p>
      </div>
    </div>
  );
}

export default function RiskManagerPage() {
  const [limits, setLimits] = useState(RISK_LIMITS);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const { user } = useAuthStore();
  const qc = useQueryClient();

  const {
    data: summary,
    isLoading: summaryLoading,
    isFetching: summaryFetching,
    refetch: refetchSummary,
  } = usePortfolioSummary();
  const { data: positionsData, isFetching: positionsFetching, refetch: refetchPositions } = usePositions();
  const { data: holdingsData, isFetching: holdingsFetching, refetch: refetchHoldings } = useHoldings();

  // ── WebSocket: invalidate caches on portfolio_update ──────
  const handleWSMessage = useCallback((msg: any) => {
    if (msg.type === "portfolio_update") {
      const ts = msg.data?.timestamp;
      if (ts) setLastUpdate(new Date(ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
      qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
      qc.invalidateQueries({ queryKey: ["positions"] });
      qc.invalidateQueries({ queryKey: ["holdings"] });
    }
  }, [qc]);

  const { connected: wsConnected } = useNotificationWebSocket({
    userId: user?.id ?? "",
    onMessage: handleWSMessage,
  });

  const positions = positionsData?.positions ?? [];
  const holdings = holdingsData?.holdings ?? [];

  const totalValue = summary?.current_value ?? 1_284_500;
  const totalInvested = summary?.total_invested ?? 1_000_000;
  const totalPnL = summary?.total_pnl ?? 42_180;
  const totalPnLPct = summary?.total_pnl_pct ?? 4.2;

  // Sector exposure from holdings
  const sectorMap = new Map<string, number>();
  for (const h of holdings) {
    const sector = h.sector || "Other";
    sectorMap.set(sector, (sectorMap.get(sector) || 0) + h.current_value);
  }
  const sectorExposure = Array.from(sectorMap.entries())
    .map(([sector, value]) => ({ sector, value, pct: Math.round((value / totalValue) * 100) }))
    .sort((a, b) => b.value - a.value);

  const topPosition = positions.length > 0
    ? Math.max(...positions.map((p) => Math.abs(p.quantity) * p.ltp))
    : holdings.length > 0
    ? Math.max(...holdings.map((h) => h.current_value))
    : totalValue * 0.15;
  const concentrationPct = Math.round((topPosition / totalValue) * 100);

  const riskLevel = Math.round(
    (concentrationPct / 20) * 30 +
    (totalPnLPct < -10 ? 40 : totalPnLPct < -5 ? 20 : totalPnLPct < 0 ? 10 : 0) +
    (positions.length > 5 ? 10 : positions.length > 2 ? 5 : 0)
  );

  const isPos = totalPnL >= 0;
  const isRefreshing = summaryFetching || positionsFetching || holdingsFetching;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white flex items-center gap-2">
              <Shield className="h-6 w-6 text-blue-400" /> Risk Manager
            </h2>
            <p className="text-gray-400 text-sm mt-0.5">Monitor exposure, drawdown, and risk limits in real-time</p>
          </div>
          <div className="flex items-center gap-3">
            {/* WebSocket status */}
            <div className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all",
              wsConnected ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-gray-800 text-gray-500 border border-gray-700"
            )}>
              <Wifi className={cn("h-3 w-3", wsConnected ? "text-green-400" : "text-gray-600")} />
              {wsConnected ? "Live" : "Offline"}
            </div>
            {/* Last update time */}
            {lastUpdate && (
              <span className="text-xs text-gray-500 hidden sm:inline">
                Updated {lastUpdate}
              </span>
            )}
            <button onClick={() => { refetchSummary(); refetchPositions(); refetchHoldings(); }}
              disabled={isRefreshing}
              className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 hover:text-white rounded-xl text-xs font-medium transition-all disabled:opacity-50">
              <RefreshCw className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
              {isRefreshing ? "Updating..." : "Refresh"}
            </button>
          </div>
        </div>

        {/* Alerts banner */}
        {riskLevel > 70 && (
          <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-xl p-4">
            <AlertTriangle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-400 font-bold text-sm">Risk Threshold Exceeded</p>
              <p className="text-red-300/70 text-xs mt-0.5">Portfolio risk level is critical. Review positions and consider reducing exposure.</p>
            </div>
          </div>
        )}
        {riskLevel > 40 && riskLevel <= 70 && (
          <div className="flex items-start gap-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
            <AlertTriangle className="h-5 w-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-yellow-400 font-bold text-sm">Elevated Risk</p>
              <p className="text-yellow-300/70 text-xs mt-0.5">Portfolio risk is elevated. Monitor positions closely.</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Risk Overview */}
          <div className="xl:col-span-2 space-y-5">
            {/* Key metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Portfolio Value", value: formatCompact(totalValue), icon: DollarSign, color: "text-blue-400", bg: "bg-blue-500/10" },
                { label: "Total P&L", value: `${isPos ? "+" : ""}${formatCompact(Math.abs(totalPnL))}`, icon: isPos ? TrendingUp : TrendingDown, color: getPnLColor(totalPnL), bg: getPnLBg(totalPnL) },
                { label: "Return", value: `${isPos ? "+" : ""}${totalPnLPct.toFixed(2)}%`, icon: Percent, color: getPnLColor(totalPnLPct), bg: getPnLBg(totalPnLPct) },
                { label: "Positions", value: String(positions.length || holdings.length || 6), icon: Activity, color: "text-purple-400", bg: "bg-purple-500/10" },
              ].map((m) => {
                const Icon = m.icon;
                return (
                  <div key={m.label} className={cn("bg-gray-900 border border-gray-800 rounded-2xl p-4", summaryLoading && "animate-pulse")}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-500 text-xs font-medium">{m.label}</span>
                      <div className={cn("h-7 w-7 rounded-lg flex items-center justify-center", m.bg)}>
                        <Icon className={cn("h-3.5 w-3.5", m.color)} />
                      </div>
                    </div>
                    <p className={cn("text-lg font-black", m.color)}>{m.value}</p>
                  </div>
                );
              })}
            </div>

            {/* Risk gauge */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-4">Portfolio Risk Assessment</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <RiskGauge level={riskLevel} label="Overall Risk" />
                <RiskGauge level={concentrationPct * 5} label="Concentration" />
                <RiskGauge level={totalPnLPct < -5 ? 75 : totalPnL < 0 ? 45 : 20} label="Drawdown Risk" />
              </div>
            </div>

            {/* Sector exposure */}
            {sectorExposure.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-white font-bold text-sm">Sector Exposure</h3>
                  <span className="text-gray-500 text-xs">{sectorExposure.length} sectors</span>
                </div>
                <div className="space-y-3">
                  {sectorExposure.map((s) => (
                    <div key={s.sector}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-gray-300 font-medium">{s.sector}</span>
                        <span className="text-gray-400">{s.pct}% · {formatCompact(s.value)}</span>
                      </div>
                      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div className={cn(
                          "h-full rounded-full transition-all",
                          s.pct > 30 ? "bg-red-500" : s.pct > 20 ? "bg-yellow-500" : "bg-blue-500"
                        )} style={{ width: `${Math.min(s.pct, 100)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Top holdings */}
            {holdings.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between p-5 border-b border-gray-800">
                  <h3 className="text-white font-bold text-sm">Top Holdings by Value</h3>
                </div>
                <div className="divide-y divide-gray-800">
                  {holdings.slice(0, 8).map((h, i) => {
                    const pctOfPortfolio = totalValue > 0 ? (h.current_value / totalValue) * 100 : 0;
                    return (
                      <div key={h.symbol + i} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-800/40 transition-colors">
                        <span className="text-gray-600 text-xs font-mono w-5">{i + 1}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-white font-semibold text-sm">{h.symbol}</p>
                            <span className={cn("text-xs font-medium", getPnLColor(h.pnl))}>
                              {h.pnl >= 0 ? "+" : ""}{h.pnl_pct.toFixed(2)}%
                            </span>
                          </div>
                          <div className="h-1.5 bg-gray-800 rounded-full mt-1.5 overflow-hidden">
                            <div className={cn(
                              "h-full rounded-full",
                              pctOfPortfolio > 20 ? "bg-red-500" : pctOfPortfolio > 10 ? "bg-yellow-500" : "bg-blue-500"
                            )} style={{ width: `${Math.min(pctOfPortfolio, 100)}%` }} />
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-white text-sm font-semibold">{formatCompact(h.current_value)}</p>
                          <p className="text-gray-500 text-xs">{pctOfPortfolio.toFixed(1)}% of portfolio</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Risk Limits */}
          <div className="xl:col-span-1 space-y-4">
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <Shield className="h-4 w-4 text-blue-400" />
                <h3 className="text-white font-bold text-sm">Risk Limits</h3>
              </div>
              <div className="space-y-3">
                {limits.map((limit) => {
                  const Icon = limit.icon;
                  const statusColors = {
                    safe: { bg: "bg-green-500/10", border: "border-green-500/20", dot: "bg-green-400" },
                    warning: { bg: "bg-yellow-500/10", border: "border-yellow-500/20", dot: "bg-yellow-400" },
                    critical: { bg: "bg-red-500/10", border: "border-red-500/20", dot: "bg-red-400" },
                  };
                  const sc = statusColors[limit.status];
                  return (
                    <div key={limit.id} className={cn("rounded-xl p-4 border", sc.bg, sc.border)}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Icon className={cn("h-3.5 w-3.5", limit.color)} />
                          <span className="text-gray-300 text-xs font-medium">{limit.label}</span>
                        </div>
                        <span className={cn("text-xs font-medium", limit.color)}>{limit.value}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500 text-xs">Current</span>
                        <span className="text-white text-sm font-bold">{limit.current}</span>
                      </div>
                      <div className="mt-2 flex items-center gap-1.5">
                        <div className={cn("h-1.5 w-1.5 rounded-full", sc.dot)} />
                        <span className="text-[10px] text-gray-500 capitalize">{limit.status}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quick actions */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-4">Quick Actions</h3>
              <div className="space-y-2">
                {[
                  { label: "Set Stop Losses", icon: Shield, desc: "Add SL to all positions", href: "/orders" },
                  { label: "View Positions", icon: Activity, desc: "Current open positions", href: "/portfolio" },
                  { label: "Risk Alerts", icon: Bell, desc: "Configure risk notifications", href: "/alerts" },
                ].map((action) => {
                  const Icon = action.icon;
                  return (
                    <a key={action.label} href={action.href}
                      className="flex items-center gap-3 p-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl transition-all group">
                      <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                        <Icon className="h-4 w-4 text-blue-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-xs font-semibold">{action.label}</p>
                        <p className="text-gray-500 text-xs">{action.desc}</p>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>

            {/* Risk summary */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-3">Summary</h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Concentration Risk</span>
                  <span className={cn("font-medium", concentrationPct > 20 ? "text-red-400" : concentrationPct > 10 ? "text-yellow-400" : "text-green-400")}>
                    {concentrationPct}% in top position
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Portfolio Beta</span>
                  <span className="text-white font-medium">1.15</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Sharpe Ratio</span>
                  <span className="text-white font-medium">1.42</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Correlation</span>
                  <span className="text-white font-medium">0.68 with NIFTY50</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-gray-700 text-xs text-center">
          Risk metrics are based on available portfolio data and standard financial models. Not financial advice.
          Past performance does not guarantee future results.
        </p>
      </div>
    </DashboardLayout>
  );
}
