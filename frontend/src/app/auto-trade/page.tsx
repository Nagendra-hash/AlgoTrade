"use client";
// Path: frontend/src/app/auto-trade/page.tsx
// Auto-Trade Dashboard — Start/Stop, settings, live positions, decision panel.
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Zap, Play, Square, Activity, TrendingUp, Briefcase, AlertTriangle,
  Bot, Settings2, RefreshCw, IndianRupee, Target, Plug, ShieldAlert,
  Shield, Newspaper, Power, RotateCcw, Check, Wifi, WifiOff,
} from "lucide-react";
import Link from "next/link";

interface EngineStatus {
  is_running: boolean;
  mode: "paper" | "live";
  active_strategies: number;
  open_positions: number;
  today_trades: number;
  today_pnl: number;
  win_rate: number;
  risk_config: {
    trading_capital?: number;
    max_daily_loss_pct?: number;
    max_position_size_pct?: number;
    max_open_positions?: number;
    max_trades_per_day?: number;
    trailing_stop_enabled?: boolean;
    trailing_stop_pct?: number;
  };
  risk_state?: {
    circuit_breaker_active: boolean;
    circuit_breaker_reason?: string | null;
    circuit_breaker_tripped_at?: string | null;
    kill_switch_armed: boolean;
    kill_switch_reason?: string | null;
    broker_last_error?: string | null;
    broker_failure_count: number;
    broker_last_recovery_at?: string | null;
    last_risk_check_at?: string | null;
    daily_loss_used_pct: number;
    trades_used_pct: number;
    open_pos_used_pct: number;
  };
}

interface Position {
  id: string; symbol: string; exchange: string; side: string;
  entry_price: number; quantity: number; current_price: number;
  stop_loss: number; take_profit: number; pnl: number; pnl_pct: number;
  entry_time: string; status: string; strategy_id: string;
}

interface ActivityRow {
  time: string; symbol: string; action: string; qty: number; price: number;
  pnl?: number; pnl_pct?: number; reason?: string; status: string;
  mode: string; strategy?: string; stop_loss?: number; take_profit?: number;
}

