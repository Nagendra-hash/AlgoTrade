"use client";
// Path: frontend/src/app/alerts/page.tsx
import { useState, useCallback, useMemo, Suspense } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { NewsFeed } from "@/components/news/NewsFeed";
import { AlertsManager } from "@/components/alerts/AlertsManager";
import { StockSuggestions } from "@/components/news/StockSuggestions";
import { useAlerts } from "@/hooks/useAlerts";
import { useNewsScreener } from "@/hooks/useNews";
import { useMultipleQuotes } from "@/hooks/useMarket";
import { cn, getPnLColor, formatCompact } from "@/lib/utils";
import {
  Bell, Newspaper, Sparkles, X, Check, ArrowUpDown, ArrowUp, ArrowDown,
  Filter, BarChart3, Globe, Target, Eye, Layers, ArrowRight, Download, TrendingUp, DollarSign,
} from "lucide-react";
import type { Alert, NewsScreenerRecommendation } from "@/types";

type Tab = "news" | "alerts" | "suggestions";
type SortField = "name" | "price" | "change" | "alerts";
type SortDir = "asc" | "desc";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "news",         label: "News",         icon: Newspaper },
  { id: "alerts",       label: "Alerts",       icon: Bell },
  { id: "suggestions",  label: "Suggestions",  icon: Sparkles },
];

// ── URL param keys ────────────────────────────────────────────
const PARAM_SYMBOLS = "symbols";
const PARAM_TAB     = "tab";

// ── Main export with Suspense boundary for useSearchParams ────
export default function AlertsPage() {
  return (
    <Suspense fallback={null}>
      <AlertsPageContent />
    </Suspense>
  );
}

