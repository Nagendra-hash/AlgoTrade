"use client";
// Path: frontend/src/app/trading-opportunities/page.tsx
// Trading Opportunities — Phase 4. Live composite of screener + sentiment + 52W range.
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { RefreshCw, Search, Target, TrendingUp, TrendingDown, AlertTriangle, Info } from "lucide-react";

interface Opportunity {
  symbol: string; company: string; ltp: number | null; change_pct: number | null;
  volume: number | null; news_sentiment: string; sentiment_score: number;
  bullish_score: number; bearish_score: number;
  promoter_holding: number | null; fii_holding: number | null; dii_holding: number | null;
  market_cap: number | null; sector: string;
  rsi: number | null; macd: number | null; macd_signal: number | null; macd_state: string;
  high_52w: number | null; low_52w: number | null;
  risk_level: string; confidence: number;
  recommended_action: "Buy" | "Watch" | "Avoid"; composite_score: number;
  ai_summary: string;
}

interface ApiResp {
  generated_at: string; total_universe: number; items: Opportunity[]; no_live_data: boolean;
}

const ACTION_COLORS: Record<string, string> = {
  Buy:   "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Watch: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  Avoid: "bg-red-500/15 text-red-300 border-red-500/30",
};
const RISK_COLORS: Record<string, string> = {
  low:      "text-emerald-400",
  moderate: "text-sky-400",
  elevated: "text-amber-400",
  high:     "text-red-400",
};

