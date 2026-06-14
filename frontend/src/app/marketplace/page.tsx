"use client";
// Path: frontend/src/app/marketplace/page.tsx
import { useState, useMemo } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useMarketplace, useCloneStrategy, useDeployStrategy } from "@/hooks/useStrategies";
import { cn } from "@/lib/utils";
import {
  Store, Search, Star, Download, Play, TrendingUp, Filter,
  Loader2, CheckCircle2, Clock, BookOpen, Code2, Sparkles,
  User, ChevronRight, X, Zap, Heart,
} from "lucide-react";
import type { Strategy } from "@/types";

const CATEGORIES = [
  { id: "all",           label: "All Strategies",  icon: Store },
  { id: "trend_following", label: "Trend Following", icon: TrendingUp },
  { id: "mean_reversion",  label: "Mean Reversion",  icon: TrendingUp },
  { id: "momentum",        label: "Momentum",        icon: Zap },
  { id: "breakout",        label: "Breakout",        icon: TrendingUp },
  { id: "scalping",        label: "Scalping",        icon: Zap },
  { id: "swing",           label: "Swing Trading",   icon: TrendingUp },
];

const TIMEFRAMES = ["1m","5m","15m","30m","1h","1d","1w"];

function StrategyCard({ strategy, onSelect }: { strategy: Strategy; onSelect: (s: Strategy) => void }) {
  return (
    <button onClick={() => onSelect(strategy)}
      className="w-full text-left bg-gray-900 border border-gray-800 rounded-2xl p-5 hover:border-gray-600 hover:bg-gray-900/80 transition-all group">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-white font-bold text-sm truncate">{strategy.name}</h3>
            {strategy.clone_count > 0 && (
              <span className="flex items-center gap-0.5 text-[10px] text-purple-400 bg-purple-400/10 px-1.5 py-0.5 rounded-full border border-purple-500/20 flex-shrink-0">
                <Download className="h-2.5 w-2.5" />{strategy.clone_count}
              </span>
            )}
          </div>
          <p className="text-gray-500 text-xs line-clamp-2">{strategy.description || "No description"}</p>
        </div>
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/20 flex items-center justify-center flex-shrink-0">
          <Sparkles className="h-4 w-4 text-blue-400" />
        </div>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full capitalize font-medium">
          {strategy.strategy_type?.replace("_", " ")}
        </span>
        <span className="text-[10px] bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">{strategy.timeframe}</span>
        {strategy.tags?.slice(0, 2).map((tag) => (
          <span key={tag} className="text-[10px] bg-gray-800 text-gray-500 border border-gray-700 px-2 py-0.5 rounded-full">#{tag}</span>
        ))}
      </div>

      {/* Indicators */}
      {strategy.indicators && strategy.indicators.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {strategy.indicators.slice(0, 4).map((ind) => (
            <span key={ind} className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded font-mono">{ind}</span>
          ))}
        </div>
      )}

      {/* Symbols */}
      {strategy.symbols && strategy.symbols.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {strategy.symbols.slice(0, 4).map((sym) => (
            <span key={sym} className="text-[10px] bg-gray-800 border border-gray-700 text-gray-500 px-1.5 py-0.5 rounded font-mono">{sym}</span>
          ))}
        </div>
      )}
    </button>
  );
}

