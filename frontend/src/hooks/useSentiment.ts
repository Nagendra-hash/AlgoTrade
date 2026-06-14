// Sentiment hooks
// Path: frontend/src/hooks/useSentiment.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SentimentData, MarketSentimentSummary } from "@/types";

export function useSentiment(symbol: string, exchange = "NSE") {
  return useQuery<SentimentData>({
    queryKey: ["sentiment", symbol, exchange],
    queryFn:  () => api.get(`/sentiment/${symbol}`, { params: { exchange } }).then((r) => r.data),
    staleTime: 15 * 60_000,
    enabled: Boolean(symbol),
  });
}

export function useBulkSentiment(symbols: string[], exchange = "NSE") {
  return useQuery<SentimentData[]>({
    queryKey: ["sentiment-bulk", symbols.join(","), exchange],
    queryFn:  () => api.post("/sentiment/bulk", { symbols, exchange }).then((r) => r.data),
    staleTime: 15 * 60_000,
    enabled: symbols.length > 0,
  });
}

export function useMarketSentimentSummary(symbols: string[]) {
  return useQuery<MarketSentimentSummary>({
    queryKey: ["sentiment-summary", symbols.join(",")],
    queryFn:  () => api.post("/sentiment/market-summary", { symbols, exchange: "NSE" }).then((r) => r.data),
    staleTime: 15 * 60_000,
    refetchInterval: 15 * 60_000,
    enabled: symbols.length > 0,
  });
}

export function useRefreshSentiment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      api.get(`/sentiment/${symbol}`, { params: { force_refresh: true } }).then((r) => r.data),
    onSuccess: (_data, symbol) => {
      qc.invalidateQueries({ queryKey: ["sentiment", symbol] });
      qc.invalidateQueries({ queryKey: ["sentiment-bulk"] });
      qc.invalidateQueries({ queryKey: ["sentiment-summary"] });
    },
  });
}
