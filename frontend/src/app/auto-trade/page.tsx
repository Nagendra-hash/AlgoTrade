"use client";
// Path: frontend/src/app/auto-trade/page.tsx
import { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useStrategies, useDeployStrategy } from "@/hooks/useStrategies";
import {
  useEngineStatus, useStartEngine, useStopEngine,
  useEnginePositions, useEngineActivity, useScreenStocks,
  useUpdateRiskConfig, useRiskConfig, useQuickStart,
} from "@/hooks/useAutoTrade";
import { cn, getPnLColor } from "@/lib/utils";
import {
  Zap, Play, Square, TrendingUp, TrendingDown,
  AlertCircle, CheckCircle2, RefreshCw, Search,
  Activity, Shield, BarChart2, Loader2, Settings2,
  Target, Crosshair, XCircle, Rocket, Sparkles,
} from "lucide-react";

const RISK_LEVELS = [
  { id: "conservative", label: "Conservative", desc: "Max 2% per trade, 10% daily loss limit", color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/20", config: { max_position_size_pct: 2, max_daily_loss_pct: 10, max_open_positions: 3, max_trades_per_day: 10 } },
  { id: "moderate",     label: "Moderate",     desc: "Max 5% per trade, 20% daily loss limit", color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20", config: { max_position_size_pct: 5, max_daily_loss_pct: 20, max_open_positions: 5, max_trades_per_day: 20 } },
  { id: "aggressive",   label: "Aggressive",   desc: "Max 10% per trade, 30% daily loss limit", color: "text-red-400",  bg: "bg-red-500/10",   border: "border-red-500/20", config: { max_position_size_pct: 10, max_daily_loss_pct: 30, max_open_positions: 8, max_trades_per_day: 40 } },
];

const QUICK_PRESETS: { id: "trend_following"|"mean_reversion"|"momentum"|"breakout"|"scalping"|"swing"; label: string; desc: string; emoji: string }[] = [
  { id: "trend_following", label: "Trend Following", desc: "EMA crossover + volume confirmation", emoji: "📈" },
  { id: "mean_reversion",  label: "Mean Reversion",  desc: "Bollinger Bands + RSI oversold",     emoji: "⚖️" },
  { id: "momentum",        label: "Momentum",        desc: "RSI 50→70 momentum surge",           emoji: "🚀" },
  { id: "breakout",        label: "Breakout",        desc: "20-day high + volume spike",          emoji: "💥" },
  { id: "swing",           label: "Swing Trade",     desc: "MACD + ADX trend strength",           emoji: "🌊" },
];

export default function AutoTradePage() {
  const [risk, setRisk]           = useState("moderate");
  const [capital, setCapital]     = useState(100000);
  const [mode, setMode]           = useState<"paper"|"live">("paper");
  const [screenType, setScreenType] = useState("momentum");
  const [showQuickStart, setShowQuickStart] = useState(false);
  const [quickPreset, setQuickPreset] = useState<typeof QUICK_PRESETS[number]["id"]>("trend_following");
  const [quickResult, setQuickResult] = useState<{name: string; symbols: string[]; indicators: string[]} | null>(null);
  const quickStart = useQuickStart();

  // Engine hooks
  const { data: status, isLoading: statusLoading } = useEngineStatus();
  const { data: positionsData }  = useEnginePositions();
  const { data: activityData }   = useEngineActivity();
  const { data: riskData }       = useRiskConfig();
  const startEngine = useStartEngine();
  const stopEngine  = useStopEngine();
  const updateRisk  = useUpdateRiskConfig();
  const screenStocks = useScreenStocks();

  // Strategy hooks
  const { data: strategies = [], isLoading: stratsLoading } = useStrategies();
  const deploy = useDeployStrategy();

  const activeStrategies = strategies.filter((s) => s.is_paper_active || s.is_live_active);
  const positions = positionsData?.positions ?? [];
  const activity  = activityData?.activity ?? [];
  const todayPnl  = status?.today_pnl ?? 0;
  const winRate   = status?.win_rate ?? 0;

  const isRunning = status?.is_running ?? false;

  const handleStart = () => startEngine.mutate(mode);
  const handleStop  = () => stopEngine.mutate();
  const handleRiskChange = (level: typeof RISK_LEVELS[number]) => {
    setRisk(level.id);
    updateRisk.mutate({ ...level.config, trading_capital: capital });
  };
  const handleScreen = () => {
    screenStocks.mutate({ strategy_type: screenType, limit: 10 });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white flex items-center gap-2">
              <Zap className="h-6 w-6 text-yellow-400" /> Auto Trading
            </h2>
            <p className="text-gray-400 text-sm mt-0.5">
              {isRunning ? "Engine is actively monitoring and trading" : "Deploy AI strategies to trade automatically"}
            </p>
          </div>

          {/* Master switch */}
          <div className="flex items-center gap-3">
            <button
              data-testid="quick-start-btn"
              onClick={() => { setQuickResult(null); setShowQuickStart(true); }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white shadow-lg shadow-purple-500/20 transition-all"
              title="Generate, deploy & launch a strategy in one tap"
            >
              <Rocket className="h-4 w-4" /> Quick Start
            </button>
            <div className="flex gap-1 bg-gray-800 rounded-xl p-1 border border-gray-700">
              {(["paper","live"] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)}
                  className={cn("px-4 py-2 rounded-lg text-xs font-bold capitalize transition-all",
                    mode === m
                      ? m === "live" ? "bg-orange-600 text-white" : "bg-blue-600 text-white"
                      : "text-gray-400 hover:text-white")}>
                  {m === "live" ? "🔴 Live" : "📋 Paper"}
                </button>
              ))}
            </div>

            <button onClick={isRunning ? handleStop : handleStart}
              disabled={startEngine.isPending || stopEngine.isPending}
              className={cn("flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm transition-all disabled:opacity-50",
                isRunning
                  ? "bg-red-600 hover:bg-red-700 text-white"
                  : "bg-green-600 hover:bg-green-700 text-white shadow-lg shadow-green-500/20")}>
              {(startEngine.isPending || stopEngine.isPending)
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : isRunning
                  ? <><Square className="h-4 w-4" /> Stop Engine</>
                  : <><Play  className="h-4 w-4" /> Start Engine</>}
            </button>
          </div>
        </div>

        {/* Live warning */}
        {mode === "live" && (
          <div className="flex items-start gap-3 bg-orange-500/10 border border-orange-500/30 rounded-xl p-4">
            <AlertCircle className="h-5 w-5 text-orange-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-orange-400 font-bold text-sm">Live Trading Mode</p>
              <p className="text-orange-300/70 text-xs mt-0.5">
                Real money will be used. Connect your broker in Settings before enabling. Paper mode is recommended for testing.
              </p>
            </div>
          </div>
        )}

        {/* Engine status cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            { label: "Engine Status",      value: isRunning ? "Running" : "Stopped",                    icon: Activity,  color: isRunning ? "text-green-400" : "text-gray-400", bg: isRunning ? "bg-green-500/10" : "bg-gray-800" },
            { label: "Active Strategies",  value: String(status?.active_strategies ?? activeStrategies.length), icon: Zap,       color: "text-blue-400",   bg: "bg-blue-500/10"   },
            { label: "Open Positions",     value: String(status?.open_positions ?? positions.length),   icon: Target,    color: "text-cyan-400",   bg: "bg-cyan-500/10"   },
            { label: "Today's P&L",        value: `${todayPnl >= 0 ? "+" : ""}₹${todayPnl.toLocaleString("en-IN")}`, icon: TrendingUp, color: getPnLColor(todayPnl), bg: todayPnl >= 0 ? "bg-green-500/10" : "bg-red-500/10" },
            { label: "Win Rate",           value: `${winRate}%`,                                       icon: BarChart2, color: "text-purple-400", bg: "bg-purple-500/10" },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-gray-400 text-xs font-medium">{stat.label}</span>
                  <div className={cn("h-8 w-8 rounded-lg flex items-center justify-center", stat.bg)}>
                    <Icon className={cn("h-4 w-4", stat.color)} />
                  </div>
                </div>
                <p className={cn("text-2xl font-black", stat.color)}>{stat.value}</p>
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Left: Config + Stock Screener */}
          <div className="space-y-4">
            {/* Risk level */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <Shield className="h-4 w-4 text-blue-400" />
                <h3 className="text-white font-bold">Risk Management</h3>
              </div>
              <div className="space-y-2">
                {RISK_LEVELS.map((r) => (
                  <button key={r.id} onClick={() => handleRiskChange(r)}
                    className={cn("w-full text-left p-3 rounded-xl border transition-all",
                      risk === r.id ? `${r.bg} ${r.border}` : "border-gray-700 bg-gray-800 hover:border-gray-600")}>
                    <p className={cn("font-bold text-sm", risk === r.id ? r.color : "text-white")}>{r.label}</p>
                    <p className="text-gray-500 text-xs mt-0.5">{r.desc}</p>
                  </button>
                ))}
              </div>
              {/* Current risk config display */}
              {riskData?.risk_config && (
                <div className="mt-3 pt-3 border-t border-gray-800 space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Max Position</span>
                    <span className="text-gray-300 font-mono">{riskData.risk_config.max_position_size_pct}%</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Daily Loss Limit</span>
                    <span className="text-gray-300 font-mono">{riskData.risk_config.max_daily_loss_pct}%</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Max Positions</span>
                    <span className="text-gray-300 font-mono">{riskData.risk_config.max_open_positions}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Trailing Stop</span>
                    <span className="text-gray-300 font-mono">{riskData.risk_config.trailing_stop_pct}%</span>
                  </div>
                </div>
              )}
            </div>

            {/* Capital allocation */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <h3 className="text-white font-bold mb-4">Capital Settings</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">
                    Trading Capital (₹)
                  </label>
                  <input
                    type="number"
                    value={capital}
                    onChange={(e) => setCapital(Number(e.target.value))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            </div>

            {/* Stock Screener */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <Crosshair className="h-4 w-4 text-purple-400" />
                <h3 className="text-white font-bold">Stock Screener</h3>
              </div>
              <div className="space-y-3">
                <div className="flex gap-2">
                  {["momentum", "trend_following", "mean_reversion"].map((t) => (
                    <button key={t} onClick={() => setScreenType(t)}
                      className={cn("flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-all",
                        screenType === t ? "bg-purple-600/20 border-purple-500/40 text-purple-400" : "border-gray-700 text-gray-500 hover:text-gray-300")}>
                      {t.replace("_", " ")}
                    </button>
                  ))}
                </div>
                <button onClick={handleScreen} disabled={screenStocks.isPending}
                  className="w-full flex items-center justify-center gap-2 py-2 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-400 rounded-xl text-xs font-semibold transition-all disabled:opacity-50">
                  {screenStocks.isPending
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <Search className="h-3.5 w-3.5" />}
                  Screen Stocks
                </button>
                {/* Screen results */}
                {screenStocks.data?.candidates && (
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {screenStocks.data.candidates.map((c: { symbol: string; ltp: number; change_pct: number; composite_score: number; rsi: number | null; trend_up: boolean }) => (
                      <div key={c.symbol} className="flex items-center justify-between p-2 bg-gray-800 rounded-lg">
                        <div>
                          <p className="text-white text-xs font-bold">{c.symbol}</p>
                          <p className="text-gray-500 text-[10px]">₹{c.ltp.toLocaleString("en-IN")} · {c.change_pct >= 0 ? "+" : ""}{c.change_pct}%</p>
                        </div>
                        <div className="text-right">
                          <p className={cn("text-xs font-bold", c.trend_up ? "text-green-400" : "text-red-400")}>
                            {c.composite_score.toFixed(0)}
                          </p>
                          {c.rsi && <p className="text-[10px] text-gray-500">RSI {c.rsi.toFixed(0)}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Middle: Active strategies + Open positions */}
          <div className="space-y-4">
            {/* Active strategies */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between p-5 border-b border-gray-800">
                <h3 className="text-white font-bold">Active Strategies</h3>
                <a href="/strategy" className="text-blue-400 text-xs hover:underline">+ Add Strategy</a>
              </div>
              <div className="p-4 max-h-64 overflow-y-auto">
                {stratsLoading ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 text-blue-400 animate-spin" />
                  </div>
                ) : strategies.length === 0 ? (
                  <div className="text-center py-10">
                    <Zap className="h-10 w-10 text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-400 font-medium text-sm">No strategies yet</p>
                    <a href="/strategy"
                      className="inline-flex items-center gap-2 px-4 py-2 mt-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold transition-all">
                      <Zap className="h-3.5 w-3.5" /> Build Strategy
                    </a>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {strategies.map((s) => (
                      <div key={s.id} className={cn(
                        "p-3.5 rounded-xl border transition-all",
                        s.is_paper_active ? "border-green-500/30 bg-green-500/5" : "border-gray-700 bg-gray-800"
                      )}>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="min-w-0">
                            <p className="text-white font-semibold text-sm truncate">{s.name}</p>
                            <p className="text-gray-500 text-xs capitalize">{s.strategy_type?.replace("_"," ")}</p>
                          </div>
                          <span className={cn("text-[10px] px-2 py-0.5 rounded-full border font-bold flex-shrink-0",
                            s.is_paper_active
                              ? "bg-green-500/10 text-green-400 border-green-500/20"
                              : "bg-gray-700 text-gray-400 border-gray-600")}>
                            {s.is_paper_active ? "● Active" : s.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          {(s.symbols ?? []).slice(0, 3).map((sym) => (
                            <span key={sym} className="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">{sym}</span>
                          ))}
                          <span className="text-[10px] text-gray-600">{s.timeframe}</span>
                        </div>
                        {!s.is_paper_active && (
                          <button
                            onClick={() => deploy.mutate({ id: s.id, mode: "paper" })}
                            disabled={deploy.isPending}
                            className="mt-2 w-full flex items-center justify-center gap-1.5 py-1.5 bg-green-600/20 hover:bg-green-600/30 border border-green-500/30 text-green-400 rounded-lg text-xs font-semibold transition-all">
                            <Play className="h-3 w-3" /> Deploy to Paper
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Open positions */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between p-5 border-b border-gray-800">
                <h3 className="text-white font-bold flex items-center gap-2">
                  <Target className="h-4 w-4 text-cyan-400" /> Open Positions
                </h3>
                <span className="text-xs text-gray-500">{positions.length} active</span>
              </div>
              <div className="divide-y divide-gray-800">
                {positions.length === 0 ? (
                  <div className="p-8 text-center">
                    <Target className="h-8 w-8 text-gray-700 mx-auto mb-2" />
                    <p className="text-gray-500 text-xs">No open positions</p>
                    <p className="text-gray-600 text-[10px] mt-1">Start the engine to begin trading</p>
                  </div>
                ) : (
                  positions.map((p) => (
                    <div key={p.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/40 transition-colors">
                      <div className={cn("h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0",
                        p.side === "BUY" ? "bg-green-500/10" : "bg-red-500/10")}>
                        <TrendingUp className="h-3.5 w-3.5 text-green-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-bold text-xs">{p.symbol}</span>
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded border bg-green-400/10 text-green-400 border-green-500/20">{p.side}</span>
                        </div>
                        <p className="text-gray-500 text-xs">
                          {p.quantity} @ ₹{p.entry_price.toLocaleString("en-IN")} → ₹{p.current_price.toLocaleString("en-IN")}
                        </p>
                        <div className="flex gap-3 mt-1">
                          <span className="text-[10px] text-red-400">SL ₹{p.stop_loss.toLocaleString("en-IN")}</span>
                          <span className="text-[10px] text-green-400">TP ₹{p.take_profit.toLocaleString("en-IN")}</span>
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className={cn("text-xs font-bold", getPnLColor(p.pnl))}>
                          {p.pnl >= 0 ? "+" : ""}₹{p.pnl.toLocaleString("en-IN")}
                        </p>
                        <p className={cn("text-[10px]", getPnLColor(p.pnl_pct))}>
                          {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct.toFixed(2)}%
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right: Activity log */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-gray-800">
              <h3 className="text-white font-bold">Today&apos;s Activity</h3>
              <span className="text-xs text-gray-500">{status?.today_trades ?? 0} trades</span>
            </div>
            <div className="divide-y divide-gray-800 max-h-[600px] overflow-y-auto">
              {activity.length === 0 ? (
                <div className="p-8 text-center">
                  <Activity className="h-8 w-8 text-gray-700 mx-auto mb-2" />
                  <p className="text-gray-500 text-xs">No trades yet today</p>
                  <p className="text-gray-600 text-[10px] mt-1">Deploy a strategy and start the engine</p>
                </div>
              ) : (
                activity.map((a, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/40 transition-colors">
                    <div className={cn("h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0",
                      a.action === "BUY" ? "bg-green-500/10" : "bg-red-500/10")}>
                      {a.action === "BUY"
                        ? <TrendingUp  className="h-3.5 w-3.5 text-green-400" />
                        : <TrendingDown className="h-3.5 w-3.5 text-red-400"  />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-bold text-xs">{a.symbol}</span>
                        <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded border",
                          a.action === "BUY"
                            ? "bg-green-400/10 text-green-400 border-green-500/20"
                            : "bg-red-400/10 text-red-400 border-red-500/20")}>
                          {a.action}
                        </span>
                        {a.mode === "paper" && (
                          <span className="text-[10px] text-gray-600 bg-gray-800 px-1 py-0.5 rounded">PAPER</span>
                        )}
                      </div>
                      <p className="text-gray-500 text-xs">{a.qty} qty · ₹{a.price.toLocaleString("en-IN")} · {a.time}</p>
                      {a.reason && <p className="text-gray-600 text-[10px]">{a.reason}</p>}
                    </div>
                    <div className="text-right flex-shrink-0">
                      {a.pnl !== undefined && (
                        <p className={cn("text-xs font-bold", getPnLColor(a.pnl))}>
                          {a.pnl >= 0 ? "+" : ""}₹{a.pnl.toLocaleString("en-IN")}
                        </p>
                      )}
                      <div className="flex items-center gap-1 justify-end mt-0.5">
                        <CheckCircle2 className="h-3 w-3 text-green-400" />
                        <span className="text-[10px] text-green-400">Done</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="p-4 border-t border-gray-800">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">Total P&L today</span>
                <span className={cn("font-black text-lg", getPnLColor(todayPnl))}>
                  {todayPnl >= 0 ? "+" : ""}₹{todayPnl.toLocaleString("en-IN")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Start Modal */}
      {showQuickStart && (
        <div
          data-testid="quick-start-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => !quickStart.isPending && setShowQuickStart(false)}
        >
          <div
            className="w-full max-w-xl bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-5 border-b border-gray-800 flex items-center justify-between bg-gradient-to-r from-purple-600/10 to-pink-600/10">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <Rocket className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h3 className="text-white font-black">Quick Start Auto-Trader</h3>
                  <p className="text-gray-400 text-xs">Generate, deploy & launch in one tap</p>
                </div>
              </div>
              {!quickStart.isPending && (
                <button onClick={() => setShowQuickStart(false)} className="text-gray-500 hover:text-white">
                  <XCircle className="h-5 w-5" />
                </button>
              )}
            </div>

            {!quickResult ? (
              <>
                <div className="p-6 space-y-5">
                  <div>
                    <label className="text-gray-400 text-xs font-semibold uppercase tracking-wide block mb-2">Choose a strategy style</label>
                    <div className="grid grid-cols-1 gap-2">
                      {QUICK_PRESETS.map((p) => (
                        <button
                          key={p.id}
                          data-testid={`quick-preset-${p.id}`}
                          onClick={() => setQuickPreset(p.id)}
                          className={cn(
                            "flex items-center gap-3 p-3 rounded-xl border text-left transition-all",
                            quickPreset === p.id
                              ? "bg-purple-500/10 border-purple-500/40"
                              : "bg-gray-800/50 border-gray-700 hover:border-gray-600",
                          )}
                        >
                          <span className="text-2xl">{p.emoji}</span>
                          <div className="flex-1">
                            <p className="text-white font-bold text-sm">{p.label}</p>
                            <p className="text-gray-400 text-xs">{p.desc}</p>
                          </div>
                          {quickPreset === p.id && <CheckCircle2 className="h-5 w-5 text-purple-400" />}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-gray-400 text-xs font-semibold uppercase tracking-wide block mb-2">Mode</label>
                      <div className="flex gap-1 bg-gray-800 rounded-xl p-1 border border-gray-700">
                        {(["paper", "live"] as const).map((m) => (
                          <button
                            key={m}
                            data-testid={`quick-mode-${m}`}
                            onClick={() => setMode(m)}
                            className={cn(
                              "flex-1 py-2 rounded-lg text-xs font-bold capitalize transition-all",
                              mode === m ? (m === "live" ? "bg-orange-600 text-white" : "bg-blue-600 text-white") : "text-gray-400",
                            )}
                          >
                            {m === "live" ? "🔴 Live" : "📋 Paper"}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="text-gray-400 text-xs font-semibold uppercase tracking-wide block mb-2">Capital (₹)</label>
                      <input
                        data-testid="quick-capital-input"
                        type="number"
                        value={capital}
                        onChange={(e) => setCapital(Number(e.target.value))}
                        min={1000}
                        step={1000}
                        className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20"
                      />
                    </div>
                  </div>

                  {mode === "live" && (
                    <div className="flex items-start gap-2 bg-orange-500/10 border border-orange-500/30 rounded-xl p-3">
                      <AlertCircle className="h-4 w-4 text-orange-400 flex-shrink-0 mt-0.5" />
                      <p className="text-orange-300/90 text-xs">
                        Live mode trades real money. Make sure your broker is connected in Settings.
                      </p>
                    </div>
                  )}
                </div>

                <div className="px-6 py-4 bg-gray-950/50 border-t border-gray-800 flex justify-end gap-2">
                  <button
                    onClick={() => setShowQuickStart(false)}
                    disabled={quickStart.isPending}
                    className="px-4 py-2 rounded-xl text-sm font-semibold text-gray-300 hover:text-white disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    data-testid="quick-start-launch-btn"
                    disabled={quickStart.isPending}
                    onClick={() =>
                      quickStart.mutate(
                        {
                          strategy_type: quickPreset,
                          mode,
                          trading_capital: capital,
                          max_position_size_pct: 10,
                        },
                        {
                          onSuccess: (res) => setQuickResult(res.strategy),
                        },
                      )
                    }
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white shadow-lg shadow-purple-500/20 disabled:opacity-50"
                  >
                    {quickStart.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" /> Generating strategy...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" /> Launch Auto-Trader
                      </>
                    )}
                  </button>
                </div>
              </>
            ) : (
              <div className="p-6 space-y-4">
                <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                  <CheckCircle2 className="h-6 w-6 text-green-400 flex-shrink-0" />
                  <div>
                    <p className="text-green-400 font-bold text-sm">Auto-trader is live!</p>
                    <p className="text-green-300/70 text-xs">{quickStart.data?.message}</p>
                  </div>
                </div>
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-xs">Strategy</span>
                    <span className="text-white text-sm font-semibold" data-testid="quick-result-name">{quickResult.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-xs">Symbols</span>
                    <span className="text-white text-sm">{quickResult.symbols.join(", ")}</span>
                  </div>
                  <div className="flex items-start justify-between gap-3">
                    <span className="text-gray-400 text-xs">Indicators</span>
                    <span className="text-white text-sm text-right">{quickResult.indicators.join(", ")}</span>
                  </div>
                </div>
                <button
                  data-testid="quick-result-close-btn"
                  onClick={() => { setShowQuickStart(false); setQuickResult(null); }}
                  className="w-full py-2.5 rounded-xl text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white"
                >
                  View on Dashboard
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
