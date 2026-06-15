"use client";
// Path: frontend/src/app/backtest/page.tsx
// Backtesting workbench — Phase 6
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  PlayCircle, TrendingUp, TrendingDown, AlertTriangle, Trophy,
  Activity, BarChart3, Sparkles, IndianRupee,
} from "lucide-react";
import {
  useBacktestStrategies, useRunBacktest,
  type BacktestResult,
} from "@/hooks/useBacktest";

const INTERVALS = ["1d", "1h", "1w"];
const PERIODS   = ["3mo", "6mo", "1y", "2y", "5y"];

const PRESET_SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "TATAMOTORS", "BHARTIARTL"];

export default function BacktestPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [strategy, setStrategy] = useState("trend_following");
  const [interval, setInterval] = useState("1d");
  const [period, setPeriod] = useState("1y");
  const [capital, setCapital] = useState(1_000_000);

  const stratsQuery = useBacktestStrategies();
  const runMut      = useRunBacktest();

  const onRun = () => {
    runMut.mutate({
      symbol: symbol.trim().toUpperCase(),
      strategy_type: strategy,
      interval, period,
      initial_capital: capital,
    });
  };

  const result: BacktestResult | undefined = runMut.data;

  return (
    <DashboardLayout>
      <div className="space-y-5" data-testid="backtest-root">
        {/* Header */}
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-amber-500/10 border border-amber-500/30 rounded-full text-amber-300 text-[11px] font-bold tracking-widest uppercase mb-2">
              <BarChart3 className="h-3 w-3" /> Workbench
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white">Backtesting</h1>
            <p className="text-gray-500 text-sm mt-1">Replay strategy logic against historical candles · Sharpe · Drawdown · Profit factor.</p>
          </div>
        </div>

        {/* Configurator */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-5" data-testid="backtest-config">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
            {/* Symbol */}
            <div className="md:col-span-3">
              <label className="block text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">Symbol</label>
              <input
                data-testid="backtest-symbol-input"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full px-3 py-2.5 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-lg text-sm text-white tabular-nums outline-none"
                placeholder="RELIANCE"
              />
              <div className="mt-2 flex flex-wrap gap-1">
                {PRESET_SYMBOLS.map((s) => (
                  <button
                    key={s}
                    data-testid={`backtest-preset-${s}`}
                    onClick={() => setSymbol(s)}
                    className={cn(
                      "text-[10px] px-2 py-1 rounded-md border tabular-nums font-bold tracking-wide transition-all",
                      s === symbol
                        ? "bg-amber-500/15 border-amber-500/40 text-amber-200"
                        : "bg-gray-950 border-gray-800 text-gray-500 hover:text-gray-300 hover:border-gray-700"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Strategy */}
            <div className="md:col-span-3">
              <label className="block text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">Strategy</label>
              <select
                data-testid="backtest-strategy-select"
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="w-full px-3 py-2.5 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-lg text-sm text-white outline-none"
              >
                {(stratsQuery.data?.strategies ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </div>

            {/* Interval */}
            <div className="md:col-span-2">
              <label className="block text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">Interval</label>
              <select
                data-testid="backtest-interval-select"
                value={interval}
                onChange={(e) => setInterval(e.target.value)}
                className="w-full px-3 py-2.5 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-lg text-sm text-white outline-none"
              >
                {INTERVALS.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>

            {/* Period */}
            <div className="md:col-span-2">
              <label className="block text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">Period</label>
              <select
                data-testid="backtest-period-select"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="w-full px-3 py-2.5 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-lg text-sm text-white outline-none"
              >
                {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>

            {/* Capital */}
            <div className="md:col-span-2">
              <label className="block text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">Capital ₹</label>
              <input
                data-testid="backtest-capital-input"
                type="number"
                value={capital}
                step={10000}
                onChange={(e) => setCapital(Number(e.target.value) || 0)}
                className="w-full px-3 py-2.5 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-lg text-sm text-white tabular-nums outline-none"
              />
            </div>
          </div>

          <div className="mt-5 flex items-center justify-between gap-3">
            <p className="text-xs text-gray-500">
              Historical data from Yahoo Finance with PostgreSQL + Redis caching. Daily candles are cached for 24h, intraday for 1h.
            </p>
            <button
              data-testid="backtest-run-btn"
              disabled={runMut.isPending || !symbol.trim()}
              onClick={onRun}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-500 hover:bg-amber-400 disabled:bg-gray-800 disabled:text-gray-600 text-gray-950 rounded-xl text-sm font-black tracking-wider uppercase transition-all"
            >
              <PlayCircle className="h-4 w-4" />
              {runMut.isPending ? "Running…" : "Run Backtest"}
            </button>
          </div>
        </div>

        {runMut.isError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3" data-testid="backtest-error">
            <AlertTriangle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-bold text-red-300">Backtest failed</p>
              <p className="text-red-200/80 text-xs mt-1">{(runMut.error as Error)?.message ?? "Unknown error"}</p>
            </div>
          </div>
        )}

        {result && <ResultPanel result={result} />}
      </div>
    </DashboardLayout>
  );
}

function ResultPanel({ result }: { result: BacktestResult }) {
  const s = result.summary;
  const ret = s.total_return ?? 0;
  const isProfit = ret >= 0;

  return (
    <div className="space-y-5" data-testid="backtest-result">
      {/* Hero */}
      <div className={cn(
        "rounded-2xl p-6 border",
        isProfit
          ? "bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent border-emerald-500/30"
          : "bg-gradient-to-br from-red-500/10 via-red-500/5 to-transparent border-red-500/30"
      )} data-testid="backtest-result-hero">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-500">Total Return</p>
            <p className={cn(
              "text-5xl font-black tabular-nums mt-1",
              isProfit ? "text-emerald-300" : "text-red-300"
            )}>
              {isProfit ? "+" : ""}{ret.toFixed(2)}%
            </p>
            <p className="text-gray-400 text-sm mt-2">
              {s.symbol} · {s.strategy_type.replace(/_/g, " ")} · {s.interval} · {s.period} · {s.candles_used} bars
            </p>
          </div>
          <div className="text-right">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-500">Final Capital</p>
            <p className="text-3xl font-black text-white tabular-nums">
              ₹{(s.final_capital ?? 0).toLocaleString("en-IN")}
            </p>
            <p className={cn("text-sm font-semibold tabular-nums mt-1", isProfit ? "text-emerald-400" : "text-red-400")}>
              {isProfit ? "+" : ""}₹{(s.total_pnl ?? 0).toLocaleString("en-IN")} P&L
            </p>
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="backtest-kpis">
        <KPI testid="kpi-trades"    icon={Activity}   label="Trades"        value={String(s.total_trades)} />
        <KPI testid="kpi-winrate"   icon={Trophy}     label="Win Rate"      value={`${s.win_rate?.toFixed(1) ?? 0}%`}
             tone={s.win_rate >= 50 ? "good" : "warn"} />
        <KPI testid="kpi-sharpe"    icon={Sparkles}   label="Sharpe Ratio"  value={(s.sharpe_ratio ?? 0).toFixed(2)}
             tone={s.sharpe_ratio >= 1 ? "good" : s.sharpe_ratio >= 0 ? "warn" : "bad"} />
        <KPI testid="kpi-drawdown"  icon={TrendingDown} label="Max Drawdown" value={`${s.max_drawdown?.toFixed(2) ?? 0}%`}
             tone={s.max_drawdown <= 10 ? "good" : s.max_drawdown <= 20 ? "warn" : "bad"} />
        <KPI testid="kpi-pf"        icon={TrendingUp} label="Profit Factor" value={(s.profit_factor ?? 0).toFixed(2)}
             tone={s.profit_factor >= 1.5 ? "good" : s.profit_factor >= 1 ? "warn" : "bad"} />
      </div>

      {/* Equity curve (ASCII-ish but smooth via SVG) */}
      {result.equity_curve.length > 1 && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-5" data-testid="backtest-equity">
          <h2 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-amber-400" /> Equity Curve
          </h2>
          <EquityChart points={result.equity_curve.map((p) => p.value)} positive={isProfit} />
          <div className="flex items-center justify-between mt-2 text-[11px] text-gray-500 tabular-nums">
            <span>Start: ₹{(s.initial_capital ?? 0).toLocaleString("en-IN")}</span>
            <span>End: ₹{(s.final_capital ?? 0).toLocaleString("en-IN")}</span>
          </div>
        </div>
      )}

      {/* Trades */}
      <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white flex items-center gap-2"><IndianRupee className="h-4 w-4 text-amber-400" /> Trade Ledger</h2>
          <span className="text-xs text-gray-500">{result.trades.length} trades shown</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="backtest-trades-table">
            <thead className="bg-gray-950 text-[11px] uppercase tracking-wider text-gray-500">
              <tr>
                <th className="text-left px-4 py-3">Entry</th>
                <th className="text-left px-4 py-3">Exit</th>
                <th>Qty</th><th>Buy ₹</th><th>Sell ₹</th><th>P&L</th><th>%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {result.trades.length === 0 && (
                <tr><td colSpan={7} className="text-center text-gray-500 py-10">No trades executed by this strategy on the given window.</td></tr>
              )}
              {result.trades.map((t, i) => (
                <tr key={`${t.entry_date}-${t.exit_date}-${i}`} className="hover:bg-gray-800/30" data-testid={`bt-trade-${i}`}>
                  <td className="px-4 py-2.5 text-gray-300 text-xs font-mono">{t.entry_date}</td>
                  <td className="px-4 py-2.5 text-gray-300 text-xs font-mono">{t.exit_date}</td>
                  <td className="text-center text-gray-300 tabular-nums">{t.qty}</td>
                  <td className="text-center text-gray-300 tabular-nums">₹{t.entry_price?.toFixed(2)}</td>
                  <td className="text-center text-gray-300 tabular-nums">₹{t.exit_price?.toFixed(2)}</td>
                  <td className={cn("text-center tabular-nums font-semibold", (t.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {(t.pnl ?? 0) >= 0 ? "+" : "-"}₹{Math.abs(t.pnl ?? 0).toLocaleString("en-IN")}
                  </td>
                  <td className={cn("text-center tabular-nums font-semibold", (t.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {(t.pnl_pct ?? 0).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KPI({ testid, icon: Icon, label, value, tone = "neutral" }: {
  testid: string; icon: any; label: string; value: string;
  tone?: "good" | "warn" | "bad" | "neutral";
}) {
  const colour =
    tone === "good" ? "text-emerald-300"
    : tone === "warn" ? "text-amber-300"
    : tone === "bad"  ? "text-red-300"
    : "text-white";
  const bg =
    tone === "good" ? "bg-emerald-500/10 border-emerald-500/25"
    : tone === "warn" ? "bg-amber-500/10 border-amber-500/25"
    : tone === "bad"  ? "bg-red-500/10 border-red-500/25"
    : "bg-gray-900/60 border-gray-800";

  return (
    <div data-testid={testid} className={cn("border rounded-xl p-4", bg)}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={cn("h-3.5 w-3.5", colour)} />
        <p className="text-gray-500 text-[10px] font-bold uppercase tracking-wider">{label}</p>
      </div>
      <p className={cn("text-2xl font-black tabular-nums", colour)}>{value}</p>
    </div>
  );
}

function EquityChart({ points, positive }: { points: number[]; positive: boolean }) {
  if (!points || points.length === 0) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = Math.max(max - min, 1);
  const w = 1000;
  const h = 220;
  const step = w / Math.max(points.length - 1, 1);
  const path = points
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * (h - 20) - 10;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const colour = positive ? "rgb(16 185 129)" : "rgb(239 68 68)";
  const fillColour = positive ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)";
  const fillPath = `${path} L ${w} ${h} L 0 ${h} Z`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-44" preserveAspectRatio="none" data-testid="backtest-equity-svg">
      <path d={fillPath} fill={fillColour} />
      <path d={path} stroke={colour} strokeWidth={2} fill="none" />
    </svg>
  );
}
