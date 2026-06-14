"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { RefreshCw, Loader2, Newspaper, Globe, Filter } from "lucide-react";
import { useNews } from "@/hooks/useNews";
import { NewsCard } from "./NewsCard";
import { cn } from "@/lib/utils";
import type { NewsCategory } from "@/types";

const CATS: { id: NewsCategory; label: string; emoji: string }[] = [
  { id: "all",         label: "All",         emoji: "📰" },
  { id: "bullish",     label: "Bullish",     emoji: "📈" },
  { id: "bearish",     label: "Bearish",     emoji: "📉" },
  { id: "earnings",    label: "Earnings",    emoji: "💰" },
  { id: "macro",       label: "Macro",       emoji: "🏦" },
  { id: "geopolitical",label: "Geopolitical",emoji: "🌍" },
  { id: "breaking",    label: "Breaking",    emoji: "🔴" },
  { id: "neutral",     label: "Neutral",     emoji: "➖" },
];

const SOURCE_CHIPS = [
  { id: "Foreign Policy",      label: "Foreign Policy",      color: "border-indigo-500/30 text-indigo-400" },
  { id: "The Economist",       label: "The Economist",       color: "border-rose-500/30 text-rose-400" },
  { id: "Geopolitical Monitor",label: "Geo Monitor",         color: "border-cyan-500/30 text-cyan-400" },
];

function Skeleton() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 animate-pulse">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-4 w-16 bg-gray-800 rounded-full" />
        <div className="h-3 w-20 bg-gray-800 rounded" />
      </div>
      <div className="h-4 w-full bg-gray-800 rounded mb-2" />
      <div className="h-4 w-4/5 bg-gray-800 rounded mb-3" />
      <div className="h-3 w-full bg-gray-800 rounded mb-1" />
      <div className="h-3 w-3/4 bg-gray-800 rounded" />
    </div>
  );
}

interface Props { symbols?: string[]; onSymbolClick?: (symbol: string) => void; }

export function NewsFeed({ symbols, onSymbolClick }: Props) {
  const [category, setCategory] = useState<NewsCategory>("all");
  const [sourceFilter, setSourceFilter] = useState<string[]>([]);
  const loaderRef = useRef<HTMLDivElement>(null);
  const obsRef    = useRef<IntersectionObserver | null>(null);

  const {
    data, isLoading, isFetchingNextPage,
    fetchNextPage, hasNextPage, refetch, isFetching,
  } = useNews(symbols, category, sourceFilter.length > 0 ? sourceFilter : undefined);

  const articles = data?.pages.flatMap((p) => p.articles) ?? [];

  // Clean up observer properly on unmount and category change
  const setupObserver = useCallback(() => {
    if (obsRef.current) {
      obsRef.current.disconnect();
      obsRef.current = null;
    }
    if (!loaderRef.current || !hasNextPage) return;

    obsRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1, rootMargin: "100px" }
    );
    obsRef.current.observe(loaderRef.current);
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  useEffect(() => {
    setupObserver();
    return () => {
      obsRef.current?.disconnect();
      obsRef.current = null;
    };
  }, [setupObserver]);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper className="h-5 w-5 text-blue-400" />
          <h2 className="text-white font-bold text-xl">Market News</h2>
          {articles.length > 0 && (
            <span className="text-gray-500 text-sm">({articles.length})</span>
          )}
        </div>
        <button onClick={() => refetch()} disabled={isFetching}
          className="h-9 w-9 flex items-center justify-center bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-gray-400 hover:text-white transition-all">
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>

      {/* Category filters */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 flex-shrink-0 scrollbar-hide">
        {CATS.map((cat) => (
          <button key={cat.id} onClick={() => setCategory(cat.id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold whitespace-nowrap transition-all flex-shrink-0",
              category === cat.id
                ? "bg-blue-600/20 border-blue-500 text-blue-400"
                : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600"
            )}>
            <span>{cat.emoji}</span>{cat.label}
          </button>
        ))}
      </div>

      {/* Source filter chips for geopolitical news sources */}
      <div className="flex items-center gap-1.5 mb-4 flex-shrink-0 overflow-x-auto scrollbar-hide">
        <Filter className="h-3.5 w-3.5 text-gray-600 flex-shrink-0" />
        <button onClick={() => setSourceFilter([])}
          className={cn("px-2.5 py-1 rounded-lg border text-[10px] font-semibold transition-all flex-shrink-0 uppercase tracking-wider",
            sourceFilter.length === 0
              ? "bg-blue-600/20 border-blue-500 text-blue-400"
              : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300"
          )}>
          All Sources
        </button>
        {SOURCE_CHIPS.map((sc) => {
          const active = sourceFilter.includes(sc.id);
          return (
            <button key={sc.id} onClick={() => {
              setSourceFilter(prev =>
                active ? prev.filter(s => s !== sc.id) : [...prev, sc.id]
              );
            }}
              className={cn("px-2.5 py-1 rounded-lg border text-[10px] font-semibold transition-all flex-shrink-0 uppercase tracking-wider",
                active
                  ? `${sc.color} bg-opacity-15`
                  : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300"
              )}>
              {sc.label}
            </button>
          );
        })}
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} />)}
          </div>
        ) : articles.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <Newspaper className="h-10 w-10 text-gray-700 mb-3" />
            <p className="text-gray-400 font-medium">No news found</p>
            <p className="text-gray-600 text-sm mt-1">
              {category !== "all" ? `No ${category} news right now` : "Check back soon"}
            </p>
          </div>
        ) : (
          <div className="space-y-4 pb-4">
            {articles.map((a) => <NewsCard key={a.id} article={a} onSymbolClick={onSymbolClick} />)}
            <div ref={loaderRef} className="h-4 flex items-center justify-center">
              {isFetchingNextPage && (
                <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
              )}
              {!hasNextPage && articles.length > 0 && (
                <p className="text-gray-600 text-xs">You&apos;ve caught up! 🎉</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