function fmtNum(n: number | null, digits = 2) { return n == null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: digits }); }
function fmtVol(n: number | null) {
  if (n == null) return "—";
  if (n >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(2) + " L";
  return n.toLocaleString("en-IN");
}

export default function TradingOpportunitiesPage() {
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const { data, isLoading, isError, refetch, isFetching } = useQuery<ApiResp>({
    queryKey: ["opportunities"],
    queryFn: async () => (await api.get("/opportunities", { params: { limit: 30 } })).data,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  const items = data?.items ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    return items.filter((o) => {
      if (actionFilter !== "all" && o.recommended_action !== actionFilter) return false;
      if (!q) return true;
      return o.symbol.includes(q) || o.company.toUpperCase().includes(q) || o.sector.toUpperCase().includes(q);
    });
  }, [items, search, actionFilter]);

  const stats = useMemo(() => ({
    buy:    items.filter((i) => i.recommended_action === "Buy").length,
    watch:  items.filter((i) => i.recommended_action === "Watch").length,
    avoid:  items.filter((i) => i.recommended_action === "Avoid").length,
    bullish:items.filter((i) => i.bullish_score > i.bearish_score).length,
  }), [items]);

  return (
    <DashboardLayout>
      <div className="space-y-5" data-testid="opportunities-root">
        {/* Header */}
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-amber-500/10 border border-amber-500/30 rounded-full text-amber-300 text-[11px] font-bold tracking-widest uppercase mb-2">
              <Target className="h-3 w-3" /> Live · Today's Setups
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white">Trading Opportunities</h1>
            <p className="text-gray-500 text-sm mt-1">Stocks ranked by composite of news sentiment, technicals (RSI / MACD / momentum), and 52-week range.</p>
            {data?.generated_at && (
              <p className="text-gray-600 text-xs mt-1 font-mono">Generated {new Date(data.generated_at).toLocaleTimeString("en-IN")} · Universe: {data.total_universe}</p>
            )}
          </div>
          <button onClick={() => refetch()} disabled={isFetching} data-testid="opportunities-refresh-btn"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-gray-900 border border-gray-800 hover:border-amber-500/40 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50">
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} /> Refresh
          </button>
        </div>

        {/* Stat strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatPill testid="opp-stat-buy"   label="Buy signals"     value={stats.buy}   icon={TrendingUp} color="text-emerald-300" />
          <StatPill testid="opp-stat-watch" label="Watch"          value={stats.watch} icon={Info} color="text-amber-300" />
          <StatPill testid="opp-stat-avoid" label="Avoid"          value={stats.avoid} icon={AlertTriangle} color="text-red-300" />
          <StatPill testid="opp-stat-bullish" label="Bullish bias" value={stats.bullish} icon={TrendingUp} color="text-sky-300" />
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
            <input data-testid="opportunities-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search symbol, company or sector…"
              className="w-full pl-9 pr-3 py-2.5 bg-gray-900 border border-gray-800 focus:border-amber-500/50 rounded-xl text-sm text-white placeholder-gray-600 outline-none" />
          </div>
          <div className="flex bg-gray-900 border border-gray-800 rounded-xl p-1 text-xs font-semibold">
            {["all", "Buy", "Watch", "Avoid"].map((a) => (
              <button key={a} onClick={() => setActionFilter(a)} data-testid={`opp-filter-${a.toLowerCase()}`}
                className={cn("px-3 py-1.5 rounded-lg transition-all", actionFilter === a ? "bg-amber-500 text-gray-950" : "text-gray-400 hover:text-white")}>
                {a === "all" ? "All" : a}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="opportunities-table">
              <thead className="bg-gray-950 text-gray-500 text-[11px] uppercase tracking-wider">
                <tr>
                  <Th>Symbol</Th><Th>Company</Th><Th>LTP</Th><Th>Δ%</Th><Th>Volume</Th>
                  <Th>News</Th><Th>Bull</Th><Th>Bear</Th>
                  <Th title="Promoter %">Prom</Th><Th>FII</Th><Th>DII</Th><Th>M-Cap</Th>
                  <Th>Sector</Th><Th>RSI</Th><Th>MACD</Th>
                  <Th>52W H</Th><Th>52W L</Th><Th>Risk</Th><Th>Conf</Th><Th>Action</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {isLoading && (
                  <tr><td colSpan={20} className="px-4 py-12 text-center text-gray-500">Loading live opportunities…</td></tr>
                )}
                {!isLoading && isError && (
                  <tr><td colSpan={20} className="px-4 py-12 text-center text-red-400">Failed to load. Try refreshing.</td></tr>
                )}
                {!isLoading && !isError && filtered.length === 0 && (
                  <tr><td colSpan={20} className="px-4 py-12 text-center text-gray-500" data-testid="opportunities-empty">No live data available.</td></tr>
                )}
                {filtered.map((o) => (
                  <tr key={o.symbol} className="hover:bg-gray-800/30" data-testid={`opp-row-${o.symbol}`}>
                    <Td><span className="font-black text-white">{o.symbol}</span></Td>
                    <Td><span className="text-gray-300">{o.company}</span></Td>
                    <Td className="tabular-nums">{o.ltp != null ? `₹${fmtNum(o.ltp)}` : "—"}</Td>
                    <Td className={cn("tabular-nums font-semibold", (o.change_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                      {o.change_pct == null ? "—" : `${o.change_pct >= 0 ? "+" : ""}${o.change_pct.toFixed(2)}%`}
                    </Td>
                    <Td className="tabular-nums text-gray-300">{fmtVol(o.volume)}</Td>
                    <Td><SentimentBadge label={o.news_sentiment} score={o.sentiment_score} /></Td>
                    <Td className="tabular-nums text-emerald-400 font-semibold">{o.bullish_score}</Td>
                    <Td className="tabular-nums text-red-400 font-semibold">{o.bearish_score}</Td>
                    <Td className="text-gray-500">{o.promoter_holding == null ? "—" : `${o.promoter_holding}%`}</Td>
                    <Td className="text-gray-500">{o.fii_holding == null ? "—" : `${o.fii_holding}%`}</Td>
                    <Td className="text-gray-500">{o.dii_holding == null ? "—" : `${o.dii_holding}%`}</Td>
                    <Td className="text-gray-500">{o.market_cap == null ? "—" : fmtVol(o.market_cap)}</Td>
                    <Td className="text-gray-300">{o.sector}</Td>
                    <Td className={cn("tabular-nums", (o.rsi ?? 50) > 70 ? "text-red-400" : (o.rsi ?? 50) < 30 ? "text-emerald-400" : "text-gray-300")}>
                      {o.rsi == null ? "—" : o.rsi.toFixed(1)}
                    </Td>
                    <Td className={cn("text-xs font-semibold", o.macd_state === "bullish" ? "text-emerald-400" : "text-red-400")}>
                      {o.macd_state === "bullish" ? "↑" : "↓"} {o.macd != null ? o.macd.toFixed(2) : "—"}
                    </Td>
                    <Td className="text-gray-400 tabular-nums">{o.high_52w == null ? "—" : `₹${fmtNum(o.high_52w)}`}</Td>
                    <Td className="text-gray-400 tabular-nums">{o.low_52w == null ? "—" : `₹${fmtNum(o.low_52w)}`}</Td>
                    <Td className={cn("font-semibold capitalize", RISK_COLORS[o.risk_level])}>{o.risk_level}</Td>
                    <Td className="tabular-nums">
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-amber-400" style={{ width: `${Math.min(100, o.confidence)}%` }} />
                        </div>
                        <span className="text-gray-300 text-xs">{o.confidence.toFixed(0)}</span>
                      </div>
                    </Td>
                    <Td>
                      <span data-testid={`opp-action-${o.symbol}`} className={cn("inline-flex px-2.5 py-1 rounded-md border text-[11px] font-bold", ACTION_COLORS[o.recommended_action])}>
                        {o.recommended_action}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI summary panel for first row (or selected) */}
        {filtered[0] && (
          <div className="bg-gray-900/60 border border-amber-500/20 rounded-2xl p-5" data-testid="opportunities-ai-panel">
            <p className="text-[11px] font-bold text-amber-300 uppercase tracking-widest mb-2">AI take — {filtered[0].symbol}</p>
            <p className="text-gray-300 text-sm leading-relaxed">{filtered[0].ai_summary}</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function Th({ children, title }: { children: any; title?: string }) {
  return <th title={title} className="text-left font-semibold px-3 py-3 whitespace-nowrap">{children}</th>;
}
function Td({ children, className = "" }: { children: any; className?: string }) {
  return <td className={`px-3 py-2.5 whitespace-nowrap ${className}`}>{children}</td>;
}
function StatPill({ testid, label, value, icon: Icon, color }: any) {
  return (
    <div data-testid={testid} className="flex items-center gap-3 bg-gray-900/60 border border-gray-800 rounded-xl p-4">
      <div className={cn("h-9 w-9 rounded-lg bg-gray-950 flex items-center justify-center", color)}><Icon className="h-4 w-4" /></div>
      <div>
        <p className="text-gray-500 text-[11px] uppercase tracking-wider font-semibold">{label}</p>
        <p className={cn("text-2xl font-black", color)}>{value}</p>
      </div>
    </div>
  );
}
function SentimentBadge({ label, score }: { label: string; score: number }) {
  const cls = label === "bullish" ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
            : label === "bearish" ? "bg-red-500/15 text-red-300 border-red-500/30"
            : "bg-gray-700/30 text-gray-400 border-gray-600/30";
  return <span className={cn("inline-flex px-2 py-0.5 rounded border text-[10px] font-bold uppercase", cls)}>{label} {score >= 0 ? "+" : ""}{score}</span>;
}
