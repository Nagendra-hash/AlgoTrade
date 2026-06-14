// News infinite query hook
// Path: frontend/src/hooks/useNews.ts
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NewsFeedResponse, NewsCategory, NewsScreenerResponse } from "@/types";

export function useNews(symbols?: string[], category?: NewsCategory, sources?: string[]) {
  return useInfiniteQuery<NewsFeedResponse>({
    queryKey: ["news", symbols?.join(",") ?? "", category ?? "", sources?.join(",") ?? ""],
    queryFn: async ({ pageParam = 1 }) => {
      const params: Record<string, string | number> = { page: pageParam as number, per_page: 20 };
      if (symbols?.length) params.symbols   = symbols.join(",");
      if (category && category !== "all") params.category = category;
      if (sources?.length)    params.sources  = sources.join(",");
      return (await api.get("/news", { params })).data;
    },
    initialPageParam: 1,
    getNextPageParam: (last) => {
      const next = last.page + 1;
      return next * last.per_page <= last.total + last.per_page ? next : undefined;
    },
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}

export function useNewsScreener(sources?: string[]) {
  return useQuery<NewsScreenerResponse>({
    queryKey: ["news-screener", sources?.join(",") ?? ""],
    queryFn: async () => {
      const params: Record<string, string | number> = { limit: 15 };
      if (sources?.length) params.sources = sources.join(",");
      return (await api.get("/news/screener", { params })).data;
    },
    staleTime: 10 * 60_000,
    refetchInterval: 10 * 60_000,
  });
}
