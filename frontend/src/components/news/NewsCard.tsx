"use client";
// Path: frontend/src/components/news/NewsCard.tsx
import { useState } from "react";
import Image from "next/image";
import { ExternalLink, Clock, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";
import type { NewsArticle } from "@/types";
import { CATEGORY_COLORS } from "@/types";

function SentimentIcon({ score }: { score: number }) {
  if (score > 0.1)  return <TrendingUp   className="h-3.5 w-3.5 text-green-400" />;
  if (score < -0.1) return <TrendingDown className="h-3.5 w-3.5 text-red-400"   />;
  return                    <Minus        className="h-3.5 w-3.5 text-gray-400"  />;
}

interface NewsCardProps { article: NewsArticle; onSymbolClick?: (symbol: string) => void; }

export function NewsCard({ article, onSymbolClick }: NewsCardProps) {
  const [imgError, setImgError] = useState(false);
  const catColor  = CATEGORY_COLORS[article.category] ?? CATEGORY_COLORS.neutral;
  const confPct   = Math.round(article.confidence * 100);
  const barOffset = 50 + article.sentiment_score * 50;
  const isPos     = article.sentiment_score >= 0;
  const barColor  = article.sentiment_score > 0.1 ? "bg-green-500" : article.sentiment_score < -0.1 ? "bg-red-500" : "bg-gray-500";

  return (
    <a href={article.url} target="_blank" rel="noreferrer noopener"
      className="block bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden hover:border-gray-600 transition-all duration-200 group">
      {article.image_url && !imgError && (
        <div className="h-32 overflow-hidden relative">
          <Image src={article.image_url} alt={article.title} fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            onError={() => setImgError(true)} />
        </div>
      )}
      <div className="p-4">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide", catColor)}>
              {article.category}
            </span>
            <span className="text-gray-600 text-xs">{article.source}</span>
          </div>
          <div className="flex items-center gap-1 text-gray-600 text-xs">
            <Clock className="h-3 w-3" />
            {formatDistanceToNow(new Date(article.published_at), { addSuffix: true })}
          </div>
        </div>

        <h3 className="text-white text-sm font-semibold leading-snug mb-2 group-hover:text-blue-300 transition-colors line-clamp-2">
          {article.title}
        </h3>

        {article.summary && (
          <p className="text-gray-500 text-xs leading-relaxed line-clamp-2 mb-3">{article.summary}</p>
        )}

        {article.ai_summary && (
          <div className="bg-blue-500/5 border border-blue-500/15 rounded-xl px-3 py-2 mb-3">
            <p className="text-blue-300 text-xs leading-relaxed">🤖 {article.ai_summary}</p>
          </div>
        )}

        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <div className="flex items-center gap-1">
              <SentimentIcon score={article.sentiment_score} />
              <span className={cn("font-medium", article.sentiment_score > 0.1 ? "text-green-400" : article.sentiment_score < -0.1 ? "text-red-400" : "text-gray-400")}>
                {article.sentiment_score > 0.1 ? "Bullish" : article.sentiment_score < -0.1 ? "Bearish" : "Neutral"}
              </span>
            </div>
            <span className="text-gray-600">{confPct}% confidence</span>
          </div>
          <div className="h-1 bg-gray-800 rounded-full relative overflow-hidden">
            <div className="absolute top-0 bottom-0 w-px bg-gray-600" style={{ left: "50%" }} />
            <div className={cn("absolute h-full rounded-full transition-all", barColor)}
              style={{ left: isPos ? "50%" : `${barOffset}%`, right: isPos ? `${100 - barOffset}%` : "50%" }} />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-1">
            {article.symbols.slice(0, 4).map((s) => (
              <button
                key={s}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onSymbolClick?.(s);
                }}
                className="px-2 py-0.5 bg-gray-800 border border-gray-700 rounded-full text-[10px] font-mono text-gray-400 hover:text-cyan-400 hover:border-cyan-500/50 hover:bg-cyan-500/10 transition-all"
                title={`View ${s} in stock screener`}
              >
                {s}
              </button>
            ))}
          </div>
          <ExternalLink className="h-3.5 w-3.5 text-gray-600 group-hover:text-gray-400 transition-colors flex-shrink-0" />
        </div>
      </div>
    </a>
  );
}
