"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface BacktestSummary {
  symbol: string;
  exchange: string;
  strategy_type: string;
  interval: string;
  period: string;
  candles_used: number;
  initial_capital: number;
  total_return: number;
  total_pnl: number;
  final_capital: number;
  total_trades: number;
  win_rate: number;
  max_drawdown: number;
  profit_factor: number;
  sharpe_ratio: number;
  ran_at: string;
}

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  side: string;
  qty: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
}

export interface BacktestEquityPoint {
  date: number;
  value: number;
}

export interface BacktestResult {
  summary: BacktestSummary;
  trades: BacktestTrade[];
  equity_curve: BacktestEquityPoint[];
  error?: string;
}

// Legacy type used by the report exporter (lib/export.ts).
// Kept as a thin shape — actual flow is through `BacktestResult.summary`.
export interface CompareBacktestItem {
  label: string;
  result: {
    total_return: number;
    total_pnl: number;
    final_capital: number;
    total_trades: number;
    win_rate: number;
    max_drawdown: number;
    profit_factor: number;
    sharpe_ratio: number;
    trades?: BacktestTrade[];
  };
}

export interface BacktestRequest {
  symbol: string;
  exchange?: string;
  interval: string;
  period: string;
  strategy_type: string;
  initial_capital: number;
  parameters?: Record<string, unknown>;
}

export function useBacktestStrategies() {
  return useQuery<{ strategies: { id: string; label: string }[] }>({
    queryKey: ["backtest-strategies"],
    queryFn: () => api.get("/backtest/strategies").then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useRunBacktest() {
  return useMutation<BacktestResult, Error, BacktestRequest>({
    mutationFn: (body) => api.post("/backtest/run", body, { timeout: 60_000 }).then((r) => r.data),
  });
}
