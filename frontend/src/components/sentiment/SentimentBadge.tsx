"use client";
// Path: frontend/src/components/sentiment/SentimentBadge.tsx
import { useState } from "react";
import { TrendingUp, TrendingDown, Minus, RefreshCw, Loader2 } from "lucide-react";
import { useSentiment, useRefreshSentiment } from "@/hooks/useSentiment";
import { cn } from "@/lib/utils";
import type { SentimentLabel } from "@/types";
import { SENTIMENT_COLORS } from "@/types";

function Icon({ label }: { label: SentimentLabel }) {
  if (label === "bullish") return <TrendingUp   className="h-3.5 w-3.5" />;
  if (label === "bearish") return <TrendingDown className="h-3.5 w-3.5" />;
  return                          <Minus        className="h-3.5 w-3.5" />;
}

function TooltipContent({ symbol }: { symbol: string }) {
  const { data, isLoading } = useSentiment(symbol);
  const refresh = useRefreshSentiment();

  if (isLoading) return (
    <div className="flex items-center gap-2 p-3">
      <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
      <span className="text-xs text-gray-400">Analyzing...</span>
    </div>
  );

  if (!data) return <p className="text-xs text-gray-500 p-3">No data available</p>;

  const pct = ((data.score + 100) / 2);
  const barColor = data.label === "bullish" ? "bg-green-500" : data.label === "bearish" ? "bg-red-500" : "bg-gray-500";

  return (
    <div className="w-64 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-white font-bold text-sm">{data.symbol} Sentiment</span>
        <button onClick={(e) => { e.stopPropagation(); refresh.mutate(symbol); }}
          className="text-gray-500 hover:text-white transition-colors" title="Refresh">
          <RefreshCw className={cn("h-3.5 w-3.5", refresh.isPending && "animate-spin")} />
        </button>
      </div>

      <div className="text-center">
        <p className={cn("text-3xl font-black",
          data.label === "bullish" ? "text-green-400" : data.label === "bearish" ? "text-red-400" : "text-gray-400")}>
          {data.score > 0 ? "+" : ""}{data.score}
        </p>
        <p className="text-gray-500 text-xs">out of ±100</p>
      </div>

      <div className="relative h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className="absolute top-0 bottom-0 w-px bg-gray-500" style={{ left: "50%" }} />
        <div className={cn("absolute h-full rounded-full transition-all", barColor)}
          style={{ left: data.score >= 0 ? "50%" : `${pct}%`, right: data.score >= 0 ? `${100 - pct}%` : "50%" }} />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-gray-800 rounded-lg p-2">
          <p className="text-gray-500">Confidence</p>
          <p className="text-white font-bold">{data.confidence}%</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-2">
          <p className="text-gray-500">Articles</p>
          <p className="text-white font-bold">{data.news_count}</p>
        </div>
      </div>

      {data.explanation && (
        <p className="text-gray-400 text-xs leading-relaxed">{data.explanation}</p>
      )}

      {data.headlines && data.headlines.length > 0 && (
        <div>
          <p className="text-gray-500 text-[10px] font-semibold uppercase mb-1">Recent Headlines</p>
          <ul className="space-y-1">
            {data.headlines.slice(0, 2).map((h, i) => (
              <li key={i} className="text-gray-500 text-[11px] leading-snug line-clamp-2">· {h}</li>
            ))}
          </ul>
        </div>
      )}

      {data.cached_at && (
        <p className="text-gray-700 text-[10px] text-right">
          Updated {new Date(data.cached_at).toLocaleTimeString("en-IN")}
        </p>
      )}
    </div>
  );
}

interface Props { symbol: string; size?: "sm" | "md" | "lg"; showTooltip?: boolean; }

export function SentimentBadge({ symbol, size = "md", showTooltip = true }: Props) {
  const [tooltipOpen, setTooltip] = useState(false);
  const { data, isLoading } = useSentiment(symbol);

  if (isLoading) return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-800 rounded-full border border-gray-700 animate-pulse">
      <div className="h-3.5 w-3.5 rounded-full bg-gray-700" />
      <div className="h-3 w-12 bg-gray-700 rounded" />
    </div>
  );

  if (!data) return null;

  const colorClass = SENTIMENT_COLORS[data.label];
  const sizeClass  = size === "sm" ? "text-[10px] px-2 py-0.5" : size === "lg" ? "text-sm px-3.5 py-1.5" : "text-xs px-2.5 py-1";

  return (
    <div className="relative inline-block">
      <span
        role={showTooltip ? "button" : undefined}
        tabIndex={showTooltip ? 0 : undefined}
        onMouseEnter={() => showTooltip && setTooltip(true)}
        onMouseLeave={() => setTooltip(false)}
        className={cn("inline-flex items-center gap-1.5 rounded-full border font-semibold transition-all",
          showTooltip && "cursor-pointer hover:opacity-80",
          !showTooltip && "cursor-default",
          colorClass, sizeClass)}>
        <Icon label={data.label} />
        <span className="capitalize">{data.label}</span>
        <span className="opacity-70">({data.score > 0 ? "+" : ""}{data.score})</span>
      </span>

      {showTooltip && tooltipOpen && (
        <div className="absolute z-50 bottom-full mb-2 left-1/2 -translate-x-1/2 bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl animate-fade-in">
          <TooltipContent symbol={symbol} />
        </div>
      )}
    </div>
  );
}
