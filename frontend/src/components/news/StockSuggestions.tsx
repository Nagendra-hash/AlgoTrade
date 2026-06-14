"use client";
// Path: frontend/src/components/news/StockSuggestions.tsx
import { useState, useMemo, useCallback, useEffect, Suspense } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useBulkSentiment, useMarketSentimentSummary } from "@/hooks/useSentiment";
import { useMultipleQuotes } from "@/hooks/useMarket";
import { useNewsScreener } from "@/hooks/useNews";
import { cn } from "@/lib/utils";
import {
  TrendingUp, TrendingDown, Sparkles, Loader2,
  RefreshCw, ArrowUpRight, ArrowDownLeft, Activity,
  Globe, Newspaper, BarChart3, Layers, Grid3X3, Search,
  ArrowUp, ArrowDown,
} from "lucide-react";
import type { NewsScreenerRecommendation, NewsScreenerSectorGroup } from "@/types";
import { SECTOR_COLORS } from "@/types";

const WATCH_SYMBOLS = ["RELIANCE","TCS","INFY","HDFCBANK","SBIN","ICICIBANK","WIPRO","BAJFINANCE","TATAMOTORS","ADANIENT","HINDUNILVR","BHARTIARTL","ASIANPAINT","MARUTI","SUNPHARMA","NIFTY50","BANKNIFTY"];

const NEWS_SOURCES_FILTER = ["Foreign Policy", "The Economist", "Geopolitical Monitor"];

function SentimentScore({ score, size = "sm" }: { score: number; size?: "sm" | "md" }) {
  const barOffset = 50 + score * 0.5;
  const isPos = score >= 0;
  return (
    <div className="flex items-center gap-1.5">
      <div className={cn("h-1.5 bg-gray-800 rounded-full overflow-hidden flex-1 relative", size === "md" ? "w-16" : "w-10")}>
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-gray-600" />
        <div style={{ width: `${Math.abs(score) * 0.5}%`, marginLeft: isPos ? "50%" : `${50 - Math.abs(score) * 0.5}%` }}
          className={cn("h-full rounded-full transition-all", score > 15 ? "bg-green-500" : score < -15 ? "bg-red-500" : "bg-gray-500")} />
      </div>
      <span className={cn("font-bold", score > 15 ? "text-green-400" : score < -15 ? "text-red-400" : "text-gray-400")}>
        {score > 0 ? "+" : ""}{score}
      </span>
    </div>
  );
}

