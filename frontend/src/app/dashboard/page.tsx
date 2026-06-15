"use client";
// Path: frontend/src/app/dashboard/page.tsx
// Real-data-only dashboard. Shows live indices, real portfolio summary, real orders.
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { MarketSentimentWidget } from "@/components/sentiment/MarketSentimentWidget";
import { useAuthStore } from "@/store/authStore";
import { usePortfolioSummary } from "@/hooks/usePortfolio";
import { useIndices, useMarketStatus } from "@/hooks/useMarket";
import { useOrders } from "@/hooks/useOrders";
import { useBrokerStatus } from "@/hooks/useBroker";
import { formatCompact, getPnLColor, getPnLBg, cn } from "@/lib/utils";
import { Briefcase, TrendingUp, TrendingDown, Activity, ArrowUpRight, ArrowDownLeft, CheckCircle2, Clock, XCircle, Plug, Target, Bell } from "lucide-react";
import Link from "next/link";

const WATCHLIST = ["RELIANCE","TCS","INFY","HDFCBANK","SBIN","NIFTY50","BANKNIFTY"];

const STATUS_CFG: Record<string, { color: string; icon: React.ElementType }> = {
  COMPLETE:  { color: "text-emerald-400", icon: CheckCircle2 },
  PENDING:   { color: "text-amber-300",   icon: Clock },
  OPEN:      { color: "text-sky-400",     icon: Clock },
  CANCELLED: { color: "text-gray-400",    icon: XCircle },
  REJECTED:  { color: "text-red-400",     icon: XCircle },
};

