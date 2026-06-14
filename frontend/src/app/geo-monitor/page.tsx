"use client";
import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow, format } from "date-fns";
import {
  Globe, Newspaper, RefreshCw, Loader2, Search, X, Download,
  Clock, ExternalLink, BarChart3, ArrowUp, ArrowDown, ArrowUpDown, ChevronLeft, ChevronRight,
  Shield, Layers, MapPin, Gauge,
} from "lucide-react";
import WorldMap from "./WorldMap";
import { HistoricalTrends } from "./HistoricalTrends";
import type { HistoryData } from "./HistoricalTrends";

// ── Types ─────────────────────────────────────────────────────
interface RiskComponents {
  news_volume: number;
  sentiment_risk: number;
  sector_breadth: number;
  region_spread: number;
}

interface RiskDetails {
  total_articles: number;
  active_regions: number;
  affected_sectors: number;
  mentioned_stocks: number;
}

interface RiskIndex {
  score: number;
  level: string;
  components: RiskComponents;
  details: RiskDetails;
}

interface GeoRegion {
  region: string;
  metadata: { color: string; border: string; bg: string; text: string; icon: string; description: string };
  article_count: number;
  stocks_mentioned: string[];
  sectors_affected: string[];
  avg_sentiment: number;
  sources: string[];
  latest_headline: string | null;
}

interface TimelineEvent {
  id: string;
  title: string;
  source: string;
  region: string;
  published_at: string;
  symbols: string[];
  sentiment_score: number;
  url: string;
  category: string;
}

interface SectorImpact {
  sector: string;
  stock_count: number;
  symbols: string[];
  avg_momentum: number;
  status: string;
}

interface GeoMonitorData {
  total_articles: number;
  active_regions: number;
  mentioned_stocks: number;
  regions: GeoRegion[];
  timeline: TimelineEvent[];
  sector_impact: SectorImpact[];
  risk_index: RiskIndex;
}