function ScreenerCard({ rec, compact }: { rec: NewsScreenerRecommendation; compact?: boolean }) {
  const sentimentColor = rec.avg_sentiment > 0.1 ? "text-green-400" : rec.avg_sentiment < -0.1 ? "text-red-400" : "text-gray-400";
  const trendIcon = rec.trend_up ? <TrendingUp className="h-3 w-3 text-green-400" /> : <TrendingDown className="h-3 w-3 text-red-400" />;
  const sectorStyle = SECTOR_COLORS[rec.sector] ?? SECTOR_COLORS["Other"];

  return (
    <div className={cn("bg-gray-800/60 rounded-xl p-3 hover:bg-gray-800 transition-all group", sectorStyle.border, "border")}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold text-sm">{rec.symbol}</span>
          {rec.ltp && (
            <span className="text-gray-400 text-xs">₹{rec.ltp.toLocaleString("en-IN")}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {rec.change_pct !== null && (
            <span className={cn("text-xs font-bold", rec.change_pct >= 0 ? "text-green-400" : "text-red-400")}>
              {rec.change_pct >= 0 ? "+" : ""}{rec.change_pct}%
            </span>
          )}
          {trendIcon}
        </div>
      </div>

      {/* News context */}
      <div className="flex items-center gap-2 mb-1.5 text-[10px]">
        <span className="flex items-center gap-1 text-gray-500">
          <Newspaper className="h-3 w-3" />
          {rec.news_count} articles
        </span>
        <span className={cn("flex items-center gap-1", sentimentColor)}>
          <Activity className="h-3 w-3" />
          {(rec.avg_sentiment * 100).toFixed(0)} sentiment
        </span>
        {rec.screener_score !== null && (
          <span className="flex items-center gap-1 text-blue-400">
            <BarChart3 className="h-3 w-3" />
            {rec.screener_score.toFixed(0)} score
          </span>
        )}
      </div>

      {/* Sources */}
      <div className="flex flex-wrap gap-1 mb-1.5">
        {rec.sources.map((src) => (
          <span key={src} className="px-1.5 py-0.5 bg-gray-800 rounded text-[9px] font-mono text-gray-500 border border-gray-700">
            {src}
          </span>
        ))}
      </div>

      {/* Headline */}
      {!compact && rec.headlines.length > 0 && (
        <p className="text-gray-500 text-[10px] line-clamp-1 italic">
          “{rec.headlines[0]}”
        </p>
      )}
    </div>
  );
}

function SectorNewsHeatmap({
  sectors,
  activeSector,
  onSectorClick,
}: {
  sectors: NewsScreenerSectorGroup[];
  activeSector: string | null;
  onSectorClick: (sector: string | null) => void;
}) {
  if (!sectors || sectors.length === 0) return null;

  const maxNews = Math.max(...sectors.map((s) => s.total_news));
  const minNews = Math.min(...sectors.map((s) => s.total_news));
  const range = Math.max(maxNews - minNews, 1);

  // Sort sectors by total_news descending for visual hierarchy
  const sorted = [...sectors].sort((a, b) => b.total_news - a.total_news);

  return (
    <div className="flex flex-wrap gap-1.5">
      {sorted.map((sector) => {
        const style = SECTOR_COLORS[sector.sector] ?? SECTOR_COLORS["Other"];
        const isActive = activeSector === sector.sector;
        const isPos = sector.avg_sentiment > 0.05;
        const isNeg = sector.avg_sentiment < -0.05;

        // Normalize weight: 0.4 (lowest) to 1.5 (highest)
        const weight = 0.4 + ((sector.total_news - minNews) / range) * 1.1;

        // Sentiment color for background overlay
        const sentBg =
          isPos ? "rgba(34, 197, 94, 0.08)" :
          isNeg ? "rgba(239, 68, 68, 0.08)" :
          "rgba(107, 114, 128, 0.04)";

        // Intensity overlay (darker = more news)
        const intensityOverlay = Math.min(0.15 + (sector.total_news / maxNews) * 0.2, 0.35);

        return (
          <button
            key={sector.sector}
            onClick={() => onSectorClick(isActive ? null : sector.sector)}
            title={`${sector.sector}: ${sector.total_news} articles · ${(sector.avg_sentiment * 100).toFixed(0)} sentiment · ${sector.count} stocks`}              className={cn(
              "relative rounded-xl p-2.5 text-left transition-all duration-200 border overflow-hidden",
              isActive
                ? `${style.border} ring-1 ring-offset-1 ring-offset-gray-950`
                : "border-gray-700/40 hover:border-gray-600",
            )}
            style={{
              flex: `${weight} 1 auto`,
              minWidth: "120px",
              background: sentBg,
            }}
          >
            {/* Intensity bar at bottom */}
            <div
              className="absolute bottom-0 left-0 right-0 transition-all"
              style={{
                height: "3px",
                background: isPos
                  ? `rgba(34, 197, 94, ${intensityOverlay})`
                  : isNeg
                    ? `rgba(239, 68, 68, ${intensityOverlay})`
                    : `rgba(107, 114, 128, ${intensityOverlay * 0.5})`,
              }}
            />

            <div className="relative z-10">
              {/* Top row: icon + name */}
              <div className="flex items-center gap-1.5 mb-1">
                <span className="text-xs">{style.icon}</span>
                <span className={cn(
                  "text-[10px] font-bold truncate",
                  isActive ? style.text : "text-gray-300",
                )}>
                  {sector.sector}
                </span>
              </div>

              {/* Middle: news count with sparkline-ish bar */}
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className="text-white font-bold text-sm tabular-nums">
                  {sector.total_news}
                </span>
                <span className="text-[9px] text-gray-500">articles</span>
              </div>

              {/* Bottom: sentiment pill */}
              <span className={cn(
                "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold",
                isPos ? "bg-green-500/15 text-green-400" :
                isNeg ? "bg-red-500/15 text-red-400" :
                "bg-gray-500/15 text-gray-400",
              )}>
                <Activity className="h-2.5 w-2.5" />
                {(sector.avg_sentiment * 100).toFixed(0)}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function SectorGroup({ sector, recs }: { sector: NewsScreenerSectorGroup; recs: NewsScreenerRecommendation[] }) {
  const style = SECTOR_COLORS[sector.sector] ?? SECTOR_COLORS["Other"];
  const isPositive = sector.avg_sentiment > 0.05;

  return (
    <div className="space-y-2">
      {/* Sector header */}
      <div className={cn("flex items-center justify-between px-3 py-2 rounded-xl", style.bg, style.border, "border")}>
        <div className="flex items-center gap-2">
          <span className="text-sm">{style.icon}</span>
          <span className={cn("font-bold text-sm", style.text)}>{sector.sector}</span>
          <span className="text-gray-500 text-xs">({sector.count})</span>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1 text-gray-400">
            <Newspaper className="h-3 w-3" />
            {sector.total_news}
          </span>
          <span className={cn("flex items-center gap-1", isPositive ? "text-green-400" : "text-red-400")}>
            <Activity className="h-3 w-3" />
            {(sector.avg_sentiment * 100).toFixed(0)}
          </span>
        </div>
      </div>

      {/* Cards for this sector */}
      {recs.map((rec) => (
        <ScreenerCard key={rec.symbol} rec={rec} compact />
      ))}
    </div>
  );
}

interface StockSuggestionsProps {
  initialSymbols?: string[];
}

export function StockSuggestions({ initialSymbols }: StockSuggestionsProps) {
  return (
    <Suspense fallback={null}>
      <StockSuggestionsContent initialSymbols={initialSymbols} />
    </Suspense>
  );
}

function StockSuggestionsContent({ initialSymbols }: { initialSymbols?: string[] }) {
  const [showNewsDriven, setShowNewsDriven] = useState(true);
  const [symbolSearch, setSymbolSearch] = useState(
    initialSymbols && initialSymbols.length > 0 ? initialSymbols.join(", ") : ""
  );

  // Sync external symbol filter
  useEffect(() => {
    if (initialSymbols && initialSymbols.length > 0) {
      setSymbolSearch(initialSymbols.join(", "));
    }
  }, [initialSymbols]);

  // Update the filter logic to handle multiple comma-separated symbols
  const filterBySymbols = useCallback((recs: NewsScreenerRecommendation[], search: string) => {
    const trimmed = search.trim();
    if (!trimmed) return recs;
    const symbols = trimmed.toUpperCase().split(/[,\s]+/).filter(Boolean);
    if (symbols.length === 0) return recs;
    return recs.filter((r) => symbols.some((s) => r.symbol.includes(s)));
  }, []);
  const { data: sentiments = [], isLoading: sentLoading } = useBulkSentiment(WATCH_SYMBOLS);
  const { data: quotes = [] } = useMultipleQuotes(WATCH_SYMBOLS);
  const { data: summary, refetch, isFetching } = useMarketSentimentSummary(WATCH_SYMBOLS);

  // Get top bullish and bearish picks from sentiment
  const bullishPicks = (sentiments || [])
    .filter((s: any) => s.label === "bullish" && s.score > 15)
    .sort((a: any, b: any) => b.score - a.score)
    .slice(0, 4);

  const bearishPicks = (sentiments || [])
    .filter((s: any) => s.label === "bearish" && s.score < -15)
    .sort((a: any, b: any) => a.score - b.score)
    .slice(0, 4);

  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const sectorFilter = searchParams.get("sector") || null;
  const setSectorFilter = useCallback((sector: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (sector) {
      params.set("sector", sector);
    } else {
      params.delete("sector");
    }
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }, [searchParams, router, pathname]);

  const [sortBy, setSortBy] = useState<"sentiment" | "news_count" | "screener_score">("screener_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const { data: screenerData, isLoading: screenerLoading, refetch: refetchScreener } = useNewsScreener(
    showNewsDriven ? NEWS_SOURCES_FILTER : undefined
  );

  // Derive filtered sectors and recommendations based on sector filter + symbol search
  const filteredSectors = useMemo(() => {
    if (!screenerData?.sectors) return [];
    if (!sectorFilter) return screenerData.sectors;
    return screenerData.sectors.filter((s) => s.sector === sectorFilter);
  }, [screenerData?.sectors, sectorFilter]);

  const filteredRecommendations = useMemo(() => {
    if (!screenerData?.recommendations) return [];
    let recs = screenerData.recommendations;
    if (sectorFilter) {
      recs = recs.filter((r) => r.sector === sectorFilter);
    }
    // Multi-symbol search: comma or space separated symbols
    if (symbolSearch.trim()) {
      recs = filterBySymbols(recs, symbolSearch);
    }
    // Sort
    const dir = sortDir === "desc" ? -1 : 1;
    recs = [...recs].sort((a, b) => {
      let va: number, vb: number;
      if (sortBy === "sentiment") {
        va = a.avg_sentiment;
        vb = b.avg_sentiment;
      } else if (sortBy === "news_count") {
        va = a.news_count;
        vb = b.news_count;
      } else {
        // screener_score — nulls always go last regardless of direction
        const aScore = a.screener_score;
        const bScore = b.screener_score;
        if (aScore === null && bScore === null) { va = 0; vb = 0; }
        else if (aScore === null) { return 1; }
        else if (bScore === null) { return -1; }
        else { va = aScore; vb = bScore; }
      }
      return va < vb ? dir : va > vb ? -dir : 0;
    });
    return recs;
  }, [screenerData?.recommendations, sectorFilter, symbolSearch, sortBy, sortDir, filterBySymbols]);

  if (sentLoading && screenerLoading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 animate-pulse">
        <div className="h-4 w-36 bg-gray-800 rounded mb-4" />
        <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-12 bg-gray-800 rounded-xl" />)}</div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-purple-400" />
          <h3 className="text-white font-bold text-lg">AI Stock Suggestions</h3>
        </div>
        <button onClick={() => { refetch(); refetchScreener(); }} disabled={isFetching}
          className="h-8 w-8 flex items-center justify-center bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-gray-400 hover:text-white transition-all">
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
        </button>
      </div>

      {/* Market mood bar */}
      {summary && (
        <div className="bg-gray-800 rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-xs font-medium">Market Mood</span>
            <span className={cn("text-xs font-bold", summary.avg_score > 10 ? "text-green-400" : summary.avg_score < -10 ? "text-red-400" : "text-gray-400")}>
              {summary.avg_score > 0 ? "+" : ""}{Math.round(summary.avg_score)}
            </span>
          </div>
          <div className="flex h-2 rounded-full overflow-hidden">
            <div className="bg-green-500 transition-all" style={{ width: `${(summary.bullish_count / Math.max(summary.total, 1)) * 100}%` }} />
            <div className="bg-gray-600" style={{ width: `${(summary.neutral_count / Math.max(summary.total, 1)) * 100}%` }} />
            <div className="bg-red-500" style={{ width: `${(summary.bearish_count / Math.max(summary.total, 1)) * 100}%` }} />
          </div>
          <div className="flex justify-between text-[10px] text-gray-600 mt-1">
            <span className="text-green-500">{summary.bullish_count} Bullish</span>
            <span className="text-gray-500">{summary.neutral_count} Neutral</span>
            <span className="text-red-500">{summary.bearish_count} Bearish</span>
          </div>
        </div>
      )}

      {/* Bullish picks */}
      {bullishPicks.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingUp className="h-3.5 w-3.5 text-green-400" />
            <span className="text-green-400 text-xs font-bold uppercase tracking-wide">Bullish Signals</span>
          </div>
          <div className="space-y-2">
            {bullishPicks.map((s: any) => {
              const quote = quotes.find((q: any) => q.symbol === s.symbol);
              return (
                <div key={s.symbol} className="bg-gray-800/60 border border-green-500/15 rounded-xl p-3 hover:bg-gray-800 transition-all">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-bold text-sm">{s.symbol}</span>
                      {quote && (
                        <span className="text-gray-400 text-xs">₹{quote.ltp?.toLocaleString("en-IN")}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <ArrowUpRight className="h-3 w-3 text-green-400" />
                      <span className="text-green-400 text-xs font-bold">+{s.score}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <SentimentScore score={s.score} size="sm" />
                    </div>
                    <span className="text-[10px] text-gray-500">{s.confidence}% confidence</span>
                  </div>
                  {s.explanation && (
                    <p className="text-gray-500 text-[10px] mt-1.5 line-clamp-1">{s.explanation}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bearish picks */}
      {bearishPicks.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingDown className="h-3.5 w-3.5 text-red-400" />
            <span className="text-red-400 text-xs font-bold uppercase tracking-wide">Bearish Signals</span>
          </div>
          <div className="space-y-2">
            {bearishPicks.map((s: any) => {
              const quote = quotes.find((q: any) => q.symbol === s.symbol);
              return (
                <div key={s.symbol} className="bg-gray-800/60 border border-red-500/15 rounded-xl p-3 hover:bg-gray-800 transition-all">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-bold text-sm">{s.symbol}</span>
                      {quote && (
                        <span className="text-gray-400 text-xs">₹{quote.ltp?.toLocaleString("en-IN")}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <ArrowDownLeft className="h-3 w-3 text-red-400" />
                      <span className="text-red-400 text-xs font-bold">{s.score}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <SentimentScore score={s.score} size="sm" />
                    </div>
                    <span className="text-[10px] text-gray-500">{s.confidence}% confidence</span>
                  </div>
                  {s.explanation && (
                    <p className="text-gray-500 text-[10px] mt-1.5 line-clamp-1">{s.explanation}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* No signals */}
      {bullishPicks.length === 0 && bearishPicks.length === 0 && (
        <div className="text-center py-8">
          <Activity className="h-8 w-8 text-gray-700 mx-auto mb-2" />
          <p className="text-gray-500 text-sm font-medium">No strong signals right now</p>
          <p className="text-gray-600 text-xs mt-1">Market sentiment is mostly neutral. Check back later.</p>
        </div>
      )}

      {/* ── News-Driven Stock Screener ──────────────────────────── */}
      <div className="border-t border-gray-800 pt-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-cyan-400" />
            <h4 className="text-white font-bold text-base">News-Driven Picks</h4>
          </div>
          <button onClick={() => setShowNewsDriven(!showNewsDriven)}
            className={cn("px-2.5 py-1 rounded-lg border text-[10px] font-semibold transition-all uppercase tracking-wider",
              showNewsDriven
                ? "bg-cyan-600/20 border-cyan-500 text-cyan-400"
                : "bg-gray-800 border-gray-700 text-gray-500"
            )}>
            {showNewsDriven ? "From Geo Sources" : "Disabled"}
          </button>
        </div>
        <p className="text-gray-600 text-xs mb-3">
          Stocks mentioned in geopolitical/foreign policy news, ranked by news coverage and technical scores.
        </p>

        {screenerLoading ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <div key={i} className="h-20 bg-gray-800 rounded-xl animate-pulse" />)}
          </div>
        ) : symbolSearch && filteredRecommendations.length === 0 ? (
          <div className="text-center py-6 bg-gray-900 rounded-xl border border-gray-800">
            <Search className="h-6 w-6 text-gray-700 mx-auto mb-2" />
            <p className="text-gray-500 text-xs font-medium">No symbols match &ldquo;{symbolSearch}&rdquo;</p>
            <button onClick={() => setSymbolSearch("")} className="text-cyan-400 text-[10px] mt-1 underline hover:text-cyan-300 transition-colors">
              Clear search
            </button>
          </div>
        ) : filteredRecommendations.length > 0 ? (
          <div className="space-y-4">
            {/* ── Sector News Heatmap ────────────────────── */}
            {screenerData?.sectors && screenerData.sectors.length > 1 && (
              <div className="bg-gray-900/50 rounded-xl p-3 border border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Grid3X3 className="h-3.5 w-3.5 text-gray-500" />
                    <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">
                      Sector News Heatmap
                    </span>
                  </div>
                  {/* Legend */}
                  <div className="flex items-center gap-2 text-[8px] text-gray-600">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-sm bg-green-500/30" /> Positive
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-sm bg-gray-500/20" /> Neutral
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-sm bg-red-500/30" /> Negative
                    </span>
                  </div>
                </div>
                <SectorNewsHeatmap
                  sectors={screenerData.sectors}
                  activeSector={sectorFilter}
                  onSectorClick={setSectorFilter}
                />
                <div className="flex items-center justify-between mt-1.5 text-[8px] text-gray-600">
                  <span>Tile size ∝ news coverage · bar color = sentiment</span>
                  <span>Click to filter by sector</span>
                </div>
              </div>
            )}

            {/* Symbol search + Sort controls */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500 pointer-events-none" />
                <input
                  value={symbolSearch}
                  onChange={(e) => setSymbolSearch(e.target.value)}
                  placeholder="Search by symbol..."
                  className="w-full pl-8 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/20 transition-all"
                />
                {symbolSearch && (
                  <button
                    onClick={() => setSymbolSearch("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-[10px] font-semibold"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* Sort toggle */}
              <div className="flex items-center gap-0.5 bg-gray-800 border border-gray-700 rounded-xl p-0.5 shrink-0">
                {([
                  { key: "sentiment" as const, label: "Sentiment" },
                  { key: "news_count" as const, label: "News" },
                  { key: "screener_score" as const, label: "Score" },
                ]).map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => {
                      if (sortBy === key) {
                        setSortDir((d) => (d === "desc" ? "asc" : "desc"));
                      } else {
                        setSortBy(key);
                        setSortDir("desc");
                      }
                    }}
                    className={cn(
                      "flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-semibold transition-all whitespace-nowrap",
                      sortBy === key
                        ? "bg-gray-700 text-white"
                        : "text-gray-500 hover:text-gray-300"
                    )}
                  >
                    {label}
                    {sortBy === key && (
                      sortDir === "desc"
                        ? <ArrowDown className="h-3 w-3" />
                        : <ArrowUp className="h-3 w-3" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Sector filter chips */}
            {screenerData?.sectors && screenerData.sectors.length > 1 && (
              <div>
                <div className="flex flex-wrap gap-1.5 items-center">
                  <Layers className="h-3.5 w-3.5 text-gray-500 flex-shrink-0" />
                  {/* All sectors toggle */}
                  <button onClick={() => setSectorFilter(null)}
                    className={cn("px-2 py-0.5 rounded-full text-[9px] font-semibold border transition-all",
                      !sectorFilter
                        ? "bg-cyan-600/20 border-cyan-500 text-cyan-400"
                        : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300"
                    )}>
                    All
                  </button>
                  {screenerData.sectors.map((sector: NewsScreenerSectorGroup) => {
                    const style = SECTOR_COLORS[sector.sector] ?? SECTOR_COLORS["Other"];
                    const isActive = sectorFilter === sector.sector;
                    return (
                      <button key={sector.sector} onClick={() => setSectorFilter(isActive ? null : sector.sector)}
                        className={cn("px-2 py-0.5 rounded-full text-[9px] font-semibold border transition-all",
                          isActive
                            ? `${style.border} ${style.text} ${style.bg} ring-1 ring-offset-1 ring-offset-gray-950`
                            : "border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600 bg-gray-800"
                        )}>
                        {style.icon} {sector.sector} · {sector.count}
                      </button>
                    );
                  })}
                </div>
                {/* Active filter indicator */}
                {sectorFilter && (
                  <p className="text-[10px] text-cyan-400/70 mt-1.5">
                    Showing only <span className="font-semibold">{sectorFilter}</span> picks
                    <button onClick={() => setSectorFilter(null)} className="ml-1.5 underline hover:text-cyan-300">
                      clear
                    </button>
                  </p>
                )}
              </div>
            )}

            {/* Grouped by sector (filtered) */}
            {filteredSectors.length === 0 ? (
              <div className="text-center py-6 bg-gray-900 rounded-xl border border-gray-800">
                <p className="text-gray-500 text-xs font-medium">No picks in this sector</p>
              </div>
            ) : (
              filteredSectors.map((sector: NewsScreenerSectorGroup) => {
                const sectorRecs = filteredRecommendations.filter(
                  (r: NewsScreenerRecommendation) => r.sector === sector.sector
                );
                if (sectorRecs.length === 0) return null;
                return <SectorGroup key={sector.sector} sector={sector} recs={sectorRecs} />;
              })
            )}

            <p className="text-gray-700 text-[10px] text-center pt-1">
              {sectorFilter
                ? `${filteredRecommendations.length} symbols in ${sectorFilter}`
                : `${screenerData?.symbols_analyzed ?? 0} symbols across ${screenerData?.sectors?.length ?? 0} sectors from ${screenerData?.news_count ?? 0} articles`
              }
            </p>
          </div>
        ) : (
          <div className="text-center py-6 bg-gray-900 rounded-xl border border-gray-800">
            <Globe className="h-6 w-6 text-gray-700 mx-auto mb-2" />
            <p className="text-gray-500 text-xs font-medium">No news-driven picks yet</p>
            <p className="text-gray-600 text-[10px] mt-1">Waiting for geopolitical news to arrive...</p>
          </div>
        )}
      </div>

      {/* Action hint */}
      <p className="text-gray-700 text-[10px] text-center">
        AI-powered sentiment analysis + news-driven stock screener · Not financial advice
      </p>
    </div>
  );
}