function StatCard({ label, value, sub, icon: Icon, color, bg, testid }: any) {
  return (
    <div data-testid={testid} className="bg-gray-900/60 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-gray-500 text-[11px] font-semibold uppercase tracking-wider">{label}</span>
        <div className={cn("h-8 w-8 rounded-lg flex items-center justify-center", bg)}>
          <Icon className={cn("h-4 w-4", color)} />
        </div>
      </div>
      <p className={cn("text-2xl font-black tracking-tight", color)}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { data: summary, isLoading: summaryLoading } = usePortfolioSummary();
  const { data: indices = [] } = useIndices();
  const { data: orders = [] } = useOrders();
  const { data: marketStatus } = useMarketStatus();
  const { data: brokerStatuses } = useBrokerStatus();

  const connectedBroker = Array.isArray(brokerStatuses) ? brokerStatuses.find((b) => b.is_connected) : null;
  const hasPortfolio = summary && (summary.holdings_count ?? 0) > 0;
  const isPos = (summary?.total_pnl ?? 0) >= 0;

  return (
    <DashboardLayout>
      <div className="space-y-6" data-testid="dashboard-root">
        {/* Greeting */}
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <p className="text-amber-400 text-xs font-bold tracking-widest uppercase mb-1">{marketStatus?.is_open ? "Markets Open" : "Markets Closed"}</p>
            <h2 className="text-3xl font-black text-white tracking-tight">Welcome back, {user?.username ?? "Trader"}</h2>
            <p className="text-gray-500 text-sm mt-1">Live snapshot of your trading desk.</p>
          </div>
          {!connectedBroker && (
            <Link href="/broker-settings" data-testid="dashboard-connect-broker-cta" className="inline-flex items-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-400 text-gray-950 rounded-xl text-sm font-bold transition-all">
              <Plug className="h-4 w-4" /> Connect Broker
            </Link>
          )}
        </div>

        {/* Indices ticker — real only */}
        {indices.length > 0 ? (
          <div className="bg-gray-900/60 border border-gray-800 rounded-xl overflow-hidden" data-testid="dashboard-indices-ticker">
            <div className="flex overflow-x-auto scrollbar-hide">
              <div className="flex gap-8 py-3 px-5 whitespace-nowrap">
                {indices.map((q: any) => (
                  <div key={q.symbol} className="flex items-center gap-3">
                    <span className="text-gray-500 text-[11px] font-bold uppercase tracking-wider">{q.symbol}</span>
                    <span className="text-white text-sm font-bold tabular-nums">₹{q.ltp?.toLocaleString("en-IN")}</span>
                    <span className={cn("text-xs font-bold tabular-nums", getPnLColor(q.change_pct))}>
                      {q.change_pct >= 0 ? "▲" : "▼"} {Math.abs(q.change_pct)?.toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-gray-900/60 border border-gray-800 rounded-xl px-5 py-4 text-gray-500 text-sm" data-testid="dashboard-indices-empty">
            No live data available. Indices feed will activate once a broker is connected or the market opens.
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4" data-testid="dashboard-stats-grid">
          <StatCard testid="stat-portfolio-value" label="Portfolio Value" value={hasPortfolio ? `₹${formatCompact(summary!.current_value)}` : "—"} sub={hasPortfolio ? undefined : "No holdings"} icon={Briefcase} color="text-sky-300" bg="bg-sky-500/10" />
          <StatCard testid="stat-day-pnl" label="Today's P&L" value={hasPortfolio ? `${(summary!.day_pnl ?? 0) >= 0 ? "+" : "-"}₹${formatCompact(Math.abs(summary!.day_pnl ?? 0))}` : "—"} icon={(summary?.day_pnl ?? 0) >= 0 ? TrendingUp : TrendingDown} color={getPnLColor(summary?.day_pnl ?? 0)} bg={getPnLBg(summary?.day_pnl ?? 0)} />
          <StatCard testid="stat-total-pnl" label="Total P&L" value={hasPortfolio ? `${isPos ? "+" : "-"}₹${formatCompact(Math.abs(summary!.total_pnl ?? 0))}` : "—"} sub={hasPortfolio ? `${(summary!.total_pnl_pct ?? 0).toFixed(2)}% overall` : undefined} icon={Activity} color={getPnLColor(summary?.total_pnl ?? 0)} bg={getPnLBg(summary?.total_pnl ?? 0)} />
          <StatCard testid="stat-holdings" label="Holdings" value={String(summary?.holdings_count ?? 0)} icon={Briefcase} color="text-amber-300" bg="bg-amber-500/10" />
        </div>

        {/* Sentiment + Quick Actions */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2 bg-gray-900/60 border border-gray-800 rounded-2xl p-6" data-testid="dashboard-quick-actions">
            <h3 className="text-white font-bold text-lg mb-4">Quick actions</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <Link href="/trading-opportunities" className="group bg-gray-950/50 hover:bg-gray-950 border border-gray-800 hover:border-amber-500/40 rounded-xl p-4 transition-all">
                <Target className="h-5 w-5 text-amber-400 mb-2" />
                <p className="text-white font-semibold text-sm">Trading Opportunities</p>
                <p className="text-gray-500 text-xs mt-1">Today's highest-probability setups</p>
              </Link>
              <Link href="/alerts-news" className="group bg-gray-950/50 hover:bg-gray-950 border border-gray-800 hover:border-amber-500/40 rounded-xl p-4 transition-all">
                <Bell className="h-5 w-5 text-amber-400 mb-2" />
                <p className="text-white font-semibold text-sm">Alerts &amp; News</p>
                <p className="text-gray-500 text-xs mt-1">Impact-analyzed market news</p>
              </Link>
              <Link href="/strategies" className="group bg-gray-950/50 hover:bg-gray-950 border border-gray-800 hover:border-amber-500/40 rounded-xl p-4 transition-all">
                <Activity className="h-5 w-5 text-amber-400 mb-2" />
                <p className="text-white font-semibold text-sm">Strategies</p>
                <p className="text-gray-500 text-xs mt-1">Build &amp; deploy algos</p>
              </Link>
            </div>
          </div>
          <div className="xl:col-span-1">
            <MarketSentimentWidget symbols={WATCHLIST} />
          </div>
        </div>

        {/* Recent orders */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden" data-testid="dashboard-recent-orders">
          <div className="flex items-center justify-between p-5 border-b border-gray-800">
            <h3 className="text-white font-bold text-lg">Recent Orders</h3>
            <Link href="/orders" className="text-amber-300 text-sm hover:text-amber-200">View all</Link>
          </div>
          {summaryLoading ? (
            <div className="py-10 text-center text-gray-500 text-sm">Loading…</div>
          ) : orders.length === 0 ? (
            <div className="py-10 text-center text-gray-500 text-sm" data-testid="dashboard-recent-orders-empty">No live data available. Place your first trade from the Orders page.</div>
          ) : (
            <div className="divide-y divide-gray-800">
              {orders.slice(0, 5).map((o: any) => {
                const isBuy = o.side === "BUY";
                const cfg = STATUS_CFG[o.status] ?? { color: "text-gray-400", icon: Clock };
                const StatusIcon = cfg.icon;
                return (
                  <div key={o.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-800/30 transition-colors">
                    <div className={cn("h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0", isBuy ? "bg-emerald-500/10" : "bg-red-500/10")}>
                      {isBuy ? <ArrowDownLeft className="h-4 w-4 text-emerald-400" /> : <ArrowUpRight className="h-4 w-4 text-red-400" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-white font-semibold text-sm">{o.symbol}</p>
                        <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded border", isBuy ? "bg-emerald-400/10 text-emerald-400 border-emerald-500/20" : "bg-red-400/10 text-red-400 border-red-500/20")}>{o.side}</span>
                      </div>
                      <p className="text-gray-500 text-xs mt-0.5">{o.quantity} shares · {new Date(o.placed_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-white font-semibold text-sm tabular-nums">{o.average_price ? `₹${o.average_price.toLocaleString("en-IN")}` : o.price ? `₹${o.price}` : "Market"}</p>
                    </div>
                    <div className={cn("flex items-center gap-1 text-xs font-semibold", cfg.color)}>
                      <StatusIcon className="h-3.5 w-3.5" />{o.status}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
