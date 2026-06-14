"use client";
// Path: frontend/src/app/backtest/page.tsx
import { useState, useMemo } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useStrategies } from "@/hooks/useStrategies";
import { useRunBacktest, useCompareBacktests } from "@/hooks/useBacktest";
import type { CompareStrategySlot, CompareBacktestItem } from "@/hooks/useBacktest";
import { cn, getPnLColor } from "@/lib/utils";
import {
  BarChart2, Play, RotateCcw, Loader2, TrendingUp, TrendingDown,
  Activity, DollarSign, Percent,
  AlertCircle, Download, FileText, FileSpreadsheet, Zap, Layers, Plus, X,
} from "lucide-react";
import {
  exportToPDF,
  exportSingleTradesCSV,
  exportCompareResultsCSV,
} from "@/lib/export";

const TIMEFRAMES = ["1m","5m","15m","30m","1h","1d","1w"];
const PERIODS = [
  { label: "1 Month",  value: "1mo" },
  { label: "3 Months", value: "3mo" },
  { label: "6 Months", value: "6mo" },
  { label: "1 Year",   value: "1y" },
  { label: "5 Years",  value: "5y" },
];

const COMPARE_COLORS = ["#22c55e","#3b82f6","#a855f7","#f59e0b","#ef4444","#06b6d4"];

const INITIAL_CAPITAL = 1_000_000;
const STRATEGY_TYPES = [
  { value: "trend_following", label: "Trend Following" },
  { value: "mean_reversion",  label: "Mean Reversion" },
  { value: "momentum",        label: "Momentum" },
];

