"use client";
// Path: frontend/src/components/news/NewsImpactPanel.tsx
// Phase 5 — Affected stocks panel. Calls /news/impact and renders per-article impact summary.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Newspaper, TrendingUp, TrendingDown, Activity, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface ImpactItem {
  id: string; headline: string; source: string; url: string; published_at: string;
  category: string; impact_direction: "positive" | "negative" | "neutral"; confidence: number;
  sentiment_score: number; affected_stocks: string[]; affected_sectors: string[];
  opportunity_summary: string;
  ai_powered?: boolean; ai_provider?: string; ai_model?: string;
}
interface Resp {
  articles_analyzed: number;
  ai_analyzed?: number;
  items: ImpactItem[];
  top_stocks: { symbol: string; mentions: number }[];
  top_sectors: { sector: string; mentions: number }[];
  no_live_data: boolean;
}

const DIR: Record<string, { bg: string; text: string; label: string; icon: any }> = {
  positive: { bg: "bg-emerald-500/10 border-emerald-500/30", text: "text-emerald-300", label: "Positive", icon: TrendingUp },
  negative: { bg: "bg-red-500/10 border-red-500/30",         text: "text-red-300",     label: "Negative", icon: TrendingDown },
  neutral:  { bg: "bg-gray-700/30 border-gray-600/30",        text: "text-gray-300",    label: "Neutral",  icon: Activity },
};

export function NewsImpactPanel() {
  const { data, isLoading, refetch, isFetching } = useQuery<Resp>({
    queryKey: ["news-impact"],
    queryFn: () => api.get("/news/impact", { params: { limit: 30 } }).then((r) => r.data),
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-5" data-testid="news-impact-panel">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <p className="text-[11px] font-bold text-amber-300 uppercase tracking-widest">News Impact Analysis</p>
          <p className="text-gray-500 text-xs mt-1">
            {data?.articles_analyzed ?? 0} articles analysed
            {data?.ai_analyzed ? <> · <span className="text-emerald-400 font-semibold">{data.ai_analyzed} AI-powered</span></> : null}
            {" "}· sentiment + sector + stock impact
          </p>
        </div>
        <button onClick={() => refetch()} disabled={isFetching} data-testid="news-impact-refresh"
          className="inline-flex items-center gap-2 px-3 py-2 bg-gray-900 border border-gray-800 hover:border-amber-500/40 text-white rounded-lg text-xs font-semibold disabled:opacity-50">
          <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} /> Refresh
        </button>
      </div>

      {/* Rollup pills */}
      {data && (data.top_stocks.length > 0 || data.top_sectors.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4" data-testid="news-impact-top-stocks">
            <p className="text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-3">Most mentioned stocks</p>
            <div className="flex flex-wrap gap-1.5">
              {data.top_stocks.map((s) => (
                <span key={s.symbol} className="px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/25 text-amber-200 text-xs font-bold">
                  {s.symbol} <span className="text-amber-400/60">×{s.mentions}</span>
                </span>
              ))}
            </div>
          </div>
          <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4" data-testid="news-impact-top-sectors">
            <p className="text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-3">Affected sectors</p>
            <div className="flex flex-wrap gap-1.5">
              {data.top_sectors.map((s) => (
                <span key={s.sector} className="px-2.5 py-1 rounded-md bg-sky-500/10 border border-sky-500/25 text-sky-200 text-xs font-bold">
                  {s.sector} <span className="text-sky-400/60">×{s.mentions}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Item cards */}
      <div className="space-y-3" data-testid="news-impact-list">
        {isLoading && <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-10 text-center text-gray-500 text-sm">Analyzing news…</div>}
        {!isLoading && (!data || data.no_live_data) && (
          <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-10 text-center text-gray-500 text-sm" data-testid="news-impact-empty">No live data available.</div>
        )}
        {data?.items.map((it) => {
          const meta = DIR[it.impact_direction];
          const Icon = meta.icon;
          return (
            <div key={it.id} className={cn("rounded-2xl border p-4 transition-all", meta.bg)} data-testid={`news-impact-item-${it.id}`}>
              <div className="flex items-start gap-3">
                <div className={cn("h-8 w-8 rounded-lg bg-gray-950 flex items-center justify-center flex-shrink-0", meta.text)}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={cn("text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded", meta.text)}>{meta.label}</span>
                    <span className="text-[10px] font-bold uppercase text-gray-500 tracking-wider">{it.source}</span>
                    <span className="text-[10px] text-gray-600">{new Date(it.published_at).toLocaleString("en-IN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" })}</span>
                    <span className="text-[10px] font-bold uppercase text-amber-300/80 tracking-wider">{it.confidence}% confidence</span>
                    {it.ai_powered && (
                      <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" data-testid={`news-impact-ai-badge-${it.id}`}>
                        AI · {it.ai_provider ?? "model"}
                      </span>
                    )}
                  </div>
                  <a href={it.url} target="_blank" rel="noreferrer" className="text-white font-bold text-sm hover:text-amber-300 transition-colors line-clamp-2">
                    {it.headline}
                  </a>
                  <p className="text-gray-400 text-xs mt-2 leading-relaxed">{it.opportunity_summary}</p>
                  {(it.affected_stocks.length > 0 || it.affected_sectors.length > 0) && (
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {it.affected_stocks.map((s) => (
                        <span key={s} className="px-2 py-0.5 rounded bg-gray-900 border border-gray-800 text-gray-200 text-[11px] font-bold">{s}</span>
                      ))}
                      {it.affected_sectors.map((s) => (
                        <span key={s} className="px-2 py-0.5 rounded bg-amber-500/5 border border-amber-500/20 text-amber-300/80 text-[11px] font-semibold uppercase tracking-wider">{s}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
