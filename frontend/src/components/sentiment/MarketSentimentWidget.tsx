"use client";
// Path: frontend/src/components/sentiment/MarketSentimentWidget.tsx
import { TrendingUp, TrendingDown, Minus, RefreshCw, Loader2 } from "lucide-react";
import { useMarketSentimentSummary } from "@/hooks/useSentiment";
import { cn } from "@/lib/utils";

const DEFAULT_SYMBOLS = ["RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","WIPRO","BAJFINANCE","TATAMOTORS","NIFTY50"];

function MoodGauge({ score }: { score: number }) {
  const pct   = Math.round((score + 100) / 2);
  const color = score > 15 ? "#22c55e" : score < -15 ? "#ef4444" : "#eab308";
  const label = score > 30 ? "Greedy" : score > 10 ? "Optimistic" : score < -30 ? "Fearful" : score < -10 ? "Cautious" : "Neutral";
  return (
    <div className="text-center">
      <svg viewBox="0 0 120 70" className="w-32 mx-auto">
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="#1f2937" strokeWidth="10" strokeLinecap="round" />
        <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${pct * 1.57} 157`} style={{ transition: "stroke-dasharray 1s ease" }} />
        <text x="60" y="58" textAnchor="middle" fill="white" fontSize="16" fontWeight="bold">
          {score > 0 ? "+" : ""}{score}
        </text>
      </svg>
      <p className="text-sm font-semibold mt-1" style={{ color }}>{label}</p>
    </div>
  );
}

export function MarketSentimentWidget({ symbols = DEFAULT_SYMBOLS }: { symbols?: string[] }) {
  const { data, isLoading, refetch, isFetching } = useMarketSentimentSummary(symbols);

  if (isLoading) return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 animate-pulse">
      <div className="h-5 w-40 bg-gray-800 rounded mb-4" />
      <div className="h-32 bg-gray-800 rounded-xl mb-4" />
      <div className="grid grid-cols-3 gap-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-gray-800 rounded-xl" />)}</div>
    </div>
  );

  if (!data) return null;

  const total   = data.total || 1;
  const bullPct = Math.round((data.bullish_count / total) * 100);
  const bearPct = Math.round((data.bearish_count / total) * 100);
  const neutPct = 100 - bullPct - bearPct;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-bold">Market Mood</h3>
        <button onClick={() => refetch()} disabled={isFetching} className="text-gray-500 hover:text-white transition-colors">
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </button>
      </div>

      <div className="flex justify-center mb-4">
        <MoodGauge score={Math.round(data.avg_score)} />
      </div>

      <div className="flex h-2.5 rounded-full overflow-hidden mb-4">
        <div className="bg-green-500 transition-all duration-700" style={{ width: `${bullPct}%` }} title={`${data.bullish_count} bullish`} />
        <div className="bg-gray-600 transition-all duration-700" style={{ width: `${neutPct}%` }} title={`${data.neutral_count} neutral`} />
        <div className="bg-red-500 transition-all duration-700"   style={{ width: `${bearPct}%` }} title={`${data.bearish_count} bearish`} />
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { label: "Bullish", count: data.bullish_count, pct: bullPct, color: "text-green-400", bg: "bg-green-500/10", icon: TrendingUp },
          { label: "Neutral", count: data.neutral_count, pct: neutPct, color: "text-gray-400",  bg: "bg-gray-500/10",  icon: Minus },
          { label: "Bearish", count: data.bearish_count, pct: bearPct, color: "text-red-400",   bg: "bg-red-500/10",   icon: TrendingDown },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className={cn("rounded-xl p-3 text-center", item.bg)}>
              <Icon className={cn("h-4 w-4 mx-auto mb-1", item.color)} />
              <p className={cn("text-lg font-black leading-none", item.color)}>{item.count}</p>
              <p className="text-gray-500 text-[10px] mt-0.5">{item.label}</p>
              <p className={cn("text-[10px] font-bold", item.color)}>{item.pct}%</p>
            </div>
          );
        })}
      </div>

      {(data.top_bullish || data.top_bearish) && (
        <div className="space-y-2">
          {data.top_bullish && (
            <div className="flex items-center justify-between bg-green-500/5 border border-green-500/15 rounded-xl px-3 py-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-3.5 w-3.5 text-green-400" />
                <span className="text-green-400 text-sm font-bold">{data.top_bullish.symbol}</span>
                <span className="text-gray-500 text-xs">Most bullish</span>
              </div>
              <span className="text-green-400 font-bold text-sm">+{data.top_bullish.score}</span>
            </div>
          )}
          {data.top_bearish && (
            <div className="flex items-center justify-between bg-red-500/5 border border-red-500/15 rounded-xl px-3 py-2">
              <div className="flex items-center gap-2">
                <TrendingDown className="h-3.5 w-3.5 text-red-400" />
                <span className="text-red-400 text-sm font-bold">{data.top_bearish.symbol}</span>
                <span className="text-gray-500 text-xs">Most bearish</span>
              </div>
              <span className="text-red-400 font-bold text-sm">{data.top_bearish.score}</span>
            </div>
          )}
        </div>
      )}
      <p className="text-gray-700 text-[10px] text-center mt-3">
        {data.total} stocks · AI analysis · Updates every 15 min
      </p>
    </div>
  );
}