export default function AutoTradePage() {
  const qc = useQueryClient();
  const [showSettings, setShowSettings] = useState(false);

  const { data: status, refetch } = useQuery<EngineStatus>({
    queryKey: ["auto-trade-status"],
    queryFn: () => api.get("/auto-trade/status").then((r) => r.data),
    refetchInterval: 5_000,
  });
  const { data: positionsResp } = useQuery<{ positions: Position[] }>({
    queryKey: ["auto-trade-positions"],
    queryFn: () => api.get("/auto-trade/positions").then((r) => r.data),
    refetchInterval: 5_000,
  });
  const { data: activityResp } = useQuery<{ activity: ActivityRow[] }>({
    queryKey: ["auto-trade-activity"],
    queryFn: () => api.get("/auto-trade/activity").then((r) => r.data),
    refetchInterval: 10_000,
  });
  const { data: brokerResp } = useQuery<any[]>({
    queryKey: ["broker-status"],
    queryFn: () => api.get("/brokers/status").then((r) => r.data),
    refetchInterval: 30_000,
  });
  const { data: modelsResp } = useQuery<any[]>({
    queryKey: ["ai-models"],
    queryFn: () => api.get("/ai-models").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const startMut = useMutation({
    mutationFn: (mode: "paper" | "live") => api.post("/auto-trade/start", { mode }).then((r) => r.data),
    onSuccess: () => { refetch(); qc.invalidateQueries({ queryKey: ["auto-trade-status"] }); },
  });
  const stopMut = useMutation({
    mutationFn: () => api.post("/auto-trade/stop").then((r) => r.data),
    onSuccess: () => { refetch(); qc.invalidateQueries({ queryKey: ["auto-trade-status"] }); },
  });

  const [aiBrainSymbols, setAiBrainSymbols] = useState("RELIANCE,INFY,TCS,HDFCBANK,ICICIBANK");
  const [aiBrainFlash, setAiBrainFlash] = useState<string | null>(null);
  const aiBrainMut = useMutation({
    mutationFn: () => api.post("/auto-trade/ai-brain/deploy", {
      symbols: aiBrainSymbols.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
      timeframe: "1d", mode: "paper", auto_start: true,
    }).then((r) => r.data),
    onSuccess: (d: any) => {
      setAiBrainFlash(`🧠 AI Brain deployed on ${d.strategy.symbols.length} symbols. First decision within 30s.`);
      setTimeout(() => setAiBrainFlash(null), 6000);
      qc.invalidateQueries({ queryKey: ["auto-trade-status"] });
    },
    onError: () => setAiBrainFlash("Deploy failed — try again."),
  });

  const connectedBrokers = (brokerResp ?? []).filter((b: any) => b.is_connected);
  const activeModels = (modelsResp ?? []).filter((m: any) => m.is_active);
  const positions = positionsResp?.positions ?? [];
  const activity = activityResp?.activity ?? [];

  const canStart = connectedBrokers.length > 0;

  return (
    <DashboardLayout>
      <div className="space-y-5" data-testid="auto-trade-root">
        {/* Header */}
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-violet-500/10 border border-violet-500/30 rounded-full text-violet-300 text-[11px] font-bold tracking-widest uppercase mb-2">
              <Zap className="h-3 w-3" /> Auto-Pilot
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white">Auto Trade Engine</h1>
            <p className="text-gray-500 text-sm mt-1">Connect broker → connect AI → press Start. Everything else is automatic.</p>
          </div>

          <div className="flex items-center gap-2">
            <button data-testid="auto-trade-settings-btn" onClick={() => setShowSettings((v) => !v)}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-gray-900 border border-gray-800 hover:border-violet-500/40 text-white rounded-xl text-sm font-semibold transition-all">
              <Settings2 className="h-4 w-4" /> Settings
            </button>
            <button data-testid="auto-trade-refresh-btn" onClick={() => refetch()}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-gray-900 border border-gray-800 hover:border-violet-500/40 text-white rounded-xl text-sm font-semibold transition-all">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Pre-flight checklist + Start/Stop */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-5" data-testid="auto-trade-control">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Checkpoint
              testid="check-broker"
              ok={connectedBrokers.length > 0}
              label="Broker"
              detail={connectedBrokers.length > 0
                ? `${connectedBrokers[0].broker.replace("_", " ")} · ${connectedBrokers[0].client_id || connectedBrokers[0].login_id || ""}`
                : "Not connected"}
              link={{ href: "/broker-settings", text: "Connect broker" }}
              icon={Plug}
            />
            <Checkpoint
              testid="check-ai"
              ok={activeModels.length > 0}
              label="AI Brain"
              detail={activeModels.length > 0
                ? `${activeModels[0].provider} · ${activeModels[0].model}`
                : "Using rule-based engine"}
              link={{ href: "/ai-models", text: "Connect AI" }}
              icon={Bot}
              softOk={true}
            />
            <Checkpoint
              testid="check-engine"
              ok={!!status?.is_running}
              label="Engine"
              detail={status?.is_running ? `Running · ${status.mode} mode` : "Stopped"}
              icon={Activity}
            />
          </div>

          <div className="mt-5 flex items-center justify-between gap-4 pt-5 border-t border-gray-800">
            <div className="text-xs text-gray-500 max-w-md">
              {!canStart && (
                <span className="flex items-center gap-2 text-amber-300">
                  <ShieldAlert className="h-4 w-4" /> Connect a broker before starting the engine.
                </span>
              )}
              {canStart && !status?.is_running && (
                <span>Engine is ready. Click <strong className="text-white">Start (Paper)</strong> to begin with simulated orders, or <strong className="text-white">Start (Live)</strong> for real trades.</span>
              )}
              {status?.is_running && (
                <span className="flex items-center gap-2 text-emerald-300">
                  <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span></span>
                  Engine running — monitoring {status.active_strategies} strategies
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              {!status?.is_running ? (
                <>
                  <button data-testid="auto-trade-start-paper" disabled={!canStart || startMut.isPending}
                    onClick={() => startMut.mutate("paper")}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:bg-gray-800 disabled:text-gray-600 text-gray-950 rounded-xl text-sm font-black tracking-wider uppercase transition-all">
                    <Play className="h-4 w-4" /> Start (Paper)
                  </button>
                  <button data-testid="auto-trade-start-live" disabled={!canStart || startMut.isPending}
                    onClick={() => { if (confirm("⚠️  Start LIVE trading? Real money orders will be placed via your broker.")) startMut.mutate("live"); }}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-violet-500 hover:bg-violet-400 disabled:bg-gray-800 disabled:text-gray-600 text-white rounded-xl text-sm font-black tracking-wider uppercase transition-all">
                    <Zap className="h-4 w-4" /> Start (Live)
                  </button>
                </>
              ) : (
                <button data-testid="auto-trade-stop" disabled={stopMut.isPending} onClick={() => stopMut.mutate()}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-400 text-white rounded-xl text-sm font-black tracking-wider uppercase transition-all">
                  <Square className="h-4 w-4" /> Stop Engine
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Risk settings panel */}
        {showSettings && status && <RiskSettings status={status} onClose={() => setShowSettings(false)} />}

        {/* AI Brain quick-deploy */}
        <div className="bg-gradient-to-br from-violet-500/10 via-violet-500/5 to-transparent border border-violet-500/30 rounded-2xl p-5" data-testid="ai-brain-panel">          <div className="flex items-start gap-4 flex-wrap">
            <div className="h-12 w-12 rounded-xl bg-violet-500/20 flex items-center justify-center shrink-0">
              <Bot className="h-6 w-6 text-violet-300" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                AI Brain Mode <span className="text-[10px] px-2 py-0.5 bg-violet-500/20 text-violet-300 rounded-full font-bold tracking-wider">PHASE 3</span>
              </h2>
              <p className="text-gray-400 text-xs mt-1">
                Let the LLM evaluate technicals + sentiment + news for each symbol and decide entry / SL / TP / qty automatically.
                Hard caps: 5% SL · 15% TP · 25% qty. Falls back to rule-based if AI quota is exhausted.
              </p>
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <input
                  data-testid="ai-brain-symbols-input"
                  value={aiBrainSymbols}
                  onChange={(e) => setAiBrainSymbols(e.target.value)}
                  placeholder="RELIANCE, INFY, TCS"
                  className="flex-1 min-w-[260px] px-3 py-2 bg-gray-950 border border-gray-800 focus:border-violet-500/50 rounded-lg text-sm text-white tabular-nums outline-none"
                />
                <button
                  data-testid="ai-brain-deploy-btn"
                  disabled={aiBrainMut.isPending || !aiBrainSymbols.trim()}
                  onClick={() => aiBrainMut.mutate()}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-violet-500 hover:bg-violet-400 disabled:bg-gray-800 disabled:text-gray-600 text-white rounded-lg text-sm font-bold transition-all">
                  <Bot className="h-4 w-4" /> {aiBrainMut.isPending ? "Deploying…" : "Deploy AI Brain"}
                </button>
              </div>
              {aiBrainFlash && (
                <p data-testid="ai-brain-flash" className="text-xs text-violet-300 mt-2">{aiBrainFlash}</p>
              )}
            </div>
          </div>
        </div>

        {/* Risk Hardening panel */}
        {status && <RiskHardeningPanel status={status} />}

        {/* News-Driven Candidates */}
        <NewsCandidatesPanel />

        {/* Stat strip */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <Stat testid="stat-status" label="Engine"     value={status?.is_running ? "RUNNING" : "STOPPED"} color={status?.is_running ? "text-emerald-300" : "text-gray-400"} />
          <Stat testid="stat-mode"   label="Mode"       value={status?.mode?.toUpperCase() ?? "—"}        color={status?.mode === "live" ? "text-violet-300" : "text-sky-300"} />
          <Stat testid="stat-strats" label="Strategies" value={String(status?.active_strategies ?? 0)} />
          <Stat testid="stat-open"   label="Open Pos."  value={String(status?.open_positions ?? 0)} />
          <Stat testid="stat-pnl"    label="Today P&L"  value={`${(status?.today_pnl ?? 0) >= 0 ? "+" : "-"}₹${Math.abs(status?.today_pnl ?? 0).toLocaleString("en-IN")}`} color={(status?.today_pnl ?? 0) >= 0 ? "text-emerald-300" : "text-red-300"} />
          <Stat testid="stat-winrate" label="Win Rate"  value={`${status?.win_rate ?? 0}%`} />
        </div>

        {/* Positions table (engine-managed) */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white flex items-center gap-2"><Briefcase className="h-4 w-4 text-violet-400" /> Engine Positions</h2>
            <span className="text-xs text-gray-500">{positions.length} open · auto-refresh 5s</span>
          </div>
          <table className="w-full text-sm" data-testid="auto-trade-positions-table">
            <thead className="bg-gray-950 text-[11px] uppercase tracking-wider text-gray-500">
              <tr>
                <th className="text-left px-4 py-3">Symbol</th>
                <th>Side</th><th>Qty</th><th>Entry</th><th>LTP</th><th>SL</th><th>TP</th><th>P&L</th><th>%</th><th>Strategy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {positions.length === 0 && (
                <tr><td colSpan={10} className="text-center text-gray-500 py-12" data-testid="positions-empty">
                  No engine positions. {status?.is_running ? "Waiting for AI signals…" : "Start the engine to begin."}
                </td></tr>
              )}
              {positions.map((p) => (
                <tr key={p.id} className="hover:bg-gray-800/30" data-testid={`engine-pos-${p.symbol}`}>
                  <td className="px-4 py-3 font-bold text-white">{p.symbol}<span className="text-gray-600 text-xs ml-2">{p.exchange}</span></td>
                  <td className={cn("text-center font-bold", p.side === "BUY" ? "text-emerald-400" : "text-red-400")}>{p.side}</td>
                  <td className="text-center text-gray-300 tabular-nums">{p.quantity}</td>
                  <td className="text-center text-gray-300 tabular-nums">₹{p.entry_price?.toFixed(2)}</td>
                  <td className="text-center text-white tabular-nums">₹{p.current_price?.toFixed(2)}</td>
                  <td className="text-center text-red-400/80 tabular-nums text-xs">₹{p.stop_loss?.toFixed(2)}</td>
                  <td className="text-center text-emerald-400/80 tabular-nums text-xs">₹{p.take_profit?.toFixed(2)}</td>
                  <td className={cn("text-center tabular-nums font-semibold", (p.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {(p.pnl ?? 0) >= 0 ? "+" : "-"}₹{Math.abs(p.pnl ?? 0).toLocaleString("en-IN")}
                  </td>
                  <td className={cn("text-center tabular-nums font-semibold", (p.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {(p.pnl_pct ?? 0).toFixed(2)}%
                  </td>
                  <td className="text-center text-gray-500 text-xs font-mono">{p.strategy_id?.slice(0, 8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Today's activity */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white flex items-center gap-2"><Activity className="h-4 w-4 text-amber-400" /> Today's Activity</h2>
            <span className="text-xs text-gray-500">{activity.length} events</span>
          </div>
          <table className="w-full text-sm" data-testid="auto-trade-activity-table">
            <thead className="bg-gray-950 text-[11px] uppercase tracking-wider text-gray-500">
              <tr><th className="text-left px-4 py-3">Time</th><th>Symbol</th><th>Action</th><th>Qty</th><th>Price</th><th>P&L</th><th>Mode</th><th>Reason</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {activity.length === 0 && (
                <tr><td colSpan={8} className="text-center text-gray-500 py-12">No activity today.</td></tr>
              )}
              {activity.slice().reverse().map((a, i) => (
                <tr key={`${a.time}-${a.symbol}-${a.action}-${i}`} className="hover:bg-gray-800/30" data-testid={`activity-${i}`}>
                  <td className="px-4 py-2.5 text-gray-400 font-mono text-xs">{a.time}</td>
                  <td className="text-center font-bold text-white">{a.symbol}</td>
                  <td className={cn("text-center font-bold", a.action === "BUY" ? "text-emerald-400" : "text-red-400")}>{a.action}</td>
                  <td className="text-center text-gray-300 tabular-nums">{a.qty}</td>
                  <td className="text-center text-gray-300 tabular-nums">₹{a.price?.toFixed(2)}</td>
                  <td className={cn("text-center tabular-nums font-semibold", (a.pnl ?? 0) >= 0 ? "text-emerald-400" : a.pnl != null ? "text-red-400" : "text-gray-600")}>
                    {a.pnl != null ? `${a.pnl >= 0 ? "+" : "-"}₹${Math.abs(a.pnl).toLocaleString("en-IN")}` : "—"}
                  </td>
                  <td className="text-center text-xs"><span className={cn("px-2 py-0.5 rounded font-mono", a.mode === "live" ? "bg-violet-500/20 text-violet-300" : "bg-sky-500/20 text-sky-300")}>{a.mode}</span></td>
                  <td className="text-gray-500 text-xs px-3">{a.reason ?? a.strategy ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Stat({ testid, label, value, color = "text-white" }: any) {
  return (
    <div data-testid={testid} className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
      <p className="text-gray-500 text-[10px] font-bold uppercase tracking-wider">{label}</p>
      <p className={cn("text-xl font-black mt-1 tabular-nums", color)}>{value}</p>
    </div>
  );
}

function Checkpoint({ testid, ok, label, detail, link, icon: Icon, softOk = false }: any) {
  const status = ok ? "ok" : softOk ? "warn" : "fail";
  return (
    <div data-testid={testid} className={cn(
      "rounded-xl border p-4 flex items-start gap-3",
      status === "ok"   && "bg-emerald-500/5 border-emerald-500/30",
      status === "warn" && "bg-amber-500/5 border-amber-500/30",
      status === "fail" && "bg-red-500/5 border-red-500/30",
    )}>
      <div className={cn(
        "h-9 w-9 rounded-lg flex items-center justify-center shrink-0",
        status === "ok"   && "bg-emerald-500/15 text-emerald-300",
        status === "warn" && "bg-amber-500/15 text-amber-300",
        status === "fail" && "bg-red-500/15 text-red-300",
      )}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500">{label}</p>
        <p className="text-sm font-semibold text-white truncate">{detail}</p>
        {!ok && link && (
          <Link href={link.href} className="text-xs text-amber-300 hover:text-amber-200 mt-1 inline-block">{link.text} →</Link>
        )}
      </div>
    </div>
  );
}

function RiskSettings({ status, onClose }: { status: EngineStatus; onClose: () => void }) {
  const qc = useQueryClient();
  const rc = status.risk_config ?? {};
  const [form, setForm] = useState({
    trading_capital:        rc.trading_capital        ?? 100000,
    max_daily_loss_pct:     rc.max_daily_loss_pct     ?? 5,
    max_position_size_pct:  rc.max_position_size_pct  ?? 10,
    max_open_positions:     rc.max_open_positions     ?? 5,
    max_trades_per_day:     rc.max_trades_per_day     ?? 20,
    trailing_stop_pct:      rc.trailing_stop_pct      ?? 1.5,
    trailing_stop_enabled:  rc.trailing_stop_enabled  ?? true,
  });

  const saveMut = useMutation({
    mutationFn: () => api.put("/auto-trade/risk", form).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["auto-trade-status"] }); onClose(); },
  });

  const Field = ({ k, label, step = 1, suffix = "" }: any) => (
    <div>
      <label className="block text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">{label}</label>
      <div className="relative">
        <input
          data-testid={`risk-${k}`}
          type="number"
          step={step}
          value={(form as any)[k]}
          onChange={(e) => setForm({ ...form, [k]: parseFloat(e.target.value) || 0 })}
          className="w-full px-3 py-2 bg-gray-950 border border-gray-800 focus:border-violet-500/50 rounded-lg text-sm text-white tabular-nums outline-none"
        />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500">{suffix}</span>}
      </div>
    </div>
  );

  return (
    <div className="bg-gray-900/60 border border-violet-500/20 rounded-2xl p-5" data-testid="risk-settings-panel">
      <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2"><Settings2 className="h-4 w-4 text-violet-400" /> Risk Settings</h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Field k="trading_capital" label="Trading Capital" step={1000} suffix="₹" />
        <Field k="max_daily_loss_pct" label="Max Daily Loss" step={0.5} suffix="%" />
        <Field k="max_position_size_pct" label="Max Pos. Size" step={0.5} suffix="%" />
        <Field k="max_open_positions" label="Max Open Pos." />
        <Field k="max_trades_per_day" label="Max Trades/Day" />
        <Field k="trailing_stop_pct" label="Trailing Stop" step={0.1} suffix="%" />
      </div>
      <div className="flex items-center gap-3 mt-5">
        <label className="flex items-center gap-2 text-sm text-gray-300">
          <input data-testid="risk-trailing-enabled" type="checkbox" checked={form.trailing_stop_enabled}
            onChange={(e) => setForm({ ...form, trailing_stop_enabled: e.target.checked })}
            className="w-4 h-4 rounded bg-gray-950 border-gray-700" />
          Trailing stop enabled
        </label>
        <div className="flex-1" />
        <button data-testid="risk-cancel" onClick={onClose}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm font-semibold">Cancel</button>
        <button data-testid="risk-save" disabled={saveMut.isPending} onClick={() => saveMut.mutate()}
          className="px-4 py-2 bg-violet-500 hover:bg-violet-400 text-white rounded-lg text-sm font-bold disabled:opacity-50">
          {saveMut.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Risk Hardening Panel — circuit breaker, kill switch, broker
// ─────────────────────────────────────────────────────────────
function RiskHardeningPanel({ status }: { status: EngineStatus }) {
  const qc = useQueryClient();
  const rs = status.risk_state;
  const [flash, setFlash] = useState<string | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["auto-trade-status"] });

  const cbResetMut = useMutation({
    mutationFn: () => api.post("/auto-trade/circuit-breaker/reset").then((r) => r.data),
    onSuccess: () => { invalidate(); setFlash("Circuit breaker reset · entries re-enabled"); setTimeout(() => setFlash(null), 4000); },
  });
  const cbTripMut = useMutation({
    mutationFn: () => api.post("/auto-trade/circuit-breaker/trip", { reason: "Manual trip from dashboard" }).then((r) => r.data),
    onSuccess: () => { invalidate(); setFlash("Circuit breaker TRIPPED — new entries blocked"); setTimeout(() => setFlash(null), 4000); },
  });
  const ksDisarmMut = useMutation({
    mutationFn: () => api.post("/auto-trade/kill-switch/disarm").then((r) => r.data),
    onSuccess: () => { invalidate(); setFlash("Kill switch disarmed"); setTimeout(() => setFlash(null), 4000); },
  });
  const ksArmMut = useMutation({
    mutationFn: () => api.post("/auto-trade/kill-switch/arm", { reason: "Manual arm from dashboard" }).then((r) => r.data),
    onSuccess: () => { invalidate(); setFlash("Kill switch ARMED — entries blocked"); setTimeout(() => setFlash(null), 4000); },
  });
  const brokerRecoverMut = useMutation({
    mutationFn: () => api.post("/auto-trade/broker-recovery/reset").then((r) => r.data),
    onSuccess: () => { invalidate(); setFlash("Broker marked healthy"); setTimeout(() => setFlash(null), 4000); },
  });

  if (!rs) return null;

  const dailyLossUsed   = rs.daily_loss_used_pct ?? 0;
  const tradesUsed      = rs.trades_used_pct ?? 0;
  const openPosUsed     = rs.open_pos_used_pct ?? 0;
  const cbActive        = rs.circuit_breaker_active;
  const ksArmed         = rs.kill_switch_armed;
  const brokerFailing   = rs.broker_failure_count > 0;

  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-5" data-testid="risk-hardening-panel">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Shield className="h-4 w-4 text-amber-400" /> Risk Hardening
          <span className="text-[10px] px-2 py-0.5 bg-amber-500/15 text-amber-300 rounded-full font-bold tracking-wider">SAFETY</span>
        </h2>
        <span className="text-[11px] text-gray-500 font-mono">
          {rs.last_risk_check_at ? `checked ${new Date(rs.last_risk_check_at).toLocaleTimeString()}` : ""}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Circuit Breaker */}
        <div className={cn(
          "rounded-xl border p-4 flex flex-col gap-3",
          cbActive ? "bg-red-500/10 border-red-500/40" : "bg-gray-950 border-gray-800"
        )} data-testid="risk-circuit-breaker">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2">
              <Power className={cn("h-3.5 w-3.5", cbActive ? "text-red-400" : "text-gray-500")} /> Circuit Breaker
            </p>
            <span className={cn(
              "text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wider",
              cbActive ? "bg-red-500/20 text-red-300" : "bg-emerald-500/15 text-emerald-300"
            )}>{cbActive ? "TRIPPED" : "ARMED"}</span>
          </div>
          <p className="text-sm text-white">
            {cbActive
              ? <>Blocking new entries · <span className="text-red-300">{rs.circuit_breaker_reason ?? "manual trip"}</span></>
              : "Normal — engine entries enabled."}
          </p>
          {cbActive && rs.circuit_breaker_tripped_at && (
            <p className="text-[11px] text-gray-500 font-mono">since {new Date(rs.circuit_breaker_tripped_at).toLocaleString()}</p>
          )}
          <div className="flex items-center gap-2 mt-1">
            {cbActive ? (
              <button data-testid="cb-reset-btn" disabled={cbResetMut.isPending} onClick={() => cbResetMut.mutate()}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 disabled:bg-gray-800 text-gray-950 rounded-lg text-xs font-bold tracking-wider uppercase">
                <Check className="h-3.5 w-3.5" /> Reset
              </button>
            ) : (
              <button data-testid="cb-trip-btn" disabled={cbTripMut.isPending} onClick={() => { if (confirm("Manually trip the circuit breaker? This blocks all new entries.")) cbTripMut.mutate(); }}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-red-500/30 text-gray-300 hover:text-red-300 rounded-lg text-xs font-bold tracking-wider uppercase border border-gray-800 hover:border-red-500/40">
                <Power className="h-3.5 w-3.5" /> Trip Manually
              </button>
            )}
          </div>
        </div>

        {/* Daily-Loss Kill Switch */}
        <div className={cn(
          "rounded-xl border p-4 flex flex-col gap-3",
          ksArmed ? "bg-amber-500/10 border-amber-500/40" : "bg-gray-950 border-gray-800"
        )} data-testid="risk-kill-switch">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2">
              <ShieldAlert className={cn("h-3.5 w-3.5", ksArmed ? "text-amber-400" : "text-gray-500")} /> Daily-Loss Kill Switch
            </p>
            <span className={cn(
              "text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wider",
              ksArmed ? "bg-amber-500/20 text-amber-300" : "bg-gray-800 text-gray-400"
            )}>{ksArmed ? "ARMED" : "SAFE"}</span>
          </div>

          <ProgressBar testid="kill-bar" label={`Daily loss · ${dailyLossUsed.toFixed(0)}% of cap`} value={dailyLossUsed}
            tone={dailyLossUsed > 80 ? "bad" : dailyLossUsed > 50 ? "warn" : "good"} />
          <ProgressBar testid="trade-bar" label={`Trades · ${tradesUsed.toFixed(0)}% of daily cap`} value={tradesUsed}
            tone={tradesUsed > 80 ? "bad" : tradesUsed > 50 ? "warn" : "good"} />
          <ProgressBar testid="open-bar" label={`Open positions · ${openPosUsed.toFixed(0)}% of cap`} value={openPosUsed}
            tone={openPosUsed > 80 ? "bad" : openPosUsed > 50 ? "warn" : "good"} />

          {ksArmed && rs.kill_switch_reason && (
            <p className="text-xs text-amber-300">{rs.kill_switch_reason}</p>
          )}
          <div className="flex items-center gap-2 mt-1">
            {ksArmed ? (
              <button data-testid="ks-disarm-btn" disabled={ksDisarmMut.isPending} onClick={() => ksDisarmMut.mutate()}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-gray-950 rounded-lg text-xs font-bold tracking-wider uppercase">
                <Check className="h-3.5 w-3.5" /> Disarm
              </button>
            ) : (
              <button data-testid="ks-arm-btn" disabled={ksArmMut.isPending} onClick={() => { if (confirm("Arm the kill switch? This blocks all new entries until disarmed.")) ksArmMut.mutate(); }}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-amber-500/30 text-gray-300 hover:text-amber-300 rounded-lg text-xs font-bold tracking-wider uppercase border border-gray-800 hover:border-amber-500/40">
                <ShieldAlert className="h-3.5 w-3.5" /> Arm
              </button>
            )}
          </div>
        </div>

        {/* Broker Recovery */}
        <div className={cn(
          "rounded-xl border p-4 flex flex-col gap-3",
          brokerFailing ? "bg-orange-500/10 border-orange-500/40" : "bg-gray-950 border-gray-800"
        )} data-testid="risk-broker">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2">
              {brokerFailing ? <WifiOff className="h-3.5 w-3.5 text-orange-400" /> : <Wifi className="h-3.5 w-3.5 text-emerald-400" />}
              Broker Recovery
            </p>
            <span className={cn(
              "text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wider",
              brokerFailing ? "bg-orange-500/20 text-orange-300" : "bg-emerald-500/15 text-emerald-300"
            )}>{brokerFailing ? `${rs.broker_failure_count} FAILS` : "HEALTHY"}</span>
          </div>
          {brokerFailing ? (
            <>
              <p className="text-sm text-white">{rs.broker_last_error}</p>
              <p className="text-[11px] text-gray-500">
                After 5 consecutive failures the breaker auto-trips. Tap "Mark Healthy" once you've reconnected.
              </p>
            </>
          ) : (
            <p className="text-sm text-white">
              No recent failures.
              {rs.broker_last_recovery_at && (
                <span className="text-[11px] text-gray-500 ml-2 font-mono">
                  last recovery {new Date(rs.broker_last_recovery_at).toLocaleTimeString()}
                </span>
              )}
            </p>
          )}
          <div>
            <button data-testid="broker-recover-btn" disabled={brokerRecoverMut.isPending} onClick={() => brokerRecoverMut.mutate()}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold tracking-wider uppercase",
                brokerFailing
                  ? "bg-emerald-500 hover:bg-emerald-400 text-gray-950"
                  : "bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-800"
              )}>
              <RotateCcw className="h-3.5 w-3.5" /> Mark Healthy
            </button>
          </div>
        </div>
      </div>

      {flash && (
        <p data-testid="risk-flash" className="text-xs text-amber-300 mt-3">{flash}</p>
      )}
    </div>
  );
}

function ProgressBar({ testid, label, value, tone = "good" }: {
  testid: string; label: string; value: number;
  tone?: "good" | "warn" | "bad";
}) {
  const barColor =
    tone === "good" ? "bg-emerald-400"
    : tone === "warn" ? "bg-amber-400"
    : "bg-red-400";
  return (
    <div data-testid={testid}>
      <p className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">{label}</p>
      <div className="w-full h-1.5 bg-gray-900 rounded-full overflow-hidden">
        <div className={cn("h-1.5 rounded-full transition-all", barColor)} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// News-Driven Candidates Panel
// ─────────────────────────────────────────────────────────────
interface NewsCandidate {
  symbol: string;
  headline: string;
  source: string;
  article_id: string;
  impact_direction: string;
  confidence: number;
  affected_sectors: string[];
  opportunity_summary: string;
  status: string;
  created_at: number;
  user_id?: string;
  ai_decision?: { decision?: string; confidence?: number; reasoning?: string; provider?: string } | null;
  rejection_reason?: string | null;
}

interface NewsCandidatesResp {
  summary: {
    enabled: boolean;
    last_run_iso?: string | null;
    next_run_in_sec: number;
    candidates_total: number;
    pending: number;
    executed: number;
    rejected: number;
    last_error?: string | null;
  };
  candidates: NewsCandidate[];
}

function NewsCandidatesPanel() {
  const qc = useQueryClient();
  const { data } = useQuery<NewsCandidatesResp>({
    queryKey: ["news-candidates"],
    queryFn: () => api.get("/auto-trade/news-candidates").then((r) => r.data),
    refetchInterval: 15_000,
  });
  const scanMut = useMutation({
    mutationFn: () => api.post("/auto-trade/news-candidates/scan", undefined, { timeout: 45_000 }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["news-candidates"] }); },
  });
  const toggleMut = useMutation({
    mutationFn: (enabled: boolean) => api.post("/auto-trade/news-candidates/toggle", { enabled }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news-candidates"] }),
  });
  const resetMut = useMutation({
    mutationFn: () => api.post("/auto-trade/news-candidates/reset").then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["news-candidates"] }),
  });

  const summary = data?.summary;
  const candidates = data?.candidates ?? [];

  return (
    <div className="bg-gradient-to-br from-sky-500/10 via-sky-500/5 to-transparent border border-sky-500/30 rounded-2xl p-5"
      data-testid="news-candidates-panel">
      <div className="flex items-start gap-4 flex-wrap">
        <div className="h-12 w-12 rounded-xl bg-sky-500/20 flex items-center justify-center shrink-0">
          <Newspaper className="h-6 w-6 text-sky-300" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              News-Driven Candidates
              <span className="text-[10px] px-2 py-0.5 bg-sky-500/20 text-sky-300 rounded-full font-bold tracking-wider">PHASE 4</span>
            </h2>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-[11px] text-gray-400 cursor-pointer">
                <input
                  data-testid="news-pipeline-toggle"
                  type="checkbox"
                  checked={summary?.enabled ?? true}
                  onChange={(e) => toggleMut.mutate(e.target.checked)}
                  className="w-3.5 h-3.5 rounded bg-gray-950 border-gray-700"
                />
                Pipeline enabled
              </label>
              <button data-testid="news-scan-btn" disabled={scanMut.isPending} onClick={() => scanMut.mutate()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-sky-500 hover:bg-sky-400 disabled:bg-gray-800 text-white rounded-lg text-xs font-bold">
                <RefreshCw className={cn("h-3.5 w-3.5", scanMut.isPending && "animate-spin")} />
                {scanMut.isPending ? "Scanning…" : "Scan Now"}
              </button>
              <button data-testid="news-reset-btn" disabled={resetMut.isPending} onClick={() => resetMut.mutate()}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 text-gray-400 rounded-lg text-xs">
                Reset
              </button>
            </div>
          </div>
          <p className="text-gray-400 text-xs mt-1.5">
            Every 5 minutes we scan news with positive impact, extract affected stocks, and push them into the AI Brain
            for evaluation. A BUY decision triggers a paper or live order via the engine.
          </p>

          {/* Summary strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
            <MiniStat testid="news-stat-total"     label="Tracked"  value={String(summary?.candidates_total ?? 0)} />
            <MiniStat testid="news-stat-pending"   label="Pending"  value={String(summary?.pending ?? 0)} />
            <MiniStat testid="news-stat-executed"  label="Executed" value={String(summary?.executed ?? 0)} tone="good" />
            <MiniStat testid="news-stat-rejected"  label="Rejected" value={String(summary?.rejected ?? 0)} tone="warn" />
          </div>

          <p className="text-[11px] text-gray-500 mt-2 font-mono">
            Last scan: {summary?.last_run_iso ? new Date(summary.last_run_iso).toLocaleTimeString() : "never"}
            {" · "}next in ~{Math.max(0, Math.round((summary?.next_run_in_sec ?? 0) / 60))}m
            {summary?.last_error && <span className="text-red-400 ml-2">· error: {summary.last_error}</span>}
          </p>
        </div>
      </div>

      <div className="mt-4 bg-gray-950/60 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm" data-testid="news-candidates-table">
          <thead className="bg-gray-950 text-[11px] uppercase tracking-wider text-gray-500">
            <tr><th className="text-left px-3 py-2.5">Symbol</th><th>Conf.</th><th className="text-left">Headline</th><th>Status</th><th className="text-left">AI Decision</th></tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {candidates.length === 0 && (
              <tr><td colSpan={5} className="text-center text-gray-500 py-8" data-testid="news-empty">
                No candidates yet. Tap <strong className="text-white">Scan Now</strong> to seed the pipeline with the latest news.
              </td></tr>
            )}
            {candidates.map((c) => (
              <tr key={`${c.user_id ?? ""}-${c.symbol}-${c.article_id}`} className="hover:bg-gray-800/30" data-testid={`news-cand-${c.symbol}`}>
                <td className="px-3 py-2 font-bold text-white">{c.symbol}<span className="text-gray-600 text-[10px] ml-2">{c.source}</span></td>
                <td className="text-center text-sky-300 tabular-nums font-semibold">{c.confidence}%</td>
                <td className="text-gray-300 text-xs max-w-md truncate pr-3">{c.headline}</td>
                <td className="text-center">
                  <span className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wider",
                    c.status === "executed" ? "bg-emerald-500/20 text-emerald-300"
                    : c.status === "rejected" ? "bg-gray-800 text-gray-400"
                    : "bg-sky-500/20 text-sky-300"
                  )}>{c.status.toUpperCase()}</span>
                </td>
                <td className="text-gray-400 text-xs max-w-xs truncate">
                  {c.ai_decision
                    ? <><span className="font-bold text-white">{c.ai_decision.decision}</span> · {c.ai_decision.confidence}% · {c.ai_decision.reasoning?.slice(0, 60)}</>
                    : c.rejection_reason
                    ? <span className="text-gray-500">{c.rejection_reason}</span>
                    : <span className="text-gray-600">pending…</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MiniStat({ testid, label, value, tone = "neutral" }: {
  testid: string; label: string; value: string; tone?: "good" | "warn" | "bad" | "neutral";
}) {
  const colour = tone === "good" ? "text-emerald-300" : tone === "warn" ? "text-amber-300" : tone === "bad" ? "text-red-300" : "text-white";
  return (
    <div data-testid={testid} className="bg-gray-950 border border-gray-800 rounded-lg px-3 py-2">
      <p className="text-gray-500 text-[10px] font-bold uppercase tracking-wider">{label}</p>
      <p className={cn("text-lg font-black mt-0.5 tabular-nums", colour)}>{value}</p>
    </div>
  );
}