function AlertsPageContent() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const pathname     = usePathname();

  // Init from URL params (persists across refreshes)
  const [tab, setTabInternal] = useState<Tab>(
    (searchParams.get(PARAM_TAB) as Tab) || "news"
  );
  // Multi-select: comma-separated symbols in URL, e.g. ?symbols=RELIANCE,TCS,INFY
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(
    () => {
      const raw = searchParams.get(PARAM_SYMBOLS);
      return raw ? raw.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean) : [];
    }
  );

  const [showSymbolFilter, setShowSymbolFilter] = useState(false);
  const [showAllStocks, setShowAllStocks] = useState(false);

  // Sort state for the overview panel
  const [overviewSortField, setOverviewSortField] = useState<SortField>("name");
  const [overviewSortDir, setOverviewSortDir] = useState<SortDir>("asc");

  // Fetch alerts and news screener data to aggregate stock symbols
  const { data: alertsData } = useAlerts();
  const { data: screenerData } = useNewsScreener();

  // Derive unique stock symbols from alerts
  const alertSymbols = useMemo(() => {
    if (!alertsData?.alerts) return [];
    const unique = new Set<string>();
    alertsData.alerts.forEach((a: Alert) => {
      if (a.symbol) unique.add(a.symbol.toUpperCase());
    });
    return Array.from(unique).sort();
  }, [alertsData]);

  // Derive unique stock symbols from news screener
  const newsSymbols = useMemo(() => {
    if (!screenerData?.recommendations) return [];
    const unique = new Set<string>();
    screenerData.recommendations.forEach((r: NewsScreenerRecommendation) => {
      if (r.symbol) unique.add(r.symbol.toUpperCase());
    });
    return Array.from(unique).sort();
  }, [screenerData]);

  // Combined unique symbols from both sources
  const allSymbols = useMemo(() => {
    const unique = new Set([...alertSymbols, ...newsSymbols]);
    return Array.from(unique).sort();
  }, [alertSymbols, newsSymbols]);

  // Live quotes for the overview panel (only enabled when panel is open)
  const { data: quotes = [] } = useMultipleQuotes(
    showAllStocks ? allSymbols : [],
    "NSE"
  );

  // Build a quick lookup map for symbol -> quote
  const quoteMap = useMemo(() => {
    const map: Record<string, { ltp: number; change_pct: number }> = {};
    (quotes as Array<{ symbol: string; ltp: number; change_pct: number }>).forEach((q) => {
      if (q.symbol) map[q.symbol] = { ltp: q.ltp, change_pct: q.change_pct };
    });
    return map;
  }, [quotes]);

  // Update both state and URL
  const updateUrl = useCallback((params: Record<string, string | null>) => {
    const sp = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === "") {
        sp.delete(key);
      } else {
        sp.set(key, value);
      }
    }
    const qs = sp.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }, [searchParams, router, pathname]);

  const setTab = useCallback((newTab: Tab) => {
    setTabInternal(newTab);
    updateUrl({ [PARAM_TAB]: newTab });
  }, [updateUrl]);

  // Toggle a symbol in/out of the multi-select
  const toggleSymbol = useCallback((symbol: string) => {
    setSelectedSymbols((prev) => {
      const sym = symbol.toUpperCase();
      const next = prev.includes(sym)
        ? prev.filter((s) => s !== sym)
        : [...prev, sym];
      updateUrl({ [PARAM_SYMBOLS]: next.length > 0 ? next.join(",") : null });
      return next;
    });
  }, [updateUrl]);

  // Send selected symbols to the screener tab
  const viewInScreener = useCallback(() => {
    if (selectedSymbols.length === 0) return;
    setTabInternal("suggestions");
    setShowSymbolFilter(true);
    setShowAllStocks(false);
    updateUrl({ [PARAM_TAB]: "suggestions" });
  }, [selectedSymbols, updateUrl]);

  const clearSymbols = useCallback(() => {
    setSelectedSymbols([]);
    setShowSymbolFilter(false);
    updateUrl({ [PARAM_SYMBOLS]: null });
  }, [updateUrl]);

  // Remove a single symbol from the selection
  const removeSymbol = useCallback((symbol: string) => {
    setSelectedSymbols((prev) => {
      const next = prev.filter((s) => s !== symbol);
      updateUrl({ [PARAM_SYMBOLS]: next.length > 0 ? next.join(",") : null });
      return next;
    });
  }, [updateUrl]);

  // Count how many alerts reference each symbol
  const alertCountMap = useMemo(() => {
    const map: Record<string, number> = {};
    (alertsData?.alerts ?? []).forEach((a: Alert) => {
      const sym = a.symbol.toUpperCase();
      map[sym] = (map[sym] || 0) + 1;
    });
    return map;
  }, [alertsData]);

  // Sorted symbols for the overview panel
  const sortedSymbols = useMemo(() => {
    const sorted = [...allSymbols];
    sorted.sort((a, b) => {
      const getVal = (sym: string): number | string => {
        switch (overviewSortField) {
          case "name":
            return sym;
          case "price": {
            const q = quoteMap[sym];
            return q ? q.ltp : -1;
          }
          case "change": {
            const q = quoteMap[sym];
            return q ? q.change_pct : -Infinity;
          }
          case "alerts":
            return alertCountMap[sym] || 0;
        }
      };

      const va = getVal(a);
      const vb = getVal(b);

      let cmp: number;
      if (typeof va === "string" && typeof vb === "string") {
        cmp = va.localeCompare(vb);
      } else {
        cmp = (va as number) - (vb as number);
      }

      return overviewSortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [allSymbols, overviewSortField, overviewSortDir, quoteMap, alertCountMap]);

  // Cycle sort: change field or toggle direction if same field
  const cycleSort = useCallback((field: SortField) => {
    setOverviewSortField((prev) => {
      if (prev === field) {
        // Toggle direction
        setOverviewSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return prev;
      }
      setOverviewSortDir("desc");
      return field;
    });
  }, []);

  // Directly set sort to a specific field + direction (for presets)
  const setSort = useCallback((field: SortField, dir: SortDir) => {
    setOverviewSortField(field);
    setOverviewSortDir(dir);
  }, []);

  // Whether all symbols are currently selected
  const allSelected = selectedSymbols.length === allSymbols.length && allSymbols.length > 0;

  // Select all / deselect all toggle
  const selectAllToggle = useCallback(() => {
    if (allSelected) {
      // Deselect all
      setSelectedSymbols([]);
      updateUrl({ [PARAM_SYMBOLS]: null });
    } else {
      // Select all
      setSelectedSymbols(allSymbols);
      updateUrl({ [PARAM_SYMBOLS]: allSymbols.join(",") });
    }
  }, [allSelected, allSymbols, updateUrl]);

  // Export all symbols as CSV
  const exportCSV = useCallback(() => {
    const headers = ["Symbol", "Source", "Alert Count", "LTP", "Change %"];
    const rows = allSymbols.map((sym) => {
      const hasAlert = alertSymbols.includes(sym);
      const hasNews = newsSymbols.includes(sym);
      const source = hasAlert && hasNews ? "Alerts + News" : hasAlert ? "Alerts" : "News";
      const quote = quoteMap[sym];
      const ltp = quote ? String(quote.ltp) : "";
      const chg = quote ? `${quote.change_pct >= 0 ? "+" : ""}${quote.change_pct.toFixed(2)}%` : "";
      return [sym, source, String(alertCountMap[sym] || 0), ltp, chg];
    });

    const csvContent = [
      headers.join(","),
      ...rows.map((r) => r.join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `stocks-overview-${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [allSymbols, alertSymbols, newsSymbols, alertCountMap, quoteMap]);

  return (
    <DashboardLayout>
      <div className="space-y-4 h-[calc(100vh-6rem)] flex flex-col">
        {/* Header with tabs */}
        <div className="flex items-center justify-between flex-shrink-0">
          <h2 className="text-2xl font-black text-white flex items-center gap-2">
            <Newspaper className="h-6 w-6 text-blue-400" /> Alerts & Intelligence
          </h2>
          <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-xl p-1">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={cn("flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap",
                    tab === t.id ? "bg-blue-600 text-white shadow" : "text-gray-400 hover:text-white")}>
                  <Icon className="h-3.5 w-3.5" />
                  {t.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Symbol filter bar — toggleable, shows aggregated symbols from alerts + news */}
        <div className="flex-shrink-0">
          <button
            onClick={() => setShowSymbolFilter(!showSymbolFilter)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-semibold border transition-all",
              showSymbolFilter
                ? "bg-blue-600/20 border-blue-500 text-blue-400"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600"
            )}
          >
            <Filter className="h-3 w-3" />
            Stock Filters
            {allSymbols.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 bg-gray-700 rounded-full text-[9px]">{allSymbols.length}</span>
            )}
          </button>

          {showSymbolFilter && (
            <div className="mt-2 p-3 bg-gray-900/80 border border-gray-800 rounded-xl backdrop-blur-sm">
              {/* Section: Symbols from Alerts */}
              {alertSymbols.length > 0 && (
                <div className="mb-2.5">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Bell className="h-3 w-3 text-orange-400" />
                    <span className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">
                      From Alerts ({alertSymbols.length})
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {alertSymbols.map((sym) => {
                      const isSelected = selectedSymbols.includes(sym);
                      return (
                        <button
                          key={`alert-${sym}`}
                          onClick={() => toggleSymbol(sym)}
                          className={cn(
                            "inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold border transition-all",
                            isSelected
                              ? "bg-orange-600/20 border-orange-500 text-orange-400 ring-1 ring-orange-500/30"
                              : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600"
                          )}
                        >
                          {isSelected ? (
                            <Check className="h-2.5 w-2.5" />
                          ) : (
                            <Target className="h-2.5 w-2.5" />
                          )}
                          {sym}
                          <span className="text-gray-600 text-[8px]">×{alertCountMap[sym] || 1}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Section: Symbols from News Screener */}
              {newsSymbols.length > 0 && (
                <div className="mb-2.5">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Globe className="h-3 w-3 text-cyan-400" />
                    <span className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">
                      From News ({newsSymbols.length})
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {newsSymbols.map((sym) => {
                      const isSelected = selectedSymbols.includes(sym);
                      return (
                        <button
                          key={`news-${sym}`}
                          onClick={() => toggleSymbol(sym)}
                          className={cn(
                            "inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold border transition-all",
                            isSelected
                              ? "bg-cyan-600/20 border-cyan-500 text-cyan-400 ring-1 ring-cyan-500/30"
                              : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600"
                          )}
                        >
                          {isSelected ? (
                            <Check className="h-2.5 w-2.5" />
                          ) : (
                            <BarChart3 className="h-2.5 w-2.5" />
                          )}
                          {sym}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* View all + View in Screener actions */}
              <div className="mt-3 pt-3 border-t border-gray-800 space-y-2">
                <button
                  onClick={() => setShowAllStocks(!showAllStocks)}
                  className={cn(
                    "flex items-center justify-center gap-1.5 w-full py-2 rounded-xl text-[10px] font-semibold border transition-all",
                    showAllStocks
                      ? "bg-blue-600/20 border-blue-500 text-blue-400"
                      : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600"
                  )}
                >
                  <Eye className="h-3 w-3" />
                  {showAllStocks ? "Hide All Stocks" : `View All Stocks (${allSymbols.length})`}
                </button>

                {/* View selected in screener */}
                <button
                  onClick={viewInScreener}
                  disabled={selectedSymbols.length === 0}
                  className={cn(
                    "flex items-center justify-center gap-1.5 w-full py-2.5 rounded-xl text-[10px] font-semibold border transition-all",
                    selectedSymbols.length > 0
                      ? "bg-purple-600/20 border-purple-500 text-purple-400 hover:bg-purple-600/30 hover:border-purple-400"
                      : "bg-gray-800 border-gray-700 text-gray-600 cursor-not-allowed"
                  )}
                >
                  <ArrowRight className="h-3 w-3" />
                  View {selectedSymbols.length} {selectedSymbols.length === 1 ? "stock" : "stocks"} in Screener
                </button>
              </div>

              {/* No symbols */}
              {allSymbols.length === 0 && (
                <p className="text-gray-600 text-[10px] text-center py-2">
                  No stocks found yet. Alerts or news will populate this list.
                </p>
              )}
            </div>
          )}
        </div>

        {/* All Stocks Overview — inline panel showing all symbols combined */}
        {showAllStocks && allSymbols.length > 0 && (
          <div className="flex-shrink-0 p-3 bg-gray-900/80 border border-blue-500/20 rounded-xl backdrop-blur-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-blue-400" />
                <span className="text-xs text-gray-300 font-semibold">All Stocks Overview</span>
                <span className="text-[10px] text-gray-600">
                  {allSymbols.length} symbols from alerts and news
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {/* Sort buttons — desktop */}
                <div className="hidden sm:flex items-center gap-0.5 bg-gray-800/50 border border-gray-700 rounded-lg p-0.5">
                  {([
                    { field: "name" as const, label: "Name", icon: ArrowUpDown },
                    { field: "price" as const, label: "Price", icon: DollarSign },
                    { field: "change" as const, label: "Chg %", icon: TrendingUp },
                    { field: "alerts" as const, label: "Alerts", icon: Bell },
                  ]).map(({ field, label, icon: Icon }) => {
                    const isActive = overviewSortField === field;
                    return (
                      <button
                        key={field}
                        onClick={() => cycleSort(field)}
                        className={cn(
                          "inline-flex items-center gap-0.5 px-1.5 py-1 rounded-md text-[9px] font-semibold transition-all whitespace-nowrap",
                          isActive
                            ? "bg-blue-600/20 text-blue-400"
                            : "text-gray-500 hover:text-gray-300"
                        )}
                        title={`Sort by ${label}`}
                      >
                        <Icon className="h-2.5 w-2.5" />
                        {label}
                        {isActive && (
                          overviewSortDir === "asc"
                            ? <ArrowUp className="h-2.5 w-2.5" />
                            : <ArrowDown className="h-2.5 w-2.5" />
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Sort dropdown — mobile */}
                <div className="sm:hidden relative">
                  <select
                    value={overviewSortField}
                    onChange={(e) => cycleSort(e.target.value as SortField)}
                    className="appearance-none bg-gray-800 border border-gray-700 rounded-lg pl-2 pr-6 py-1 text-[10px] font-semibold text-gray-300 cursor-pointer outline-none focus:border-blue-500/50"
                    title="Sort by"
                  >
                    <option value="name">Name {overviewSortField === "name" ? (overviewSortDir === "asc" ? "↑" : "↓") : ""}</option>
                    <option value="price">Price {overviewSortField === "price" ? (overviewSortDir === "asc" ? "↑" : "↓") : ""}</option>
                    <option value="change">Chg % {overviewSortField === "change" ? (overviewSortDir === "asc" ? "↑" : "↓") : ""}</option>
                    <option value="alerts">Alerts {overviewSortField === "alerts" ? (overviewSortDir === "asc" ? "↑" : "↓") : ""}</option>
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-1.5 flex items-center">
                    <ArrowUpDown className="h-3 w-3 text-gray-500" />
                  </div>
                </div>

                {/* Top Gainers / Top Losers presets */}
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setSort("change", "desc")}
                    className={cn(
                      "flex items-center gap-0.5 px-1.5 py-1 rounded-lg text-[9px] font-semibold border transition-all",
                      overviewSortField === "change" && overviewSortDir === "desc"
                        ? "bg-green-600/20 border-green-500/50 text-green-400"
                        : "bg-gray-800 border-gray-700 text-gray-500 hover:text-green-400 hover:border-green-500/30"
                    )}
                    title="Top Gainers"
                  >
                    <ArrowUp className="h-2.5 w-2.5" />
                    Gainers
                  </button>
                  <button
                    onClick={() => setSort("change", "asc")}
                    className={cn(
                      "flex items-center gap-0.5 px-1.5 py-1 rounded-lg text-[9px] font-semibold border transition-all",
                      overviewSortField === "change" && overviewSortDir === "asc"
                        ? "bg-red-600/20 border-red-500/50 text-red-400"
                        : "bg-gray-800 border-gray-700 text-gray-500 hover:text-red-400 hover:border-red-500/30"
                    )}
                    title="Top Losers"
                  >
                    <ArrowDown className="h-2.5 w-2.5" />
                    Losers
                  </button>
                </div>

                <button
                  onClick={selectAllToggle}
                  className={cn(
                    "flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold border transition-all",
                    allSelected
                      ? "bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20"
                      : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600"
                  )}
                  title={allSelected ? "Deselect all symbols" : "Select all symbols"}
                >
                  {allSelected ? (
                    <X className="h-3 w-3" />
                  ) : (
                    <Check className="h-3 w-3" />
                  )}
                  {allSelected ? "Deselect All" : "Select All"}
                </button>
                <button
                  onClick={exportCSV}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-cyan-400 text-[10px] font-semibold border border-gray-700 hover:border-cyan-500/30 transition-all"
                  title="Download as CSV"
                >
                  <Download className="h-3 w-3" />
                  Export CSV
                </button>
                <button
                  onClick={() => setShowAllStocks(false)}
                  className="p-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-500 hover:text-white transition-all"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>

            {/* Selection summary bar */}
            {selectedSymbols.length > 0 && (
              <div className="flex items-center justify-between mb-3 px-1">
                <span className="text-[10px] text-blue-400 font-medium">
                  {selectedSymbols.length} {selectedSymbols.length === 1 ? "symbol" : "symbols"} selected
                </span>
                <button
                  onClick={viewInScreener}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/20 border border-purple-500/30 text-purple-400 hover:bg-purple-600/30 text-[10px] font-semibold transition-all"
                >
                  <ArrowRight className="h-3 w-3" />
                  View in Screener
                </button>
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
              {sortedSymbols.map((sym) => {
                const hasAlert = alertSymbols.includes(sym);
                const hasNews = newsSymbols.includes(sym);
                const alertCount = alertCountMap[sym] || 0;
                const isSelected = selectedSymbols.includes(sym);
                const quote = quoteMap[sym];

                return (
                  <button
                    key={sym}
                    onClick={() => toggleSymbol(sym)}
                    className={cn(
                      "flex flex-col items-start gap-1 p-2.5 rounded-xl border transition-all text-left group",
                      isSelected
                        ? "bg-blue-600/15 border-blue-500/40 ring-1 ring-blue-500/30"
                        : hasAlert && hasNews
                          ? "bg-purple-500/5 border-purple-500/20 hover:border-purple-500/40 hover:bg-purple-500/10"
                          : hasAlert
                            ? "bg-orange-500/5 border-orange-500/20 hover:border-orange-500/40 hover:bg-orange-500/10"
                            : "bg-cyan-500/5 border-cyan-500/20 hover:border-cyan-500/40 hover:bg-cyan-500/10"
                    )}
                  >
                    {/* Symbol name */}
                    <div className="flex items-center gap-1.5 w-full">
                      {isSelected && (
                        <Check className="h-3 w-3 text-blue-400 flex-shrink-0" />
                      )}
                      <span className={cn(
                        "text-xs font-bold transition-colors",
                        isSelected ? "text-blue-300" : "text-white group-hover:text-blue-300"
                      )}>
                        {sym}
                      </span>
                    </div>

                    {/* Live price & change % */}
                    {quote ? (
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-gray-300 tabular-nums">
                          {formatCompact(quote.ltp)}
                        </span>
                        <span className={cn(
                          "text-[10px] font-bold tabular-nums",
                          getPnLColor(quote.change_pct)
                        )}>
                          {quote.change_pct >= 0 ? "+" : ""}{quote.change_pct.toFixed(2)}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-[8px] text-gray-700 italic">Loading price...</span>
                    )}

                    {/* Source badges */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {hasAlert && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-orange-500/10 rounded text-[8px] font-semibold text-orange-400">
                          <Bell className="h-2 w-2" />
                          {alertCount}
                        </span>
                      )}
                      {hasNews && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-cyan-500/10 rounded text-[8px] font-semibold text-cyan-400">
                          <Globe className="h-2 w-2" />
                          news
                        </span>
                      )}
                    </div>

                    <span className="text-[8px] text-gray-600 group-hover:text-gray-500 transition-colors">
                      {isSelected ? "Click to remove" : "Click to select"}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Active multi-select filter badges */}
        {selectedSymbols.length > 0 && (
          <div className="flex-shrink-0">
            <div className="flex items-center gap-2 px-3 py-2 bg-blue-600/10 border border-blue-500/20 rounded-xl mb-2">
              <Filter className="h-3.5 w-3.5 text-blue-400 flex-shrink-0" />
              <span className="text-blue-400 text-xs font-medium">
                {selectedSymbols.length} {selectedSymbols.length === 1 ? "symbol" : "symbols"} selected
              </span>
              <button
                onClick={viewInScreener}
                className="ml-2 flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-600/20 border border-purple-500/30 text-purple-400 hover:bg-purple-600/30 text-[10px] font-semibold transition-all"
              >
                <ArrowRight className="h-3 w-3" />
                View in Screener
              </button>
              <button
                onClick={clearSymbols}
                className="ml-auto flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white text-[10px] font-semibold transition-all"
              >
                <X className="h-3 w-3" /> Clear All
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {selectedSymbols.map((sym) => (
                <div
                  key={sym}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-blue-600/15 border border-blue-500/25 text-blue-300 text-[10px] font-semibold"
                >
                  {sym}
                  <button
                    onClick={() => removeSymbol(sym)}
                    className="ml-0.5 hover:text-white transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-h-0">
          {tab === "news" && (
            <div className="h-full">
              <NewsFeed onSymbolClick={toggleSymbol} />
            </div>
          )}
          {tab === "alerts" && (
            <div className="h-full">
              <AlertsManager onSymbolClick={toggleSymbol} />
            </div>
          )}
          {tab === "suggestions" && (
            <div className="h-full overflow-y-auto pr-2">
              <StockSuggestions initialSymbols={selectedSymbols} />
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