export default function BacktestPage() {
  const [mode, setMode] = useState<"single" | "compare">("single");

  // ── Single mode state ──────────────────────────────────────
  const [selectedStrategyId, setSelectedStrategyId] = useState("");
  const [symbol, setSymbol] = useState("NIFTY50");
  const [timeframe, setTimeframe] = useState("1d");
  const [period, setPeriod] = useState("1y");
  const [capital, setCapital] = useState(INITIAL_CAPITAL);
  const [results, setResults] = useState<any>(null);
  const [showAllTrades, setShowAllTrades] = useState(false);

  // ── Compare mode state ─────────────────────────────────────
  const [compareSlots, setCompareSlots] = useState<CompareStrategySlot[]>([
    { label: "Trend Follow", strategy_type: "trend_following" },
    { label: "Mean Reversion", strategy_type: "mean_reversion" },
  ]);
  const [compareResults, setCompareResults] = useState<CompareBacktestItem[] | null>(null);

  const { data: strategies = [] } = useStrategies();
  const runBacktest = useRunBacktest();
  const compareBacktests = useCompareBacktests();

  const selectedStrategy = strategies.find((s) => s.id === selectedStrategyId);

  // ── Handlers ───────────────────────────────────────────────

  const handleRun = async () => {
    if (mode === "single") {
      setResults(null);
      try {
        const result = await runBacktest.mutateAsync({
          strategy_id: selectedStrategyId || undefined,
          symbol,
          timeframe,
          period,
          initial_capital: capital,
          save_results: true,
        });
        setResults(result);
      } catch { /* handled by mutation */ }
    } else {
      setCompareResults(null);
      try {
        const result = await compareBacktests.mutateAsync({
          strategies: compareSlots,
          symbol,
          timeframe,
          period,
          initial_capital: capital,
        });
        setCompareResults(result);
      } catch { /* handled by mutation */ }
    }
  };

  const updateSlot = (idx: number, patch: Partial<CompareStrategySlot>) => {
    setCompareSlots((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  };

  const addSlot = () => {
    if (compareSlots.length >= 6) return;
    setCompareSlots((prev) => [
      ...prev,
      { label: `Strategy ${prev.length + 1}`, strategy_type: "trend_following" },
    ]);
  };

  const removeSlot = (idx: number) => {
    if (compareSlots.length <= 2) return;
    setCompareSlots((prev) => prev.filter((_, i) => i !== idx));
  };

  const equityData = useMemo(() => {
    if (!results?.equity_curve) return [];
    return results.equity_curve;
  }, [results]);

  const isPositive = (results?.total_return ?? 0) > 0;
  const isPending = runBacktest.isPending || compareBacktests.isPending;
  const isError = runBacktest.isError || compareBacktests.isError;
  const error = runBacktest.error || compareBacktests.error;

  // ── Comparison chart data (overlaid equity curves) ─────────
  const comparisonChart = useMemo(() => {
    if (!compareResults?.length) return null;
    const series = compareResults.map((item) => {
      const values = (item.result.equity_curve ?? []).map((e: any) => e.value);
      return { label: item.label, values, color: COMPARE_COLORS[compareResults.indexOf(item) % COMPARE_COLORS.length] };
    });
    const allValues = series.flatMap((s) => s.values);
    const min = Math.min(...allValues) || 0;
    const max = Math.max(...allValues) || 1;
    const range = max - min || 1;
    const pointsCount = Math.max(...series.map((s) => s.values.length));
    return { series, min, max, range, pointsCount };
  }, [compareResults]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white flex items-center gap-2">
              <BarChart2 className="h-6 w-6 text-blue-400" /> Backtesting Engine
            </h2>
            <p className="text-gray-400 text-sm mt-0.5">Test strategies against historical market data</p>
          </div>
          {/* Mode toggle */}
          <div className="flex gap-1 bg-gray-800 rounded-xl p-1 border border-gray-700">
            <button onClick={() => { setMode("single"); setCompareResults(null); }}
              className={cn("px-4 py-2 rounded-lg text-xs font-bold transition-all",
                mode === "single" ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20" : "text-gray-500 hover:text-white")}>
              Single
            </button>
            <button onClick={() => { setMode("compare"); setResults(null); }}
              className={cn("px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5",
                mode === "compare" ? "bg-purple-600 text-white shadow-lg shadow-purple-600/20" : "text-gray-500 hover:text-white")}>
              <Layers className="h-3.5 w-3.5" /> Compare
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
          {/* Left: Config */}
          <div className="xl:col-span-1 space-y-4">
            {/* ── SINGLE MODE ── */}
            {mode === "single" && (
              <>
                {/* Strategy selector */}
                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="h-4 w-4 text-purple-400" />
                    <h3 className="text-white font-bold text-sm">Strategy</h3>
                  </div>
                  <select
                    value={selectedStrategyId}
                    onChange={(e) => setSelectedStrategyId(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 appearance-none cursor-pointer">
                    <option value="">Quick Strategy (auto)</option>
                    {strategies.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                  {selectedStrategy && (
                    <div className="mt-3 p-3 bg-gray-800 rounded-xl border border-gray-700">
                      <p className="text-gray-400 text-xs">{selectedStrategy.description}</p>
                      <div className="flex gap-1.5 mt-2 flex-wrap">
                        <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded capitalize">
                          {selectedStrategy.strategy_type.replace("_", " ")}
                        </span>
                        <span className="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded">{selectedStrategy.timeframe}</span>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ── COMPARE MODE ── */}
            {mode === "compare" && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-purple-400" />
                    <h3 className="text-white font-bold text-sm">Strategies ({compareSlots.length})</h3>
                  </div>
                  {compareSlots.length < 6 && (
                    <button onClick={addSlot}
                      className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 font-semibold transition-colors">
                      <Plus className="h-3 w-3" /> Add
                    </button>
                  )}
                </div>
                <div className="space-y-3">
                  {compareSlots.map((slot, idx) => (
                    <div key={idx} className="bg-gray-800 border border-gray-700 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <span className="h-2 w-2 rounded-full flex-shrink-0"
                            style={{ backgroundColor: COMPARE_COLORS[idx % COMPARE_COLORS.length] }} />
                          <input value={slot.label}
                            onChange={(e) => updateSlot(idx, { label: e.target.value })}
                            className="bg-transparent text-white text-xs font-semibold border-b border-transparent hover:border-gray-600 focus:border-blue-500 focus:outline-none flex-1 min-w-0" />
                        </div>
                        {compareSlots.length > 2 && (
                          <button onClick={() => removeSlot(idx)}
                            className="text-gray-600 hover:text-red-400 transition-colors flex-shrink-0 ml-1">
                            <X className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <select value={slot.strategy_id || ""}
                          onChange={(e) => updateSlot(idx, { strategy_id: e.target.value || undefined })}
                          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-gray-300 text-xs focus:outline-none focus:border-blue-500 appearance-none cursor-pointer min-w-0">
                          <option value="">Quick type</option>
                          {strategies.map((s) => (
                            <option key={s.id} value={s.id}>{s.name}</option>
                          ))}
                        </select>
                        {!slot.strategy_id && (
                          <select value={slot.strategy_type}
                            onChange={(e) => updateSlot(idx, { strategy_type: e.target.value })}
                            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-gray-300 text-xs focus:outline-none focus:border-blue-500 appearance-none cursor-pointer min-w-0">
                            {STRATEGY_TYPES.map((t) => (
                              <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Symbol & Timeframe (shared) */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-4">Market Data</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Symbol</label>
                  <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                    placeholder="e.g. NIFTY50, RELIANCE"
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 uppercase" />
                </div>
                <div>
                  <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Timeframe</label>
                  <div className="flex gap-1.5">
                    {TIMEFRAMES.map((tf) => (
                      <button key={tf} onClick={() => setTimeframe(tf)}
                        className={cn("flex-1 py-2 rounded-lg text-xs font-semibold border transition-all",
                          timeframe === tf ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300")}>
                        {tf}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Period</label>
                  <div className="flex gap-1.5">
                    {PERIODS.map((p) => (
                      <button key={p.value} onClick={() => setPeriod(p.value)}
                        className={cn("flex-1 py-2 rounded-lg text-xs font-semibold border transition-all",
                          period === p.value ? "bg-purple-600/20 border-purple-500 text-purple-400" : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300")}>
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Capital */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-white font-bold text-sm mb-4">Parameters</h3>
              <div>
                <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Initial Capital (₹)</label>
                <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500" />
              </div>
            </div>

            {/* Run button */}
            <button onClick={handleRun} disabled={isPending}
              className={cn("w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50 shadow-lg",
                mode === "compare"
                  ? "bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white shadow-purple-600/20"
                  : "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white shadow-blue-600/20"
              )}>
              {isPending ? <><Loader2 className="h-5 w-5 animate-spin" /> Running...</>
                : mode === "compare" ? <><Layers className="h-5 w-5" /> Compare ({compareSlots.length})</>
                : <><Play className="h-5 w-5" /> Run Backtest</>}
            </button>

            {/* Error display */}
            {isError && (
              <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-red-400 text-xs">{error?.message || "Backtest failed. Check symbol and try again."}</p>
              </div>
            )}
          </div>

          {/* Right: Results */}
          <div className="xl:col-span-3 space-y-5">
            {/* ── Empty state ── */}
            {!results && !compareResults && !isPending && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-12 text-center">
                <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/20 flex items-center justify-center mx-auto mb-5">
                  {mode === "compare" ? <Layers className="h-10 w-10 text-purple-400" /> : <BarChart2 className="h-10 w-10 text-blue-400" />}
                </div>
                <h3 className="text-white font-bold text-xl mb-2">
                  {mode === "compare" ? "Compare Strategies" : "Ready to Backtest"}
                </h3>
                <p className="text-gray-400 text-sm max-w-md mx-auto leading-relaxed">
                  {mode === "compare"
                    ? "Add 2–6 strategies below and run them side-by-side on the same historical data."
                    : "Select a strategy and symbol, then click <strong className=\"text-blue-400\">Run Backtest</strong> to simulate performance against historical data."}
                </p>
                <div className="flex items-center justify-center gap-6 mt-6 text-xs text-gray-500">
                  <span>📊 Historical candles</span>
                  <span>⚡ Realistic simulation</span>
                  <span>📈 Win rate & metrics</span>
                </div>
              </div>
            )}

            {/* ── Loading state ── */}
            {isPending && (
              <div className="bg-gray-900 border border-blue-500/20 rounded-2xl p-12 text-center">
                <div className="h-16 w-16 rounded-2xl bg-blue-600/10 flex items-center justify-center mx-auto mb-4 relative">
                  <Activity className="h-8 w-8 text-blue-400" />
                  <div className="absolute inset-0 rounded-2xl border-2 border-blue-500/30 animate-ping" />
                </div>
                <h3 className="text-white font-bold text-lg mb-2">
                  {mode === "compare" ? `Running ${compareSlots.length} Backtests...` : "Running Simulation..."}
                </h3>
                <p className="text-gray-400 text-sm">
                  {mode === "compare" ? `Comparing strategies on ${symbol}` : `Fetching data and running simulation for ${symbol}`}
                </p>
              </div>
            )}

            {/* ════════════════ SINGLE MODE RESULTS ════════════════ */}
            {results && !isPending && mode === "single" && (
              <div id="backtest-report">
                {/* Performance summary */}
                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                  <div className="flex items-center justify-between mb-5">
                    <div>
                      <h3 className="text-white font-bold text-lg">Performance Summary</h3>
                      <p className={cn("text-sm font-semibold mt-0.5", isPositive ? "text-green-400" : "text-red-400")}>
                        {selectedStrategy?.name || "Quick Strategy"} · {symbol} · {timeframe}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={cn("text-3xl font-black", isPositive ? "text-green-400" : "text-red-400")}>
                        {isPositive ? "+" : ""}{results.total_return}%
                      </p>
                      <p className={cn("text-sm font-medium", isPositive ? "text-green-400" : "text-red-400")}>
                        {isPositive ? "+" : ""}₹{Math.abs(results.total_pnl).toLocaleString("en-IN")}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: "Final Capital", value: `₹${results.final_capital.toLocaleString("en-IN")}`, icon: DollarSign, color: "text-blue-400", bg: "bg-blue-500/10" },
                      { label: "Total Trades",  value: String(results.total_trades), icon: Activity, color: "text-purple-400", bg: "bg-purple-500/10" },
                      { label: "Win Rate",      value: `${results.win_rate}%`,       icon: TrendingUp, color: results.win_rate > 50 ? "text-green-400" : "text-red-400", bg: results.win_rate > 50 ? "bg-green-500/10" : "bg-red-500/10" },
                      { label: "Max Drawdown",  value: `${results.max_drawdown}%`,   icon: TrendingDown, color: "text-orange-400", bg: "bg-orange-500/10" },
                      { label: "Profit Factor", value: String(results.profit_factor > 100 ? "∞" : results.profit_factor.toFixed(2)), icon: Percent, color: "text-green-400", bg: "bg-green-500/10" },
                      { label: "Sharpe Ratio",  value: String(results.sharpe_ratio.toFixed(2)), icon: Activity, color: results.sharpe_ratio > 1 ? "text-green-400" : "text-yellow-400", bg: results.sharpe_ratio > 1 ? "bg-green-500/10" : "bg-yellow-500/10" },
                      { label: "Total Trades",  value: String(results.total_trades), icon: Zap, color: "text-blue-400", bg: "bg-blue-500/10" },
                      { label: "Return",        value: `${isPositive ? "+" : ""}${results.total_return}%`, icon: TrendingUp, color: isPositive ? "text-green-400" : "text-red-400", bg: isPositive ? "bg-green-500/10" : "bg-red-500/10" },
                    ].map((stat) => {
                      const Icon = stat.icon;
                      return (
                        <div key={stat.label} className="bg-gray-800 border border-gray-700 rounded-xl p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-gray-500 text-xs font-medium">{stat.label}</span>
                            <div className={cn("h-7 w-7 rounded-lg flex items-center justify-center", stat.bg)}>
                              <Icon className={cn("h-3.5 w-3.5", stat.color)} />
                            </div>
                          </div>
                          <p className={cn("text-lg font-black", stat.color)}>{stat.value}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Equity curve */}
                {equityData.length > 1 && (
                  <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                    <h3 className="text-white font-bold text-sm mb-4">Equity Curve</h3>
                    <svg viewBox={`0 0 ${equityData.length * 10} 100`} className="w-full h-48" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={isPositive ? "#22c55e" : "#ef4444"} stopOpacity="0.3" />
                          <stop offset="100%" stopColor={isPositive ? "#22c55e" : "#ef4444"} stopOpacity="0" />
                        </linearGradient>
                      </defs>
                      {(() => {
                        const values = equityData.map((e: any) => e.value);
                        const min = Math.min(...values);
                        const max = Math.max(...values);
                        const range = max - min || 1;
                        const points = equityData.map((e: any, i: number) =>
                          `${i * (100 / Math.max(equityData.length - 1, 1))},${100 - ((e.value - min) / range) * 80 - 10}`
                        ).join(" ");
                        return (
                          <>
                            <polygon points={`0,100 ${points} ${equityData.length * (100 / Math.max(equityData.length - 1, 1))},100`} fill="url(#eqGrad)" />
                            <polyline points={points} fill="none" stroke={isPositive ? "#22c55e" : "#ef4444"} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                          </>
                        );
                      })()}
                    </svg>
                    <div className="flex justify-between text-xs text-gray-600 mt-1">
                      <span>{new Date(equityData[0]?.date * 1000).toLocaleDateString("en-IN")}</span>
                      <span>₹{Math.min(...equityData.map((e: any) => e.value)).toLocaleString("en-IN")} — ₹{Math.max(...equityData.map((e: any) => e.value)).toLocaleString("en-IN")}</span>
                      <span>{new Date(equityData[equityData.length - 1]?.date * 1000).toLocaleDateString("en-IN")}</span>
                    </div>
                  </div>
                )}

                {/* Trades table */}
                <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
                  <div className="flex items-center justify-between p-5 border-b border-gray-800">
                    <h3 className="text-white font-bold text-sm">Trade Log ({results.trades.length})</h3>
                    <button onClick={() => setShowAllTrades(!showAllTrades)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 hover:text-white rounded-lg text-xs font-medium transition-all">
                      <Download className="h-3.5 w-3.5" /> {showAllTrades ? "Collapse" : "Show All"}
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-800">
                          {["#", "Entry", "Exit", "Side", "Qty", "Entry Price", "Exit Price", "P&L", "P&L %"].map((h) => (
                            <th key={h} className="px-4 py-3 text-left text-xs text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(showAllTrades ? results.trades : results.trades.slice(-20)).map((t: any, i: number) => (
                          <tr key={i} className={cn("border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors")}>
                            <td className="px-4 py-3 text-gray-500 text-xs">{showAllTrades ? i + 1 : results.trades.length - 20 + i + 1}</td>
                            <td className="px-4 py-3 text-gray-300 text-xs whitespace-nowrap">{t.entry_date}</td>
                            <td className="px-4 py-3 text-gray-300 text-xs whitespace-nowrap">{t.exit_date}</td>
                            <td className="px-4 py-3">
                              <span className={cn("text-xs font-bold px-2 py-0.5 rounded border",
                                t.side === "BUY" ? "bg-green-400/10 text-green-400 border-green-500/20" : "bg-red-400/10 text-red-400 border-red-500/20")}>
                                {t.side}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-gray-300 text-xs">{t.qty}</td>
                            <td className="px-4 py-3 text-gray-300 text-xs">₹{t.entry_price.toLocaleString("en-IN")}</td>
                            <td className="px-4 py-3 text-gray-300 text-xs">₹{t.exit_price.toLocaleString("en-IN")}</td>
                            <td className={cn("px-4 py-3 text-xs font-bold", getPnLColor(t.pnl))}>
                              {t.pnl >= 0 ? "+" : ""}₹{Math.abs(t.pnl).toLocaleString("en-IN")}
                            </td>
                            <td className="px-4 py-3">
                              <span className={cn("text-xs font-bold px-2 py-0.5 rounded", getPnLColor(t.pnl_pct))}>
                                {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {results.trades.length === 0 && (
                    <div className="text-center py-8 text-gray-500 text-sm">No trades generated for this strategy/symbol combination</div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-3">
                  <button onClick={handleRun}
                    className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all">
                    <RotateCcw className="h-4 w-4" /> Re-run
                  </button>
                  {selectedStrategy && (
                    <a href="/auto-trade"
                      className="flex items-center gap-2 px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-semibold transition-all">
                      <Zap className="h-4 w-4" /> Deploy to Auto Trade
                    </a>
                  )}
                  <div className="flex-1" />
                  <button onClick={() => exportSingleTradesCSV(results.trades, symbol, selectedStrategy?.name || "Quick")}
                    className="flex items-center gap-2 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white rounded-xl text-xs font-semibold transition-all">
                    <FileSpreadsheet className="h-4 w-4" /> Export CSV
                  </button>
                  <button onClick={() => exportToPDF("backtest-report", `backtest-${symbol}-${selectedStrategy?.name || "quick"}.pdf`)}
                    className="flex items-center gap-2 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white rounded-xl text-xs font-semibold transition-all">
                    <FileText className="h-4 w-4" /> Export PDF
                  </button>
                </div>
              </div>
            )}

            {/* ════════════════ COMPARE MODE RESULTS ════════════════ */}
            {compareResults && !isPending && mode === "compare" && (
              <div id="compare-report">
                {/* Legend */}
                <div className="flex items-center flex-wrap gap-3">
                  {compareResults.map((item, i) => (
                    <div key={item.label} className="flex items-center gap-1.5 text-xs">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COMPARE_COLORS[i % COMPARE_COLORS.length] }} />
                      <span className="text-gray-300 font-semibold">{item.label}</span>
                      <span className={cn("font-bold", item.result.total_return >= 0 ? "text-green-400" : "text-red-400")}>
                        ({item.result.total_return >= 0 ? "+" : ""}{item.result.total_return}%)
                      </span>
                    </div>
                  ))}
                </div>

                {/* Overlaid equity curves */}
                {comparisonChart && (
                  <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                    <h3 className="text-white font-bold text-sm mb-4">Equity Curves Comparison</h3>
                    <div className="h-56 relative">
                      <svg viewBox="0 0 1000 120" className="w-full h-full" preserveAspectRatio="none">
                        {/* Grid lines */}
                        {[0, 25, 50, 75, 100].map((pct) => (
                          <line key={pct} x1="0" y1={120 - (pct * 1.2)} x2="1000" y2={120 - (pct * 1.2)}
                            stroke="#1f2937" strokeWidth="0.5" />
                        ))}
                        {/* Y-axis labels */}
                        <text x="5" y="14" fill="#6b7280" fontSize="8">{Math.round(comparisonChart.max).toLocaleString()}</text>
                        <text x="5" y="118" fill="#6b7280" fontSize="8">{Math.round(comparisonChart.min).toLocaleString()}</text>
                        {/* Equity curves */}
                        {comparisonChart.series.map((s) => {
                          if (s.values.length < 2) return null;
                          const points = s.values.map((v, i) =>
                            `${(i / Math.max(s.values.length - 1, 1)) * 1000},${120 - ((v - comparisonChart.min) / comparisonChart.range) * 100 - 10}`
                          ).join(" ");
                          return <polyline key={s.label} points={points} fill="none" stroke={s.color} strokeWidth="2" vectorEffect="non-scaling-stroke" />;
                        })}
                      </svg>
                    </div>
                    <div className="flex justify-between text-xs text-gray-600 mt-1">
                      <span>{new Date(compareResults[0]?.result.equity_curve?.[0]?.date * 1000 || Date.now()).toLocaleDateString("en-IN")}</span>
                      <span>Overlaid equity curves</span>
                      <span>{new Date(compareResults[0]?.result.equity_curve?.[compareResults[0]?.result.equity_curve.length - 1]?.date * 1000 || Date.now()).toLocaleDateString("en-IN")}</span>
                    </div>
                  </div>
                )}

                {/* Comparison metrics table */}
                <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
                  <div className="px-5 py-4 border-b border-gray-800">
                    <h3 className="text-white font-bold text-sm">Side-by-Side Metrics</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-800">
                          <th className="px-5 py-3 text-left text-xs text-gray-500 font-semibold uppercase tracking-wider w-40">Metric</th>
                          {compareResults.map((item, i) => (
                            <th key={item.label} className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wider min-w-[120px]"
                              style={{ color: COMPARE_COLORS[i % COMPARE_COLORS.length] }}>
                              {item.label}
                            </th>
                          ))}
                          <th className="px-5 py-3 text-center text-xs text-gray-500 font-semibold uppercase tracking-wider min-w-[80px]">Best</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          { label: "Total Return", key: "total_return", fmt: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`, higher: true },
                          { label: "Total P&L", key: "total_pnl", fmt: (v: number) => `${v >= 0 ? "+" : ""}₹${Math.abs(Math.round(v)).toLocaleString("en-IN")}`, higher: true },
                          { label: "Final Capital", key: "final_capital", fmt: (v: number) => `₹${v.toLocaleString("en-IN")}`, higher: true },
                          { label: "Win Rate", key: "win_rate", fmt: (v: number) => `${v.toFixed(1)}%`, higher: true },
                          { label: "Max Drawdown", key: "max_drawdown", fmt: (v: number) => `${v.toFixed(2)}%`, higher: false },
                          { label: "Profit Factor", key: "profit_factor", fmt: (v: number) => v > 100 ? "∞" : v.toFixed(2), higher: true },
                          { label: "Sharpe Ratio", key: "sharpe_ratio", fmt: (v: number) => v.toFixed(3), higher: true },
                          { label: "Total Trades", key: "total_trades", fmt: (v: number) => String(v), higher: false },
                        ].map((metric) => {
                          const values = compareResults.map((r) => (r.result as any)[metric.key] as number);
                          const bestVal = metric.higher ? Math.max(...values) : Math.min(...values);
                          return (
                            <tr key={metric.key} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                              <td className="px-5 py-3.5 text-gray-400 text-xs font-medium">{metric.label}</td>
                              {compareResults.map((item, i) => {
                                const v = (item.result as any)[metric.key] as number;
                                const isBest = v === bestVal;
                                return (
                                  <td key={item.label} className={cn("px-5 py-3.5 text-center text-sm", isBest ? "text-white font-bold" : "text-gray-400")}>
                                    {metric.fmt(v)}
                                    {isBest && <span className="ml-1 text-[10px] text-yellow-400">★</span>}
                                  </td>
                                );
                              })}
                              <td className="px-5 py-3.5 text-center text-xs text-yellow-500 font-bold">
                                {compareResults.findIndex((r) => (r.result as any)[metric.key] === bestVal) >= 0
                                  ? compareResults[compareResults.findIndex((r) => (r.result as any)[metric.key] === bestVal)].label
                                  : "—"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Best performer summary */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {["total_return", "win_rate", "sharpe_ratio"].map((key) => {
                    const best = compareResults.reduce((a, b) =>
                      (b.result as any)[key] > (a.result as any)[key] ? b : a
                    );
                    return (
                      <div key={key} className="bg-gray-900 border border-gray-800 rounded-2xl p-5 text-center">
                        <p className="text-gray-500 text-xs font-medium uppercase tracking-wider mb-1">
                          Best {key.replace("_", " ")}
                        </p>
                        <p className="text-white font-bold text-sm">{best.label}</p>
                        <p className="text-lg font-black mt-1" style={{ color: best.result.total_return >= 0 ? "#22c55e" : "#ef4444" }}>
                          {key === "total_return" ? `${best.result.total_return >= 0 ? "+" : ""}${best.result.total_return.toFixed(2)}%` :
                           key === "win_rate" ? `${best.result.win_rate.toFixed(1)}%` :
                           best.result.sharpe_ratio.toFixed(3)}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Re-run & Export */}
                <div className="flex flex-wrap gap-3">
                  <button onClick={handleRun}
                    className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-sm font-semibold transition-all">
                    <RotateCcw className="h-4 w-4" /> Re-run Comparison
                  </button>
                  <div className="flex-1" />
                  <button onClick={() => exportCompareResultsCSV(compareResults, symbol, timeframe, period)}
                    className="flex items-center gap-2 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white rounded-xl text-xs font-semibold transition-all">
                    <FileSpreadsheet className="h-4 w-4" /> Export CSV
                  </button>
                  <button onClick={() => exportToPDF("compare-report", `backtest-compare-${symbol}.pdf`)}
                    className="flex items-center gap-2 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white rounded-xl text-xs font-semibold transition-all">
                    <FileText className="h-4 w-4" /> Export PDF
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
