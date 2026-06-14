"use client";
// 7-day historical trends for the Geopolitical Monitor dashboard.
// Path: frontend/src/app/geo-monitor/HistoricalTrends.tsx
import { useMemo } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────
interface DaySnapshot {
  date: string;
  article_count: number;
  avg_sentiment: number;
  active_regions: number;
  mentioned_stocks: number;
  sectors_affected: number;
}

interface Delta {
  current: number;
  previous: number;
  change_pct: number;
}

interface HistoryDeltas {
  articles: Delta;
  sentiment: Delta;
  regions: Delta;
  sectors: Delta;
  stocks: Delta;
}

export interface HistoryData {
  days: DaySnapshot[];
  deltas: HistoryDeltas;
  total_articles_7d: number;
}

// ── Custom Tooltip ────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload) return null;
  return (
    <div className="bg-gray-900/95 border border-gray-700 rounded-xl p-3 shadow-xl backdrop-blur-sm">
      <p className="text-gray-400 text-[10px] mb-1.5 font-medium">
        {new Date(label).toLocaleDateString("en-IN", { weekday: "short", month: "short", day: "numeric" })}
      </p>
      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-gray-500">{entry.name}:</span>
          <span className="text-white font-semibold">
            {typeof entry.value === "number" ? entry.value.toFixed(1) : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Delta Badge ──────────────────────────────────────────────
function DeltaBadge({ delta }: { delta: Delta }) {
  const isUp = delta.change_pct > 0;
  const isDown = delta.change_pct < 0;
  return (
    <span className={cn(
      "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-semibold",
      isUp ? "bg-green-500/15 text-green-400" : isDown ? "bg-red-500/15 text-red-400" : "bg-gray-500/15 text-gray-400",
    )}>
      {isUp ? <TrendingUp className="h-2.5 w-2.5" /> : isDown ? <TrendingDown className="h-2.5 w-2.5" /> : <Minus className="h-2.5 w-2.5" />}
      {delta.current.toFixed(1)}
      <span className="opacity-70">({delta.change_pct > 0 ? "+" : ""}{delta.change_pct.toFixed(0)}%)</span>
    </span>
  );
}

// ── Main Component ───────────────────────────────────────────
interface HistoricalTrendsProps {
  data: HistoryData;
}

export function HistoricalTrends({ data }: HistoricalTrendsProps) {
  const { days, deltas } = data;

  // Format dates for display
  const chartData = useMemo(() => days.map((d) => ({
    ...d,
    dateLabel: new Date(d.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric" }),
    sentimentDisplay: +(d.avg_sentiment * 100).toFixed(0),
  })), [days]);

  if (chartData.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 md:p-5">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-cyan-400" />
          <h3 className="text-white font-bold">7-Day Historical Trends</h3>
          <span className="text-gray-500 text-xs">{data.total_articles_7d} total articles</span>
        </div>
      </div>

      {/* ── Delta Summary Row ── */}
      <div className="flex flex-wrap gap-2 mb-4 pb-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">Articles</span>
          <DeltaBadge delta={deltas.articles} />
        </div>
        <div className="w-px h-4 bg-gray-800" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">Sentiment</span>
          <DeltaBadge delta={deltas.sentiment} />
        </div>
        <div className="w-px h-4 bg-gray-800" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">Regions</span>
          <DeltaBadge delta={deltas.regions} />
        </div>
        <div className="w-px h-4 bg-gray-800" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">Sectors</span>
          <DeltaBadge delta={deltas.sectors} />
        </div>
        <div className="w-px h-4 bg-gray-800" />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">Stocks</span>
          <DeltaBadge delta={deltas.stocks} />
        </div>
      </div>

      {/* ── Dual Charts ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Article Volume Line */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">Article Volume</span>
            <span className="text-white text-xs font-bold tabular-nums">
              {deltas.articles.current.toFixed(0)}
              <span className="text-gray-500 text-[10px] ml-1">today</span>
            </span>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="volumeGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="dateLabel" tick={{ fill: "#6b7280", fontSize: 9 }} tickLine={false} axisLine={false} interval={0} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="article_count" stroke="#22d3ee" strokeWidth={2} fill="url(#volumeGrad)" name="Articles" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Sentiment Line */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">Avg Sentiment</span>
            <span className="text-white text-xs font-bold tabular-nums">
              {(deltas.sentiment.current * 100).toFixed(0)}
              <span className="text-gray-500 text-[10px] ml-1">today</span>
            </span>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="dateLabel" tick={{ fill: "#6b7280", fontSize: 9 }} tickLine={false} axisLine={false} interval={0} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} tickLine={false} axisLine={false} domain={[-100, 100]} />
              <Tooltip content={<ChartTooltip />} />
              {/* Zero line */}
              <CartesianGrid horizontalPoints={[0]} stroke="#374151" strokeDasharray="2 2" />
              <Line
                type="monotone" dataKey="sentimentDisplay" stroke="#a78bfa" strokeWidth={2}
                dot={{ r: 3, fill: "#a78bfa", strokeWidth: 0 }}
                activeDot={{ r: 5, fill: "#a78bfa", strokeWidth: 2, stroke: "#1f2937" }}
                name="Sentiment"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Regions + Stocks multi-line */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">Coverage Breadth</span>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="dateLabel" tick={{ fill: "#6b7280", fontSize: 9 }} tickLine={false} axisLine={false} interval={0} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: "9px", color: "#9ca3af" }} />
              <Line type="monotone" dataKey="active_regions" stroke="#f59e0b" strokeWidth={2} dot={{ r: 2 }} name="Regions" />
              <Line type="monotone" dataKey="sectors_affected" stroke="#10b981" strokeWidth={2} dot={{ r: 2 }} name="Sectors" />
              <Line type="monotone" dataKey="mentioned_stocks" stroke="#f472b6" strokeWidth={2} dot={{ r: 2 }} name="Stocks" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Weekly context */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3 flex flex-col justify-center">
          <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mb-3">Weekly Summary</span>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Avg daily articles</span>
              <span className="text-white font-semibold">
                {(data.total_articles_7d / Math.max(chartData.length, 1)).toFixed(0)}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Most active day</span>
              <span className="text-cyan-400 font-semibold">
                {chartData.reduce((max, d) => d.article_count > (max.article_count || 0) ? d : max, chartData[0])?.dateLabel || "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Peak article count</span>
              <span className="text-white font-semibold">
                {Math.max(...chartData.map((d) => d.article_count))}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Peak regions</span>
              <span className="text-white font-semibold">
                {Math.max(...chartData.map((d) => d.active_regions))}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
