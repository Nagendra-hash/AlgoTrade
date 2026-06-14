// Portfolio hooks
// Path: frontend/src/hooks/usePortfolio.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Holding, Position, PortfolioSummary } from "@/types";

interface HoldingsResponse {
  holdings:   Holding[];
  source:     string;
  is_real:    boolean;
  message?:   string;
  client_id?: string;
  fetched_at: string;
}

interface PositionsResponse {
  positions: Position[];
  source:    string;
  is_real:   boolean;
}

export function useHoldings() {
  return useQuery<HoldingsResponse>({
    queryKey: ["holdings"],
    queryFn:  () => api.get("/portfolio/holdings").then((r) => r.data),
    staleTime: 30_000,
  });
}

export function usePortfolioSummary() {
  return useQuery<PortfolioSummary>({
    queryKey: ["portfolio-summary"],
    queryFn:  () => api.get("/portfolio/summary").then((r) => r.data),
    refetchInterval: 30_000,
  });
}

export function usePositions() {
  return useQuery<PositionsResponse>({
    queryKey: ["positions"],
    queryFn:  () => api.get("/portfolio/positions").then((r) => r.data),
    refetchInterval: 15_000,
  });
}
