"use client";
// Path: frontend/src/app/market/page.tsx
import { useState, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { SentimentBadge } from "@/components/sentiment/SentimentBadge";
import { useQuote, useCandles, useMarketStatus, useSymbolSearch } from "@/hooks/useMarket";
import { useMarketWebSocket } from "@/hooks/useWebSocket";
import { useAuthStore } from "@/store/authStore";
import { cn, getPnLColor } from "@/lib/utils";
import { Search, TrendingUp, Wifi, WifiOff, X, Activity, Database, Zap } from "lucide-react";
import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import type { Candle } from "@/types";

const WATCHLIST = ["RELIANCE","TCS","INFY","HDFCBANK","SBIN","WIPRO","NIFTY50","BANKNIFTY"];
const INTERVALS = [
  { label: "1m",  value: "1m",  period: "1d"  },
  { label: "5m",  value: "5m",  period: "5d"  },
  { label: "15m", value: "15m", period: "5d"  },
  { label: "1h",  value: "1h",  period: "1mo" },
  { label: "1D",  value: "1d",  period: "1y"  },
  { label: "1W",  value: "1w",  period: "5y"  },
];

function WatchlistCard({ symbol, selected, onClick }: { symbol: string; selected: boolean; onClick: () => void }) {
  const { data: q } = useQuote(symbol);
  const isPos = (q?.change_pct ?? 0) >= 0;
  return (
    <button onClick={onClick} className={cn(
      "w-full text-left bg-gray-900 border rounded-xl p-3.5 transition-all hover:border-gray-600",
      selected ? "border-blue-500 ring-1 ring-blue-500/20" : "border-gray-800"
    )}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-white font-bold text-sm">{symbol}</span>
        <span className={cn("text-xs font-semibold", getPnLColor(q?.change_pct ?? 0))}>
          {isPos ? "+" : ""}{q?.change_pct?.toFixed(2) ?? "0.00"}%
        </span>
      </div>
      <p className="text-xl font-black text-white">₹{q?.ltp?.toLocaleString("en-IN") ?? "—"}</p>
      <p className={cn("text-xs font-medium mt-0.5", getPnLColor(q?.change ?? 0))}>
        {(q?.change ?? 0) >= 0 ? "+" : ""}₹{q?.change?.toFixed(2) ?? "0.00"}
      </p>
      <div className="mt-2">
        <SentimentBadge symbol={symbol} size="sm" showTooltip={false} />
      </div>
    </button>
  );
}

function CandlestickChart({ symbol, interval, period }: { symbol: string; interval: string; period: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<ReturnType<typeof createChart> | null>(null);
  const candleRef    = useRef<ReturnType<ReturnType<typeof createChart>["addCandlestickSeries"]> | null>(null);
  const volumeRef    = useRef<ReturnType<ReturnType<typeof createChart>["addHistogramSeries"]> | null>(null);
  const { data: candles } = useCandles(symbol, interval, period);

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height: 380,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#4b5563", labelBackgroundColor: "#374151" },
        horzLine: { color: "#4b5563", labelBackgroundColor: "#374151" },
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
      },
      rightPriceScale: {
        borderColor: "#374151",
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
    });

    // ✅ Correct v4 API — use addCandlestickSeries and addHistogramSeries
    const candleSeries = chart.addCandlestickSeries({
      upColor:        "#22c55e",
      downColor:      "#ef4444",
      borderUpColor:  "#22c55e",
      borderDownColor:"#ef4444",
      wickUpColor:    "#22c55e",
      wickDownColor:  "#ef4444",
    });

    const volumeSeries = chart.addHistogramSeries({
      color:      "#3b82f6",
      priceFormat:{ type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current  = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.resize(containerRef.current.clientWidth, 380);
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current  = null;
      candleRef.current = null;
      volumeRef.current = null;
    };
  }, []);

  // Update data when candles change
  useEffect(() => {
    if (!candles || !candleRef.current || !volumeRef.current) return;

    candleRef.current.setData(
      candles.map((c: Candle) => ({
        time:  c.time as unknown as import("lightweight-charts").Time,
        open:  c.open,
        high:  c.high,
        low:   c.low,
        close: c.close,
      }))
    );

    volumeRef.current.setData(
      candles.map((c: Candle) => ({
        time:  c.time as unknown as import("lightweight-charts").Time,
        value: c.volume,
        color: c.close >= c.open ? "#22c55e33" : "#ef444433",
      }))
    );

    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  return <div ref={containerRef} className="w-full" style={{ height: 380 }} />;
}

function SymbolSearch({ onSelect }: { onSelect: (s: string) => void }) {
  const [q, setQ]   = useState("");
  const [open, setOpen] = useState(false);
  const { data: results = [] } = useSymbolSearch(q);

  return (
    <div className="relative w-72">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder="Search symbol..."
        className="w-full pl-9 pr-9 py-2.5 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
      />
      {q && (
        <button onClick={() => { setQ(""); setOpen(false); }} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      )}
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-xl shadow-xl overflow-hidden z-50">
          {results.map((r) => (
            <button key={r.symbol} onClick={() => { onSelect(r.symbol); setQ(""); setOpen(false); }}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-700 transition-colors text-left">
              <TrendingUp className="h-4 w-4 text-blue-400 flex-shrink-0" />
              <div>
                <p className="text-white font-semibold text-sm">{r.symbol}</p>
                <p className="text-gray-400 text-xs">{r.name}</p>
              </div>
              <span className="ml-auto text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded">{r.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MarketPage() {
  const [selected, setSelected]     = useState("RELIANCE");
  const [interval, setIntervalVal]  = useState("1d");
  const [period, setPeriod]         = useState("1y");
  const [liveQuotes, setLiveQuotes] = useState<Record<string, { ltp: number; change_pct: number; change?: number; source?: string }>>({});

  const { user } = useAuthStore();
  const { data: quote }  = useQuote(selected);
  const { data: status } = useMarketStatus();

  const { connected } = useMarketWebSocket(
    [selected, ...WATCHLIST],
    (data) => {
      const q = data as { symbol: string; ltp: number; change_pct: number };
      if (q?.symbol) setLiveQuotes((prev) => ({ ...prev, [q.symbol]: q }));
    },
    user?.id ?? undefined
  );

  const dataSource = liveQuotes[selected]?.source ?? quote?.source ?? "yfinance";
  const sourceConfig = dataSource === "angel_one"
    ? { label: "Angel One", color: "bg-green-500/10 border-green-500/20 text-green-400", icon: Zap }
    : dataSource === "zerodha"
    ? { label: "Zerodha", color: "bg-blue-500/10 border-blue-500/20 text-blue-400", icon: Zap }
    : { label: "Delayed", color: "bg-yellow-500/10 border-yellow-500/20 text-yellow-400", icon: Database };
  const SourceIcon = sourceConfig.icon;

  const displayQuote = { ...quote, ...(liveQuotes[selected] ?? {}) };
  const isPos = (displayQuote?.change_pct ?? 0) >= 0;

  return (
    <DashboardLayout>
      <div className="space-y-5">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-4 justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold",
              status?.is_open
                ? "bg-green-500/10 border-green-500/20 text-green-400"
                : "bg-red-500/10 border-red-500/20 text-red-400"
            )}>
              <Activity className="h-3 w-3" /> NSE {status?.status ?? "Checking..."}
            </div>
            <div className={cn("flex items-center gap-1.5 text-xs", connected ? "text-blue-400" : "text-gray-500")}>
              {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
              {connected ? "Live" : "Reconnecting..."}
            </div>
            {/* Data source indicator */}
            <div className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold",
              sourceConfig.color
            )}>
              <SourceIcon className="h-3 w-3" />
              {sourceConfig.label}
            </div>
          </div>
          <SymbolSearch onSelect={setSelected} />
        </div>

        {/* Quote hero */}
        {displayQuote && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <div className="flex flex-wrap items-start gap-6">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-2xl font-black text-white">{selected}</h2>
                  <SentimentBadge symbol={selected} size="sm" />
                </div>
                <div className="flex items-baseline gap-3">
                  <span className="text-4xl font-black text-white">
                    ₹{displayQuote.ltp?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                  </span>
                  <span className={cn("text-lg font-bold", getPnLColor(displayQuote.change_pct ?? 0))}>
                    {isPos ? "+" : ""}{displayQuote.change?.toFixed(2)} ({isPos ? "+" : ""}{displayQuote.change_pct?.toFixed(2)}%)
                  </span>
                </div>
              </div>
              <div className="flex flex-wrap gap-6 text-sm ml-auto">
                {[["Open", displayQuote.open], ["High", displayQuote.high], ["Low", displayQuote.low], ["Prev", displayQuote.prev_close]].map(([l, v]) => (
                  <div key={String(l)}>
                    <p className="text-gray-500 text-xs">{l}</p>
                    <p className="text-white font-bold">₹{Number(v)?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Chart + Watchlist */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
          <div className="xl:col-span-3 bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-800">
              <span className="text-white font-bold">{selected}</span>
              <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
                {INTERVALS.map((iv) => (
                  <button key={iv.value}
                    onClick={() => { setIntervalVal(iv.value); setPeriod(iv.period); }}
                    className={cn("px-3 py-1.5 rounded-md text-xs font-semibold transition-all",
                      interval === iv.value ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white")}>
                    {iv.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="p-2">
              <CandlestickChart symbol={selected} interval={interval} period={period} />
            </div>
          </div>

          <div className="xl:col-span-1 space-y-2">
            <h3 className="text-white font-bold text-sm px-1">Watchlist</h3>
            {WATCHLIST.map((sym) => (
              <WatchlistCard key={sym} symbol={sym} selected={sym === selected} onClick={() => setSelected(sym)} />
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