// ── History Hook ──────────────────────────────────────────────
function useGeoMonitorHistory() {
  return useQuery<HistoryData>({
    queryKey: ["geo-monitor-history"],
    queryFn: async () => (await api.get("/news/geo-monitor/history", { params: { days: 7 } })).data,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}

// ── Hook ──────────────────────────────────────────────────────
function useGeoMonitor() {
  return useQuery<GeoMonitorData>({
    queryKey: ["geo-monitor"],
    queryFn: async () => (await api.get("/news/geo-monitor", { params: { limit: 50 } })).data,
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}

// ── CSV Export Utility ───────────────────────────────────────
function downloadCSV(filename: string, headers: string[], rows: string[][]) {
  const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Generic sort hook ────────────────────────────────────────
function useTableSort<T>(data: T[], defaultCol: string, defaultDir: "asc" | "desc" = "asc") {
  const [sortCol, setSortCol] = useState(defaultCol);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultDir);

  const toggleSort = useCallback((col: string) => {
    setSortCol((prev) => {
      if (prev === col) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return prev;
      }
      setSortDir("desc");
      return col;
    });
  }, []);

  return { sortCol, sortDir, toggleSort };
}

// ── Table Search Input ───────────────────────────────────────
function TableSearch({ value, onChange, placeholder }: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-gray-600 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || "Filter..."}
        className="w-full pl-7 pr-7 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-[11px] text-gray-300 placeholder-gray-600 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all"
      />
      {value && (
        <button onClick={() => onChange("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 transition-colors">
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

// ── Sort header component ────────────────────────────────────
function SortHeader({ col, currentCol, dir, label, className }: {
  col: string; currentCol: string; dir: "asc" | "desc"; label: string; className?: string;
}) {
  const isActive = col === currentCol;
  return (
    <span className={cn("inline-flex items-center gap-1 select-none", className)}>
      {label}
      {isActive ? (
        dir === "asc" ? <ArrowUp className="h-2.5 w-2.5" /> : <ArrowDown className="h-2.5 w-2.5" />
      ) : (
        <ArrowUpDown className="h-2.5 w-2.5 text-gray-700" />
      )}
    </span>
  );
}

// ── Generic Excel-style Table ─────────────────────────────────
function GeoTable({ headers, children, className }: {
  headers: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("overflow-x-auto rounded-xl border border-gray-800", className)}>
      <table className="w-full text-[11px] border-collapse">
        <thead>
          <tr className="bg-gray-800/80 border-b border-gray-700">
            {headers}
          </tr>
        </thead>
        <tbody>
          {children}
        </tbody>
      </table>
    </div>
  );
}

// ── Pagination Bar ───────────────────────────────────────────
function PaginationBar({ page, totalPages, totalItems, onPageChange }: {
  page: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between px-4 py-2 border-t border-gray-800">
      <span className="text-[10px] text-gray-600">
        {totalItems} total events
      </span>
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className={cn(
            "flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all",
            page <= 1
              ? "text-gray-700 cursor-not-allowed"
              : "text-gray-400 hover:text-white hover:bg-gray-800"
          )}
        >
          <ChevronLeft className="h-3 w-3" />
          Prev
        </button>

        {/* Page number buttons */}
        {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
          // Show pages around current page
          let pageNum: number;
          if (totalPages <= 7) {
            pageNum = i + 1;
          } else if (page <= 4) {
            pageNum = i + 1;
          } else if (page >= totalPages - 3) {
            pageNum = totalPages - 6 + i;
          } else {
            pageNum = page - 3 + i;
          }
          const isCurrent = pageNum === page;
          return (
            <button
              key={pageNum}
              onClick={() => onPageChange(pageNum)}
              className={cn(
                "w-6 h-6 rounded-md text-[10px] font-semibold transition-all",
                isCurrent
                  ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                  : "text-gray-500 hover:text-white hover:bg-gray-800"
              )}
            >
              {pageNum}
            </button>
          );
        })}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className={cn(
            "flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all",
            page >= totalPages
              ? "text-gray-700 cursor-not-allowed"
              : "text-gray-400 hover:text-white hover:bg-gray-800"
          )}
        >
          Next
          <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

// ── Timeline Table ────────────────────────────────────────────
const TIMELINE_PAGE_SIZE = 25;

function TimelineTable({ events, regionFilter, searchQuery }: { events: TimelineEvent[]; regionFilter: string | null; searchQuery: string }) {
  const { sortCol, sortDir, toggleSort } = useTableSort<TimelineEvent>(events, "date");
  const [page, setPage] = useState(1);

  const sorted = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    let filtered = regionFilter ? events.filter((e) => e.region === regionFilter) : events;
    if (q) {
      filtered = filtered.filter((e) =>
        e.region.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q) ||
        e.title.toLowerCase().includes(q) ||
        e.symbols.some((s) => s.toLowerCase().includes(q))
      );
    }
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "date":
          cmp = new Date(a.published_at).getTime() - new Date(b.published_at).getTime();
          break;
        case "region":
          cmp = a.region.localeCompare(b.region);
          break;
        case "source":
          cmp = a.source.localeCompare(b.source);
          break;
        case "sentiment":
          cmp = a.sentiment_score - b.sentiment_score;
          break;
        default:
          cmp = new Date(a.published_at).getTime() - new Date(b.published_at).getTime();
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [events, regionFilter, sortCol, sortDir, searchQuery]);

  // Paginate
  const totalPages = Math.max(1, Math.ceil(sorted.length / TIMELINE_PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paginated = useMemo(() => {
    const start = (safePage - 1) * TIMELINE_PAGE_SIZE;
    return sorted.slice(start, start + TIMELINE_PAGE_SIZE);
  }, [sorted, safePage]);

  // Reset to page 1 when filters/sort change
  const filterKey = `${searchQuery}|${regionFilter}|${sortCol}|${sortDir}`;
  const prevFilterKey = useRef(filterKey);
  useEffect(() => {
    if (prevFilterKey.current !== filterKey) {
      prevFilterKey.current = filterKey;
      setPage(1);
    }
  }, [filterKey]);

  if (sorted.length === 0) {
    return (
      <div className="text-center py-8">
        <Clock className="h-6 w-6 text-gray-700 mx-auto mb-1" />
        <p className="text-gray-500 text-xs">
          {searchQuery ? "No events match your search" : "No events in this region"}
        </p>
      </div>
    );
  }

  const REGION_ICONS: Record<string, string> = {
    "Indo-Pacific": "🌏", "Middle East": "🕌", "Eastern Europe": "🏰",
    "Africa": "🌍", "Latin America": "🌎", "Arctic": "❄️", "Europe": "🇪🇺",
  };

  return (
    <>
    <GeoTable
      headers={
        <>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-24 cursor-pointer" onClick={() => toggleSort("date")}>
            <SortHeader col="date" currentCol={sortCol} dir={sortDir} label="Date" />
          </th>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-28 cursor-pointer" onClick={() => toggleSort("region")}>
            <SortHeader col="region" currentCol={sortCol} dir={sortDir} label="Region" />
          </th>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider cursor-pointer" onClick={() => toggleSort("source")}>
            <SortHeader col="source" currentCol={sortCol} dir={sortDir} label="Source" />
          </th>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider">Headline</th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-16 cursor-pointer" onClick={() => toggleSort("sentiment")}>
            <SortHeader col="sentiment" currentCol={sortCol} dir={sortDir} label="Sent." className="justify-end" />
          </th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-24">Symbols</th>
        </>
      }
    >
      {paginated.map((event, i) => {
        const icon = REGION_ICONS[event.region] || "🌐";
        const isEven = i % 2 === 0;
        return (
          <tr key={event.id} className={cn(
            "transition-colors",
            isEven ? "bg-gray-900/30" : "bg-gray-900/10",
            "hover:bg-gray-800/50"
          )}>
            <td className="px-3 py-2 text-gray-400 font-mono whitespace-nowrap text-[10px]">
              {format(new Date(event.published_at), "dd MMM")}
            </td>
            <td className="px-3 py-2 whitespace-nowrap">
              <span className="mr-1 text-[10px]">{icon}</span>
              <span className="text-gray-300 text-[10px]">{event.region}</span>
            </td>
            <td className="px-3 py-2 text-gray-500 text-[10px]">{event.source}</td>
            <td className="px-3 py-2">
              <a href={event.url} target="_blank" rel="noreferrer noopener"
                className="text-gray-300 hover:text-cyan-400 text-[10px] leading-snug line-clamp-1 transition-colors">
                {event.title}
              </a>
            </td>
            <td className="px-3 py-2 text-right">
              <span className={cn(
                "text-[10px] font-bold tabular-nums",
                event.sentiment_score > 0.05 ? "text-green-400" : event.sentiment_score < -0.05 ? "text-red-400" : "text-gray-500"
              )}>
                {event.sentiment_score > 0 ? "+" : ""}{(event.sentiment_score * 100).toFixed(0)}
              </span>
            </td>
            <td className="px-3 py-2 text-right">
              <div className="inline-flex gap-1">
                {event.symbols.slice(0, 2).map((sym) => (
                  <span key={sym} className="px-1 py-0.5 bg-gray-800 rounded text-[8px] font-mono text-gray-500">{sym}</span>
                ))}
                {event.symbols.length > 2 && (
                  <span className="text-[8px] text-gray-600">+{event.symbols.length - 2}</span>
                )}
              </div>
            </td>
          </tr>
        );
      })}
    </GeoTable>

    <PaginationBar
      page={safePage}
      totalPages={totalPages}
      totalItems={sorted.length}
      onPageChange={setPage}
    />
    </>
  );
}

// ── Sector Impact Table ──────────────────────────────────────
function SectorImpactTable({ sectors, searchQuery }: { sectors: SectorImpact[]; searchQuery: string }) {
  const { sortCol, sortDir, toggleSort } = useTableSort<SectorImpact>(sectors, "stock_count");

  const sorted = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    let filtered = sectors;
    if (q) {
      filtered = filtered.filter((s) =>
        s.sector.toLowerCase().includes(q) ||
        s.status.toLowerCase().includes(q) ||
        s.symbols.some((sym) => sym.toLowerCase().includes(q))
      );
    }
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "sector":
          cmp = a.sector.localeCompare(b.sector);
          break;
        case "stocks":
          cmp = a.stock_count - b.stock_count;
          break;
        case "momentum":
          cmp = a.avg_momentum - b.avg_momentum;
          break;
        case "status":
          cmp = a.status.localeCompare(b.status);
          break;
        default:
          cmp = a.stock_count - b.stock_count;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [sectors, sortCol, sortDir, searchQuery]);

  const SECTOR_ICONS: Record<string, string> = {
    "Defense & Aerospace": "🛡️", "Energy": "⚡", "Banking & Finance": "🏦",
    "IT": "💻", "Auto": "🚗", "Pharma": "💊", "FMCG": "🛒",
    "Metals & Mining": "⛏️", "Infrastructure": "🏗️", "Telecom": "📡",
  };

  return (
    <GeoTable
      headers={
        <>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider cursor-pointer" onClick={() => toggleSort("sector")}>
            <SortHeader col="sector" currentCol={sortCol} dir={sortDir} label="Sector" />
          </th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-16 cursor-pointer" onClick={() => toggleSort("stocks")}>
            <SortHeader col="stocks" currentCol={sortCol} dir={sortDir} label="Stocks" />
          </th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-20 cursor-pointer" onClick={() => toggleSort("momentum")}>
            <SortHeader col="momentum" currentCol={sortCol} dir={sortDir} label="Momentum" />
          </th>
          <th className="text-center px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-16 cursor-pointer" onClick={() => toggleSort("status")}>
            <SortHeader col="status" currentCol={sortCol} dir={sortDir} label="Status" />
          </th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider">Key Symbols</th>
        </>
      }
    >
      {sorted.length === 0 ? (
        <tr>
          <td colSpan={5} className="text-center py-8 text-gray-600 text-[10px]">No sectors match your filter</td>
        </tr>
      ) : sorted.map((s, i) => {
        const icon = SECTOR_ICONS[s.sector] || "📊";
        const isEven = i % 2 === 0;
        return (
          <tr key={s.sector} className={cn(
            "transition-colors",
            isEven ? "bg-gray-900/30" : "bg-gray-900/10",
            "hover:bg-gray-800/50"
          )}>
            <td className="px-3 py-2 whitespace-nowrap">
              <span className="mr-1.5 text-[10px]">{icon}</span>
              <span className="text-gray-300 text-[10px]">{s.sector}</span>
            </td>
            <td className="px-3 py-2 text-right text-gray-400 font-mono text-[10px]">{s.stock_count}</td>
            <td className="px-3 py-2 text-right">
              <div className="inline-flex items-center gap-1.5">
                <div className="w-12 h-1 bg-gray-800 rounded-full overflow-hidden inline-block">
                  <div className={cn(
                    "h-full rounded-full",
                    s.avg_momentum >= 60 ? "bg-green-500" : s.avg_momentum >= 45 ? "bg-yellow-500" : "bg-red-500",
                  )} style={{ width: `${s.avg_momentum}%` }} />
                </div>
                <span className={cn(
                  "text-[10px] font-bold tabular-nums",
                  s.avg_momentum >= 60 ? "text-green-400" : s.avg_momentum >= 45 ? "text-yellow-400" : "text-red-400"
                )}>{s.avg_momentum.toFixed(0)}</span>
              </div>
            </td>
            <td className="px-3 py-2 text-center">
              <span className={cn(
                "text-[9px] font-semibold px-1.5 py-0.5 rounded-full",
                s.status === "bullish" ? "bg-green-500/10 text-green-400" :
                s.status === "bearish" ? "bg-red-500/10 text-red-400" :
                "bg-gray-500/10 text-gray-400"
              )}>{s.status}</span>
            </td>
            <td className="px-3 py-2 text-right">
              <div className="inline-flex gap-1">
                {s.symbols.slice(0, 3).map((sym) => (
                  <span key={sym} className="px-1 py-0.5 bg-gray-800 rounded text-[8px] font-mono text-gray-500">{sym}</span>
                ))}
                {s.symbols.length > 3 && (
                  <span className="text-[8px] text-gray-600">+{s.symbols.length - 3}</span>
                )}
              </div>
            </td>
          </tr>
        );
      })}
    </GeoTable>
  );
}

// ── Region Details Table ──────────────────────────────────────
function RegionTable({ regions, selectedRegion, onSelectRegion, searchQuery }: {
  regions: GeoRegion[];
  selectedRegion: string | null;
  onSelectRegion: (r: string | null) => void;
  searchQuery: string;
}) {
  const { sortCol, sortDir, toggleSort } = useTableSort<GeoRegion>(regions, "article_count");

  const sorted = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    let filtered = regions;
    if (q) {
      filtered = filtered.filter((r) =>
        r.region.toLowerCase().includes(q) ||
        r.sectors_affected.some((s) => s.toLowerCase().includes(q)) ||
        r.sources.some((s) => s.toLowerCase().includes(q)) ||
        (r.latest_headline && r.latest_headline.toLowerCase().includes(q))
      );
    }
    return [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "region":
          cmp = a.region.localeCompare(b.region);
          break;
        case "articles":
          cmp = a.article_count - b.article_count;
          break;
        case "sentiment":
          cmp = a.avg_sentiment - b.avg_sentiment;
          break;
        default:
          cmp = a.article_count - b.article_count;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [regions, sortCol, sortDir, searchQuery]);

  return (
    <GeoTable
      headers={
        <>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider cursor-pointer" onClick={() => toggleSort("region")}>
            <SortHeader col="region" currentCol={sortCol} dir={sortDir} label="Region" />
          </th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-16 cursor-pointer" onClick={() => toggleSort("articles")}>
            <SortHeader col="articles" currentCol={sortCol} dir={sortDir} label="Articles" />
          </th>
          <th className="text-right px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-20 cursor-pointer" onClick={() => toggleSort("sentiment")}>
            <SortHeader col="sentiment" currentCol={sortCol} dir={sortDir} label="Sentiment" />
          </th>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider">Sectors</th>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider">Sources</th>
          <th className="text-left px-3 py-2 text-[10px] text-gray-500 font-semibold uppercase tracking-wider w-32">Latest Headline</th>
        </>
      }
    >
      {sorted.length === 0 ? (
        <tr>
          <td colSpan={6} className="text-center py-8 text-gray-600 text-[10px]">No regions match your filter</td>
        </tr>
      ) : sorted.map((r, i) => {
        const isEven = i % 2 === 0;
        const isSelected = selectedRegion === r.region;
        return (
          <tr
            key={r.region}
            onClick={() => onSelectRegion(isSelected ? null : r.region)}
            className={cn(
              "transition-colors cursor-pointer",
              isEven ? "bg-gray-900/30" : "bg-gray-900/10",
              isSelected ? "bg-blue-600/10 ring-1 ring-inset ring-blue-500/30" : "hover:bg-gray-800/50"
            )}
          >
            <td className="px-3 py-2 whitespace-nowrap">
              <span className="mr-1.5 text-[10px]">{r.metadata.icon}</span>
              <span className={cn("text-[10px] font-semibold", r.metadata.text)}>{r.region}</span>
            </td>
            <td className="px-3 py-2 text-right text-gray-400 font-mono text-[10px]">{r.article_count}</td>
            <td className="px-3 py-2 text-right">
              <span className={cn(
                "text-[10px] font-bold tabular-nums",
                r.avg_sentiment > 0.05 ? "text-green-400" : r.avg_sentiment < -0.05 ? "text-red-400" : "text-gray-500"
              )}>{(r.avg_sentiment * 100).toFixed(0)}</span>
            </td>
            <td className="px-3 py-2">
              <div className="flex flex-wrap gap-0.5">
                {r.sectors_affected.slice(0, 3).map((s) => (
                  <span key={s} className="text-[8px] text-gray-500 bg-gray-800 px-1 py-0.5 rounded">{s}</span>
                ))}
                {r.sectors_affected.length > 3 && (
                  <span className="text-[8px] text-gray-600">+{r.sectors_affected.length - 3}</span>
                )}
              </div>
            </td>
            <td className="px-3 py-2">
              <div className="flex flex-wrap gap-0.5">
                {r.sources.map((s) => (
                  <span key={s} className="text-[8px] text-gray-500 bg-gray-800 px-1 py-0.5 rounded">{s}</span>
                ))}
              </div>
            </td>
            <td className="px-3 py-2 text-gray-600 text-[9px] truncate max-w-[120px]">{r.latest_headline}</td>
          </tr>
        );
      })}
    </GeoTable>
  );
}

// ── Risk Index Gauge ─────────────────────────────────────────
function RiskIndexGauge({ risk }: { risk: RiskIndex }) {
  const angle = (risk.score / 100) * 180; // 0° (left) to 180° (right)
  const radians = (angle * Math.PI) / 180;

  // Arc path for the gauge track (semicircle from -90° to +90°)
  const r = 60;
  const cx = 80;
  const cy = 75;
  const startX = cx - r;
  const startY = cy;
  const endX = cx + r;
  const endY = cy;

  // Needle position
  const needleLen = 52;
  const needleX = cx + needleLen * Math.sin(radians);
  const needleY = cy - needleLen * Math.cos(radians);

  const levelColors: Record<string, { text: string; bar: string; glow: string }> = {
    low:      { text: "text-green-400", bar: "bg-green-500", glow: "rgba(34,197,94,0.3)" },
    moderate: { text: "text-yellow-400", bar: "bg-yellow-500", glow: "rgba(234,179,8,0.3)" },
    high:     { text: "text-orange-400", bar: "bg-orange-500", glow: "rgba(249,115,22,0.3)" },
    critical: { text: "text-red-400",    bar: "bg-red-500",    glow: "rgba(239,68,68,0.3)" },
  };
  const colors = levelColors[risk.level] ?? levelColors.moderate;

  const componentLabels: Record<string, string> = {
    news_volume: "News Volume",
    sentiment_risk: "Sentiment Risk",
    sector_breadth: "Sector Breadth",
    region_spread: "Region Spread",
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 md:p-5">
      <div className="flex items-center gap-2 mb-3">
        <Gauge className="h-5 w-5 text-cyan-400" />
        <h3 className="text-white font-bold">Geopolitical Risk Index</h3>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-4">
        {/* ── SVG Gauge ── */}
        <div className="relative flex-shrink-0">
          <svg width="160" height="90" viewBox="0 0 160 90" className="overflow-visible">
            {/* Background arc (gray track) */}
            <path
              d={`M ${startX} ${startY} A ${r} ${r} 0 0 1 ${endX} ${endY}`}
              fill="none"
              stroke="#374151"
              strokeWidth="10"
              strokeLinecap="round"
            />
            {/* Colored arc up to needle position */}
            <path
              d={`M ${startX} ${startY} A ${r} ${r} 0 ${angle > 90 ? 1 : 0} 1 ${needleX} ${needleY}`}
              fill="none"
              stroke={colors.glow}
              strokeWidth="6"
              strokeLinecap="round"
              opacity="0.8"
            />
            {/* Needle */}
            <line
              x1={cx} y1={cy}
              x2={needleX} y2={needleY}
              stroke="#e5e7eb"
              strokeWidth="2"
              strokeLinecap="round"
              className="transition-all duration-500"
            />
            {/* Center dot */}
            <circle cx={cx} cy={cy} r="3.5" fill="#e5e7eb" />
            {/* Score label */}
            <text x={cx} y={cy + 20} textAnchor="middle" fill="#9ca3af" fontSize="9" fontFamily="monospace">
              {risk.score.toFixed(0)}/100
            </text>
            {/* Level label */}
            <text x={cx} y={cy + 34} textAnchor="middle" fill={colors.glow} fontSize="9" fontFamily="sans-serif" fontWeight="bold">
              {risk.level.toUpperCase()}
            </text>
          </svg>
        </div>

        {/* ── Component breakdown ── */}
        <div className="flex-1 w-full space-y-2">
          {Object.entries(risk.components).map(([key, value]) => {
            const label = componentLabels[key] ?? key;
            const maxVal = key === "news_volume" ? 35 : key === "sentiment_risk" ? 30 : key === "sector_breadth" ? 20 : 15;
            const pct = (value / maxVal) * 100;
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500 w-24 flex-shrink-0">{label}</span>
                <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      background: value > maxVal * 0.7 ? "#ef4444" : value > maxVal * 0.4 ? "#eab308" : "#22c55e",
                    }}
                  />
                </div>
                <span className="text-[10px] font-mono text-gray-400 w-8 text-right">{value.toFixed(0)}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Context summary */}
      <div className="mt-3 pt-3 border-t border-gray-800 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-gray-600">
        <span>{risk.details.total_articles} articles</span>
        <span>{risk.details.active_regions} regions</span>
        <span>{risk.details.affected_sectors} sectors</span>
        <span>{risk.details.mentioned_stocks} stocks</span>
      </div>
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center", color ?? "bg-blue-500/10")}>
          <Icon className={cn("h-5 w-5", color ? `${color.replace("bg", "text").replace("/10", "")}` : "text-blue-400")} />
        </div>
        <div>
          <p className="text-gray-400 text-xs font-medium">{label}</p>
          <p className="text-white text-xl font-bold">{value}</p>
          {sub && <p className="text-gray-600 text-[10px]">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────
export default function GeoMonitorPage() {
  const [regionFilter, setRegionFilter] = useState<string | null>(null);
  const [timelineSearch, setTimelineSearch] = useState("");
  const [sectorSearch, setSectorSearch] = useState("");
  const [regionSearch, setRegionSearch] = useState("");
  const { data, isLoading, refetch, isFetching } = useGeoMonitor();
  const { data: historyData } = useGeoMonitorHistory();

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-5">
        {/* ── Header ── */}
        <div className="flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Globe className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-white font-bold text-xl">Geopolitical Monitor</h2>
              <p className="text-gray-400 text-xs">Real-time geopolitical events impacting Indian markets</p>
            </div>
          </div>
          <button onClick={() => refetch()} disabled={isFetching}
            className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 hover:text-white rounded-xl text-xs font-medium transition-all">
            <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
            Refresh
          </button>
        </div>

        {/* ── Risk Index ── */}
        {data?.risk_index && <RiskIndexGauge risk={data.risk_index} />}

        {/* ── Historical Trends ── */}
        {historyData && <HistoricalTrends data={historyData} />}

        {/* ── Stats Row ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={Globe} label="Active Regions" value={data?.active_regions ?? 0}
            sub="Geopolitical hotspots" color="bg-cyan-500/10" />
          <StatCard icon={Newspaper} label="Total Articles" value={data?.total_articles ?? 0}
            sub="Last 24 hours" color="bg-blue-500/10" />
          <StatCard icon={BarChart3} label="Mentioned Stocks" value={data?.mentioned_stocks ?? 0}
            sub="Across all regions" color="bg-purple-500/10" />
          <StatCard icon={Shield} label="Affected Sectors" value={data?.sector_impact.length ?? 0}
            sub="With momentum data" color="bg-amber-500/10" />
        </div>

        {/* ── Region Map + Timeline (two columns on large screens) ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left: Map + Region details */}
          <div className="lg:col-span-1 space-y-5">
            {/* Interactive World Map */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-4 md:p-5">
              <div className="flex items-center gap-2 mb-3">
                <MapPin className="h-5 w-5 text-cyan-400" />
                <h3 className="text-white font-bold">Geopolitical Risk Map</h3>
                <span className="text-gray-500 text-xs">({data?.active_regions ?? 0} active)</span>
              </div>
              <WorldMap
                regions={data?.regions ?? []}
                selectedRegion={regionFilter}
                onSelectRegion={setRegionFilter}
              />
              <p className="text-gray-700 text-[10px] text-center mt-2">
                Click a country to filter timeline · Hover for details · Intensity = article volume
              </p>
            </div>

            {/* Region Details Table — Excel-style */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-4 pt-4 pb-2">
                <h3 className="text-white font-bold text-sm flex items-center gap-2">
                  <Layers className="h-4 w-4 text-cyan-400" />
                  Region Details
                </h3>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 text-[10px]">{data?.regions.length ?? 0} regions</span>
                  <button onClick={() => {
                    const regions = data?.regions ?? [];
                    downloadCSV(
                      `geo-regions-${new Date().toISOString().split("T")[0]}.csv`,
                      ["Region", "Articles", "Sentiment", "Sectors", "Sources", "Latest Headline"],
                      regions.map((r) => [
                        r.region,
                        String(r.article_count),
                        (r.avg_sentiment * 100).toFixed(0),
                        r.sectors_affected.slice(0, 4).join("; "),
                        r.sources.join("; "),
                        r.latest_headline || "",
                      ])
                    );
                  }}
                    className="flex items-center gap-1 px-1.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-cyan-400 text-[9px] font-semibold border border-gray-700 hover:border-cyan-500/30 transition-all"
                    title="Export CSV"
                  >
                    <Download className="h-2.5 w-2.5" />
                    CSV
                  </button>
                </div>
              </div>
              <div className="px-4 pb-2">
                <TableSearch value={regionSearch} onChange={setRegionSearch} placeholder="Filter regions..." />
              </div>
              <div className="px-0">
                <RegionTable
                  regions={data?.regions ?? []}
                  selectedRegion={regionFilter}
                  onSelectRegion={setRegionFilter}
                  searchQuery={regionSearch}
                />
              </div>
            </div>
          </div>

          {/* Right: Timeline + Sector Impact */}
          <div className="lg:col-span-2 space-y-5">
            {/* Timeline Table */}
            <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-4 pt-4 pb-2">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-cyan-400" />
                  <h3 className="text-white font-bold">Event Timeline</h3>
                  {regionFilter && (
                    <span className="text-cyan-400 text-xs bg-cyan-400/10 border border-cyan-500/30 px-2 py-0.5 rounded-full">
                      {regionFilter}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 text-[10px]">{data?.timeline.length ?? 0} events</span>
                  <button onClick={() => {
                    const events = data?.timeline ?? [];
                    downloadCSV(
                      `geo-timeline-${new Date().toISOString().split("T")[0]}.csv`,
                      ["Date", "Region", "Source", "Headline", "Sentiment", "Symbols"],
                      events.map((e) => [
                        format(new Date(e.published_at), "yyyy-MM-dd HH:mm"),
                        e.region,
                        e.source,
                        e.title.replace(/"/g, '""'),
                        (e.sentiment_score * 100).toFixed(0),
                        e.symbols.join("; "),
                      ])
                    );
                  }}
                    className="flex items-center gap-1 px-1.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-cyan-400 text-[9px] font-semibold border border-gray-700 hover:border-cyan-500/30 transition-all"
                    title="Export CSV"
                  >
                    <Download className="h-2.5 w-2.5" />
                    CSV
                  </button>
                  {regionFilter && (
                    <button onClick={() => setRegionFilter(null)}
                      className="text-[10px] text-gray-500 hover:text-white transition-colors">
                      Clear filter
                    </button>
                  )}
                </div>
              </div>
              <div className="px-4 pb-2">
                <TableSearch value={timelineSearch} onChange={setTimelineSearch} placeholder="Filter events by region, source, symbol..." />
              </div>
              <TimelineTable events={data?.timeline ?? []} regionFilter={regionFilter} searchQuery={timelineSearch} />
              <p className="text-gray-700 text-[10px] text-center py-3 border-t border-gray-800">
                Sources: Foreign Policy · The Economist · Geopolitical Monitor · Moneycontrol · ET
              </p>
            </div>

            {/* Sector Impact Table */}
            {data?.sector_impact && data.sector_impact.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between px-4 pt-4 pb-2">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-purple-400" />
                    <h3 className="text-white font-bold">Sector Impact Analysis</h3>
                    <span className="text-gray-500 text-xs">({data.sector_impact.length} sectors)</span>
                  <button onClick={() => {
                    downloadCSV(
                      `geo-sectors-${new Date().toISOString().split("T")[0]}.csv`,
                      ["Sector", "Stocks", "Momentum", "Status", "Key Symbols"],
                      (data.sector_impact ?? []).map((s) => [
                        s.sector,
                        String(s.stock_count),
                        s.avg_momentum.toFixed(1),
                        s.status,
                        s.symbols.join("; "),
                      ])
                    );
                  }}
                    className="flex items-center gap-1 px-1.5 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-cyan-400 text-[9px] font-semibold border border-gray-700 hover:border-cyan-500/30 transition-all"
                    title="Export CSV"
                  >
                    <Download className="h-2.5 w-2.5" />
                    CSV
                  </button>
                  </div>
                </div>
                <div className="px-4 pb-2">
                  <TableSearch value={sectorSearch} onChange={setSectorSearch} placeholder="Filter sectors..." />
                </div>
                <SectorImpactTable sectors={data.sector_impact} searchQuery={sectorSearch} />
                <p className="text-gray-700 text-[10px] text-center py-3 border-t border-gray-800">
                  Momentum scores based on technical analysis of mentioned stocks
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
