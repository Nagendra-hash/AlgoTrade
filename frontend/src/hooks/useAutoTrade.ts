// Auto-trade engine hooks
// Path: frontend/src/hooks/useAutoTrade.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────
export interface EngineStatus {
  is_running: boolean;
  mode: string;
  active_strategies: number;
  open_positions: number;
  today_trades: number;
  today_pnl: number;
  win_rate: number;
  risk_config: RiskConfig;
}

export interface RiskConfig {
  max_daily_loss_pct: number;
  max_position_size_pct: number;
  max_open_positions: number;
  max_trades_per_day: number;
  trailing_stop_enabled: boolean;
  trailing_stop_pct: number;
  trading_capital?: number;
}

export interface EnginePosition {
  id: string;
  symbol: string;
  exchange: string;
  side: string;
  entry_price: number;
  quantity: number;
  current_price: number;
  stop_loss: number;
  take_profit: number;
  pnl: number;
  pnl_pct: number;
  entry_time: string;
  status: string;
  strategy_id: string;
}

export interface EngineActivity {
  time: string;
  symbol: string;
  action: string;
  qty: number;
  price: number;
  pnl?: number;
  pnl_pct?: number;
  stop_loss?: number;
  take_profit?: number;
  reason?: string;
  status: string;
  mode: string;
  strategy?: string;
}

export interface ScreenCandidate {
  symbol: string;
  ltp: number;
  change_pct: number;
  avg_volume: number;
  rsi: number | null;
  roc: number;
  macd: number | null;
  trend_up: boolean;
  vol_ratio: number;
  momentum_score: number;
  trend_score: number;
  reversion_score: number;
  composite_score: number;
}

// ── Hooks ─────────────────────────────────────────────────────

export function useEngineStatus() {
  return useQuery<EngineStatus>({
    queryKey: ["auto-trade-status"],
    queryFn: () => api.get("/auto-trade/status").then((r) => r.data),
    refetchInterval: 10_000, // Poll every 10s
  });
}

export function useStartEngine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (mode: "paper" | "live" = "paper") =>
      api.post("/auto-trade/start", { mode }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auto-trade-status"] }),
  });
}

export function useStopEngine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/auto-trade/stop").then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auto-trade-status"] }),
  });
}

export function useEnginePositions() {
  return useQuery<{ positions: EnginePosition[] }>({
    queryKey: ["auto-trade-positions"],
    queryFn: () => api.get("/auto-trade/positions").then((r) => r.data),
    refetchInterval: 15_000,
  });
}

export function useEngineActivity(limit = 50) {
  return useQuery<{ activity: EngineActivity[]; total: number }>({
    queryKey: ["auto-trade-activity", limit],
    queryFn: () => api.get("/auto-trade/activity", { params: { limit } }).then((r) => r.data),
    refetchInterval: 15_000,
  });
}

export function useRiskConfig() {
  return useQuery<{ risk_config: RiskConfig }>({
    queryKey: ["auto-trade-risk"],
    queryFn: () => api.get("/auto-trade/risk").then((r) => r.data),
  });
}

export function useUpdateRiskConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<RiskConfig>) =>
      api.put("/auto-trade/risk", config).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auto-trade-risk"] }),
  });
}

export function useScreenStocks() {
  return useMutation({
    mutationFn: (payload: { strategy_type: string; min_volume?: number; limit?: number }) =>
      api.post("/auto-trade/screen", payload).then((r) => r.data),
  });
}

export interface QuickStartPayload {
  strategy_type: "trend_following" | "mean_reversion" | "momentum" | "breakout" | "scalping" | "swing";
  symbols?: string[];
  timeframe?: string;
  exchange?: string;
  mode?: "paper" | "live";
  trading_capital?: number;
  max_position_size_pct?: number;
}

export interface QuickStartResponse {
  message: string;
  strategy: { id: string; name: string; strategy_type: string; symbols: string[]; indicators: string[] };
  engine: EngineStatus;
}

export function useQuickStart() {
  const qc = useQueryClient();
  return useMutation<QuickStartResponse, Error, QuickStartPayload>({
    mutationFn: (payload) =>
      api.post("/auto-trade/quick-start", payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["auto-trade-status"] });
      qc.invalidateQueries({ queryKey: ["auto-trade-risk"] });
      qc.invalidateQueries({ queryKey: ["strategies"] });
    },
  });
}