function StrategyDetail({ strategy, onClose, onClone, onDeploy }: {
  strategy: Strategy; onClose: () => void;
  onClone: (id: string) => void; onDeploy: (id: string) => void;
}) {
  const [tab, setTab] = useState<"overview" | "logic" | "code">("overview");

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-gray-800 bg-gradient-to-r from-blue-600/10 to-purple-600/10">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-white font-black text-lg">{strategy.name}</h3>
              <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full capitalize font-medium">
                {strategy.strategy_type?.replace("_", " ")}
              </span>
            </div>
            <p className="text-gray-400 text-sm">{strategy.description}</p>
            <div className="flex gap-3 mt-2 text-xs text-gray-500">
              <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {strategy.timeframe}</span>
              <span className="flex items-center gap-1"><Download className="h-3 w-3" /> {strategy.clone_count} clones</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white"><X className="h-5 w-5" /></button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800">
        {(["overview", "logic", "code"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn("flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 capitalize transition-all",
              tab === t ? "border-blue-500 text-blue-400" : "border-transparent text-gray-500 hover:text-gray-300")}>
            {t === "overview" ? <BookOpen className="h-3.5 w-3.5" /> : t === "logic" ? <Sparkles className="h-3.5 w-3.5" /> : <Code2 className="h-3.5 w-3.5" />}
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-5 max-h-80 overflow-y-auto">
        {tab === "overview" && (
          <div className="space-y-4">
            {strategy.indicators && strategy.indicators.length > 0 && (
              <div>
                <p className="text-gray-400 text-xs font-semibold mb-2 uppercase tracking-wide">Indicators</p>
                <div className="flex flex-wrap gap-1.5">
                  {strategy.indicators.map((ind) => (
                    <span key={ind} className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-2 py-1 rounded-lg font-mono">{ind}</span>
                  ))}
                </div>
              </div>
            )}
            {strategy.symbols && strategy.symbols.length > 0 && (
              <div>
                <p className="text-gray-400 text-xs font-semibold mb-2 uppercase tracking-wide">Symbols</p>
                <div className="flex flex-wrap gap-1.5">
                  {strategy.symbols.map((sym) => (
                    <span key={sym} className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-2 py-1 rounded-lg font-mono">{sym}</span>
                  ))}
                </div>
              </div>
            )}
            {strategy.tags && strategy.tags.length > 0 && (
              <div>
                <p className="text-gray-400 text-xs font-semibold mb-2 uppercase tracking-wide">Tags</p>
                <div className="flex flex-wrap gap-1.5">
                  {strategy.tags.map((tag) => (
                    <span key={tag} className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-2 py-1 rounded-lg">#{tag}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {tab === "logic" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { title: "Entry Logic", content: strategy.entry_logic, color: "text-green-400" },
              { title: "Exit Logic", content: strategy.exit_logic, color: "text-red-400" },
              { title: "Risk Rules", content: strategy.risk_rules, color: "text-blue-400" },
            ].map((section) => (
              <div key={section.title} className="bg-gray-800 rounded-xl p-4">
                <p className={cn("font-bold text-sm mb-3", section.color)}>{section.title}</p>
                <div className="space-y-1.5">
                  {(section.content || "").split("\n").filter(Boolean).map((line, i) => (
                    <p key={i} className="text-gray-300 text-xs leading-relaxed">
                      {line.startsWith("-") ? <>· {line.slice(1).trim()}</> : line}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === "code" && (
          <div className="bg-gray-800 rounded-xl p-4 overflow-x-auto">
            <pre className="text-gray-300 text-xs leading-relaxed font-mono whitespace-pre-wrap">{strategy.python_code || "No code available"}</pre>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="border-t border-gray-800 p-4 flex gap-3">
        <button onClick={() => onClone(strategy.id)}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl text-sm font-medium transition-all">
          <Download className="h-4 w-4" /> Clone Strategy
        </button>
        <button onClick={() => onDeploy(strategy.id)}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-semibold transition-all">
          <Play className="h-4 w-4" /> Deploy to Paper
        </button>
      </div>
    </div>
  );
}

export default function MarketplacePage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [timeframe, setTimeframe] = useState("");
  const [selected, setSelected] = useState<Strategy | null>(null);
  const [sort, setSort] = useState<"popular" | "newest">("popular");

  const { data: strategies = [], isLoading } = useMarketplace(search || undefined);
  const clone = useCloneStrategy();
  const deploy = useDeployStrategy();

  const filtered = useMemo(() => {
    let items = strategies;
    if (category !== "all") {
      items = items.filter((s) => s.strategy_type === category);
    }
    if (timeframe) {
      items = items.filter((s) => s.timeframe === timeframe);
    }
    if (sort === "popular") {
      items = [...items].sort((a, b) => b.clone_count - a.clone_count);
    } else {
      items = [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }
    return items;
  }, [strategies, category, timeframe, sort]);

  const handleClone = async (id: string) => {
    await clone.mutateAsync(id);
  };

  const handleDeploy = async (id: string) => {
    await deploy.mutateAsync({ id, mode: "paper" });
  };

  return (
    <DashboardLayout>
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white flex items-center gap-2">
              <Store className="h-6 w-6 text-purple-400" /> Strategy Marketplace
            </h2>
            <p className="text-gray-400 text-sm mt-0.5">Discover and clone community trading strategies</p>
          </div>
          <a href="/strategy"
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-purple-600/20">
            <Sparkles className="h-4 w-4" /> Create Your Own
          </a>
        </div>

        {/* Search & filters */}
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search strategies..."
              className="w-full pl-10 pr-4 py-2.5 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-600 focus:outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all" />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"><X className="h-4 w-4" /></button>
            )}
          </div>
          <div className="flex gap-1.5 bg-gray-800/50 p-1 rounded-xl">
            {(["popular", "newest"] as const).map((s) => (
              <button key={s} onClick={() => setSort(s)}
                className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all",
                  sort === s ? "bg-gray-900 text-white shadow" : "text-gray-500 hover:text-gray-300")}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Category + Timeframe filters */}
        <div className="flex flex-wrap gap-1.5 items-center">
          <Filter className="h-3.5 w-3.5 text-gray-500 mr-1" />
          {CATEGORIES.map((cat) => (
            <button key={cat.id} onClick={() => setCategory(cat.id)}
              className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold whitespace-nowrap transition-all",
                category === cat.id ? "bg-purple-600/20 border-purple-500 text-purple-400" : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600")}>
              {cat.label}
            </button>
          ))}
          <div className="h-4 w-px bg-gray-700 mx-1" />
          {TIMEFRAMES.map((tf) => (
            <button key={tf} onClick={() => setTimeframe(timeframe === tf ? "" : tf)}
              className={cn("px-2 py-1 rounded-lg border text-xs font-semibold transition-all",
                timeframe === tf ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300")}>
              {tf}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Strategy grid */}
          <div className={cn(selected ? "xl:col-span-2" : "xl:col-span-3")}>
            {isLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1,2,3,4].map((i) => (
                  <div key={i} className="bg-gray-900 border border-gray-800 rounded-2xl p-5 animate-pulse">
                    <div className="h-4 w-32 bg-gray-800 rounded mb-3" />
                    <div className="h-3 w-full bg-gray-800 rounded mb-2" />
                    <div className="h-3 w-4/5 bg-gray-800 rounded mb-4" />
                    <div className="flex gap-1.5">{[1,2,3].map((j) => <div key={j} className="h-5 w-12 bg-gray-800 rounded-full" />)}</div>
                  </div>
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-12 text-center">
                <Store className="h-12 w-12 text-gray-700 mx-auto mb-4" />
                <h3 className="text-white font-bold text-lg mb-2">
                  {search ? `No results for "${search}"` : "No strategies available"}
                </h3>
                <p className="text-gray-400 text-sm max-w-md mx-auto">
                  {search ? "Try a different search term or browse categories" : "Community strategies will appear here once shared. Create your own strategy with the AI Builder!"}
                </p>
                {!search && (
                  <a href="/strategy"
                    className="inline-flex items-center gap-2 mt-5 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl text-sm font-semibold transition-all">
                    <Sparkles className="h-4 w-4" /> Build a Strategy
                  </a>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filtered.map((s) => (
                  <StrategyCard key={s.id} strategy={s} onSelect={setSelected} />
                ))}
              </div>
            )}
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="xl:col-span-1">
              <StrategyDetail
                strategy={selected}
                onClose={() => setSelected(null)}
                onClone={handleClone}
                onDeploy={handleDeploy}
              />
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
