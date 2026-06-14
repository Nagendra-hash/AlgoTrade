// Market data hooks
// Path: frontend/src/hooks/useMarket.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Quote, Candle, Instrument } from "@/types";

export function useQuote(symbol: string, exchange = "NSE") {
  return useQuery<Quote>({
    queryKey: ["quote", symbol, exchange],
    queryFn:  () => api.get(`/market/quote/${symbol}`, { params: { exchange } }).then((r) => r.data),
    refetchInterval: 3_000,
    enabled: Boolean(symbol),
    staleTime: 1_000,
  });
}

export function useCandles(symbol: string, interval = "1d", period = "1y", exchange = "NSE") {
  return useQuery<Candle[]>({
    queryKey: ["candles", symbol, interval, period, exchange],
    queryFn:  () => api.get(`/market/candles/${symbol}`, { params: { interval, period, exchange } }).then((r) => r.data),
    staleTime: interval === "1d" ? 60_000 : 10_000,
    enabled: Boolean(symbol),
  });
}

export function useMultipleQuotes(symbols: string[], exchange = "NSE") {
  return useQuery<Quote[]>({
    queryKey: ["quotes", symbols.join(","), exchange],
    queryFn:  () => api.get("/market/quotes", { params: { symbols: symbols.join(","), exchange } }).then((r) => r.data),
    refetchInterval: 3_000,
    enabled: symbols.length > 0,
  });
}

export function useMarketStatus() {
  return useQuery<{ is_open: boolean; status: string; exchange: string }>({
    queryKey: ["market-status"],
    queryFn:  () => api.get("/market/status").then((r) => r.data),
    refetchInterval: 30_000,
  });
}

export function useSymbolSearch(query: string) {
  return useQuery<Instrument[]>({
    queryKey: ["symbol-search", query],
    queryFn:  () => api.get("/market/search", { params: { q: query } }).then((r) => r.data),
    enabled: query.length >= 1,
    staleTime: 60_000,
  });
}

export function useIndices() {
  return useQuery<Quote[]>({
    queryKey: ["indices"],
    queryFn:  () => api.get("/market/indices").then((r) => r.data),
    refetchInterval: 5_000,
  });
}
