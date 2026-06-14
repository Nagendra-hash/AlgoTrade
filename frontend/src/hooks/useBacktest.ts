// Backtest API hook
// Path: frontend/src/hooks/useBacktest.ts
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface BacktestRequest {
  strategy_id?: string;
  symbol: string;
  exchange?: string;
  timeframe: string;
  period: string;
  initial_capital: number;
  save_results?: boolean;
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

export interface BacktestResult {
  total_return: number;
  total_pnl: number;
  final_capital: number;
  total_trades: number;
  win_rate: number;
  max_drawdown: number;
  profit_factor: number;
  sharpe_ratio: number;
  trades: BacktestTrade[];
  equity_curve: { date: number; value: number }[];
  strategy_id?: string;
  symbol: string;
  timeframe: string;
  period: string;
  initial_capital: number;
  ran_at: string;
}

export function useRunBacktest() {
  return useMutation<BacktestResult, Error, BacktestRequest>({
    mutationFn: async (data) => {
      const res = await api.post("/strategy/backtest", data);
      return res.data as BacktestResult;
    },
  });
}

export interface CompareStrategySlot {
  label: string;
  strategy_id?: string;
  strategy_type: string;
  parameters?: Record<string, unknown>;
}

export interface CompareBacktestRequest {
  strategies: CompareStrategySlot[];
  symbol: string;
  exchange?: string;
  timeframe: string;
  period: string;
  initial_capital: number;
}

export interface CompareBacktestItem {
  label: string;
  result: BacktestResult;
}

export function useCompareBacktests() {
  return useMutation<CompareBacktestItem[], Error, CompareBacktestRequest>({
    mutationFn: async (data) => {
      const res = await api.post("/strategy/backtest/compare", data);
      return res.data as CompareBacktestItem[];
    },
  });
}
