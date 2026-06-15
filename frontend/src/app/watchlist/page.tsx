"use client";
// Path: frontend/src/app/watchlist/page.tsx
// Personal watchlist — symbols saved to localStorage. Quotes are live via /market/quotes.
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { Star, Plus, X, Search, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/lib/utils";

const DEFAULTS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"];

interface Quote { symbol: string; ltp: number; change: number; change_pct: number; volume: number; source?: string }

function loadList(): string[] {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem("tradeai:watchlist");
    return raw ? JSON.parse(raw) : DEFAULTS;
  } catch { return DEFAULTS; }
}

export default function WatchlistPage() {
  const [symbols, setSymbols] = useState<string[]>(DEFAULTS);
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState("");

  useEffect(() => { setSymbols(loadList()); }, []);
  useEffect(() => { if (typeof window !== "undefined") localStorage.setItem("tradeai:watchlist", JSON.stringify(symbols)); }, [symbols]);

  const { data: results = [] } = useQuery<{ symbol: string; name: string; exchange: string; sector: string }[]>({
    queryKey: ["search", search],
    queryFn: () => api.get("/market/search", { params: { q: search } }).then((r) => r.data),
    enabled: search.length >= 1,
    staleTime: 30_000,
  });

  const { data: quotes = [], isLoading } = useQuery<Quote[]>({
    queryKey: ["watchlist-quotes", symbols.join(",")],
    queryFn: async () => symbols.length ? (await api.get("/market/quotes", { params: { symbols: symbols.join(",") } })).data : [],
    refetchInterval: 5_000,
    enabled: symbols.length > 0,
  });

  const add = (s: string) => { if (!symbols.includes(s)) setSymbols([...symbols, s]); setAdding(""); setSearch(""); };
  const remove = (s: string) => setSymbols(symbols.filter((x) => x !== s));

  return (
    <DashboardLayout>
      <div className="space-y-5" data-testid="watchlist-root">
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-amber-500/10 border border-amber-500/30 rounded-full text-amber-300 text-[11px] font-bold tracking-widest uppercase mb-2">
              <Star className="h-3 w-3" /> My Watchlist
            </div>
            <h1 className="text-3xl font-black tracking-tight text-white">Watchlist</h1>
            <p className="text-gray-500 text-sm mt-1">Live quotes refresh every 5 seconds. Add or remove symbols below.</p>
          </div>
        </div>

        {/* Add */}
        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <input data-testid="watchlist-search" value={search} onChange={(e) => { setSearch(e.target.value); setAdding(e.target.value.toUpperCase()); }}
                placeholder="Search to add a symbol (e.g. INFY)…"
                className="w-full pl-9 pr-3 py-2.5 bg-gray-950 border border-gray-800 focus:border-amber-500/50 rounded-xl text-sm text-white placeholder-gray-600 outline-none" />
            </div>
            <button onClick={() => adding && add(adding.toUpperCase())} data-testid="watchlist-add-btn"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-amber-500 hover:bg-amber-400 text-gray-950 rounded-xl text-sm font-bold transition-all">
              <Plus className="h-4 w-4" /> Add
            </button>
          </div>
          {search && results.length > 0 && (
            <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2" data-testid="watchlist-suggestions">
              {results.slice(0, 6).map((r) => (
                <button key={r.symbol} onClick={() => add(r.symbol)} data-testid={`watchlist-suggest-${r.symbol}`}
                  className="flex items-center justify-between gap-2 px-3 py-2 bg-gray-950 border border-gray-800 hover:border-amber-500/40 rounded-lg text-left transition-all">
                  <div>
                    <p className="text-white font-bold text-sm">{r.symbol}</p>
                    <p className="text-gray-500 text-xs">{r.name} · {r.sector}</p>
                  </div>
                  <Plus className="h-4 w-4 text-amber-400" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quote grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" data-testid="watchlist-grid">
          {symbols.length === 0 && (
            <div className="col-span-full bg-gray-900/60 border border-gray-800 rounded-2xl p-10 text-center text-gray-500 text-sm">No symbols in your watchlist.</div>
          )}
          {symbols.map((sym) => {
            const q = quotes.find((x) => x.symbol === sym);
            const up = (q?.change_pct ?? 0) >= 0;
            return (
              <div key={sym} className="bg-gray-900/60 border border-gray-800 rounded-2xl p-4 hover:border-amber-500/30 transition-all group" data-testid={`watchlist-card-${sym}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-white font-black text-lg">{sym}</p>
                    <p className="text-gray-600 text-[10px] uppercase tracking-wider mt-0.5">{q?.source ?? (isLoading ? "loading…" : "—")}</p>
                  </div>
                  <button onClick={() => remove(sym)} data-testid={`watchlist-remove-${sym}`} className="text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <p className={cn("text-3xl font-black mt-3 tabular-nums", up ? "text-emerald-300" : "text-red-300")}>{q?.ltp != null ? `₹${q.ltp.toLocaleString("en-IN")}` : "—"}</p>
                <div className="flex items-center gap-2 mt-1 text-sm font-semibold tabular-nums">
                  {up ? <ArrowUpRight className="h-4 w-4 text-emerald-400" /> : <ArrowDownRight className="h-4 w-4 text-red-400" />}
                  <span className={up ? "text-emerald-400" : "text-red-400"}>
                    {q ? `${up ? "+" : ""}${q.change?.toFixed(2)} (${q.change_pct?.toFixed(2)}%)` : "No live data available"}
                  </span>
                </div>
                <p className="text-gray-500 text-xs mt-3">Volume {q?.volume ? q.volume.toLocaleString("en-IN") : "—"}</p>
              </div>
            );
          })}
        </div>
      </div>
    </DashboardLayout>
  );
}
