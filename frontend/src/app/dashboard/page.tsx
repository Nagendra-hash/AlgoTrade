"use client";
// Path: frontend/src/app/dashboard/page.tsx
import { useState, useEffect } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { MarketSentimentWidget } from "@/components/sentiment/MarketSentimentWidget";
import { useAuthStore } from "@/store/authStore";
import { usePortfolioSummary } from "@/hooks/usePortfolio";
import { useIndices } from "@/hooks/useMarket";
import { useOrders } from "@/hooks/useOrders";
import { formatCompact, formatPercent, getPnLColor, getPnLBg, cn } from "@/lib/utils";
import { Briefcase, TrendingUp, TrendingDown, Activity, RefreshCw, ArrowUpRight, ArrowDownLeft, CheckCircle2, Clock, XCircle } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const WATCHLIST = ["RELIANCE","TCS","INFY","HDFCBANK","SBIN","NIFTY50","BANKNIFTY"];

function generateEquity(days: number) {
  const data = []; let val = 1_000_000;
  const now = new Date();
  for (let i = days; i >= 0; i--) {
    const d = new Date(now); d.setDate(d.getDate() - i);
    val = Math.max(800_000, val + (Math.random() - 0.45) * 15000);
    data.push({ date: d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" }), value: Math.round(val) });
  }
  return data;
}

const STATUS_CFG: Record<string, { color: string; icon: React.ElementType }> = {
  COMPLETE:  { color: "text-green-400",  icon: CheckCircle2 },
  PENDING:   { color: "text-yellow-400", icon: Clock },
  OPEN:      { color: "text-blue-400",   icon: Clock },
  CANCELLED: { color: "text-gray-400",   icon: XCircle },
  REJECTED:  { color: "text-red-400",    icon: XCircle },
};

export default function DashboardPage() {
  const { user }     = useAuthStore();
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary();
  const { data: indices = [] }  = useIndices();
  const { data: orders  = [] }  = useOrders();
  const [equityData] = useState(() => generateEquity(30));
  const [activeFrame, setActiveFrame] = useState("1M");

  const isPos = (summary?.total_pnl ?? 0) >= 0;

  const stats = [
    { label: "Portfolio Value",  value: formatCompact(summary?.current_value  ?? 1_284_500), icon: Briefcase,    color: "text-blue-400",   bg: "bg-blue-500/10",   change: summary?.total_pnl_pct },
    { label: "Today's P&L",      value: formatCompact(Math.abs(summary?.day_pnl ?? 8240)),   icon: isPos ? TrendingUp : TrendingDown, color: getPnLColor(summary?.day_pnl ?? 0), bg: getPnLBg(summary?.day_pnl ?? 0), change: undefined },
    { label: "Total P&L",        value: formatCompact(Math.abs(summary?.total_pnl ?? 42180)),icon: Activity,    color: getPnLColor(summary?.total_pnl ?? 0), bg: getPnLBg(summary?.total_pnl ?? 0), change: summary?.total_pnl_pct },
    { label: "Holdings",         value: String(summary?.holdings_count ?? 6),                 icon: Briefcase,   color: "text-purple-400", bg: "bg-purple-500/10", change: undefined },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Greeting */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white">Good morning, {user?.username ?? "Trader"} 👋</h2>
            <p className="text-gray-400 text-sm mt-0.5">Here&rsquo;s your portfolio overview</p>
          </div>
        </div>

        {/* Indices ticker */}
        {indices.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="flex overflow-x-auto scrollbar-hide">
              <div className="flex gap-6 py-3 px-4 whitespace-nowrap">
                {indices.map((q) => (
                  <div key={q.symbol} className="flex items-center gap-3">
                    <span className="text-gray-400 text-xs font-semibold">{q.symbol}</span>
                    <span className="text-white text-xs font-bold">₹{q.ltp?.toLocaleString("en-IN")}</span>
                    <span className={cn("text-xs font-semibold", getPnLColor(q.change_pct))}>
                      {q.change_pct >= 0 ? "+" : ""}{q.change_pct?.toFixed(2)}%
                    </span>
                    <div className="h-3 w-px bg-gray-700" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
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
                {s.change !== undefined && (
                  <p className={cn("text-xs font-medium mt-1", getPnLColor(s.change))}>
                    {s.change >= 0 ? "+" : ""}{s.change?.toFixed(2)}% all time
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Equity chart + Sentiment */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Chart */}
          <div className="xl:col-span-2 bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-white font-bold text-lg">Portfolio Performance</h3>
                <p className={cn("text-sm font-semibold mt-0.5", getPnLColor(summary?.total_pnl ?? 0))}>
                  {(summary?.total_pnl ?? 0) >= 0 ? "+" : ""}₹{Math.abs(summary?.total_pnl ?? 42180).toLocaleString("en-IN")} overall
                </p>
              </div>
              <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
                {["1W","1M","3M"].map((f) => (
                  <button key={f} onClick={() => setActiveFrame(f)}
                    className={cn("px-3 py-1.5 rounded-md text-xs font-semibold transition-all",
                      activeFrame === f ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white")}>
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={equityData.slice(activeFrame === "1W" ? -7 : activeFrame === "1M" ? -30 : -90)}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={isPos ? "#22c55e" : "#ef4444"} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={isPos ? "#22c55e" : "#ef4444"} stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `₹${(v/100_000).toFixed(0)}L`} width={48} />
                <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: "12px", fontSize: "12px" }}
                  formatter={(v: number) => [`₹${v.toLocaleString("en-IN")}`, "Value"]} />
                <Area type="monotone" dataKey="value" stroke={isPos ? "#22c55e" : "#ef4444"} strokeWidth={2} fill="url(#grad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Sentiment */}
          <div className="xl:col-span-1">
            <MarketSentimentWidget symbols={WATCHLIST} />
          </div>
        </div>

        {/* Recent orders */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between p-5 border-b border-gray-800">
            <h3 className="text-white font-bold text-lg">Recent Orders</h3>
            <a href="/orders" className="text-blue-400 text-sm hover:underline">View all</a>
          </div>
          <div className="divide-y divide-gray-800">
            {orders.slice(0, 5).map((o) => {
              const isBuy = o.side === "BUY";
              const cfg   = STATUS_CFG[o.status] ?? { color: "text-gray-400", icon: Clock };
              const StatusIcon = cfg.icon;
              return (
                <div key={o.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-800/40 transition-colors">
                  <div className={cn("h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0", isBuy ? "bg-green-500/10" : "bg-red-500/10")}>
                    {isBuy ? <ArrowDownLeft className="h-4 w-4 text-green-400" /> : <ArrowUpRight className="h-4 w-4 text-red-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-white font-semibold text-sm">{o.symbol}</p>
                      <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded border", isBuy ? "bg-green-400/10 text-green-400 border-green-500/20" : "bg-red-400/10 text-red-400 border-red-500/20")}>{o.side}</span>
                      <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded border", o.is_paper_trade === "true" ? "bg-blue-400/10 text-blue-400 border-blue-500/20" : "bg-orange-400/10 text-orange-400 border-orange-500/20")}>
                        {o.is_paper_trade === "true" ? "Paper" : "Live"}
                      </span>
                    </div>
                    <p className="text-gray-500 text-xs mt-0.5">{o.quantity} shares · {new Date(o.placed_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-semibold text-sm">{o.average_price ? `₹${o.average_price.toLocaleString("en-IN")}` : o.price ? `₹${o.price}` : "Market"}</p>
                  </div>
                  <div className={cn("flex items-center gap-1 text-xs font-semibold", cfg.color)}>
                    <StatusIcon className="h-3.5 w-3.5" />{o.status}
                  </div>
                </div>
              );
            })}
            {orders.length === 0 && (
              <div className="py-10 text-center text-gray-500 text-sm">No orders yet. Place your first trade!</div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
