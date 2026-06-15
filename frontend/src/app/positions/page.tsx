"use client";
// Path: frontend/src/app/positions/page.tsx
// Open intraday + carry positions from Angel One / Zerodha.
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plug, ArrowUpRight, ArrowDownRight, Briefcase } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface Position {
  symbol: string; exchange: string; quantity: number; average_price: number; ltp: number;
  pnl: number; pnl_pct: number; product_type?: string; is_real?: boolean;
}
interface Resp { positions: Position[]; source: string; is_real: boolean; no_live_data?: boolean }

export default function PositionsPage() {
  const { data, isLoading } = useQuery<Resp>({
    queryKey: ["positions"],
    queryFn: () => api.get("/portfolio/positions").then((r) => r.data),
    refetchInterval: 10_000,
  });

  const positions = data?.positions ?? [];
  const totalPnl = positions.reduce((s, p) => s + (p.pnl || 0), 0);

  return (
    <DashboardLayout>
      <div className="space-y-5" data-testid="positions-root">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-sky-500/10 border border-sky-500/30 rounded-full text-sky-300 text-[11px] font-bold tracking-widest uppercase mb-2">
            <Briefcase className="h-3 w-3" /> Open Positions
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white">Positions</h1>
          <p className="text-gray-500 text-sm mt-1">Live MTM from connected broker. Auto-refresh every 10s.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Stat testid="pos-stat-count" label="Open positions" value={String(positions.length)} />
          <Stat testid="pos-stat-pnl" label="MTM P&amp;L" value={positions.length ? `${totalPnl >= 0 ? "+" : "-"}₹${Math.abs(totalPnl).toLocaleString("en-IN")}` : "—"} color={totalPnl >= 0 ? "text-emerald-300" : "text-red-300"} />
          <Stat testid="pos-stat-source" label="Source" value={data?.source ?? "—"} />
        </div>

        <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden">
          <table className="w-full text-sm" data-testid="positions-table">
            <thead className="bg-gray-950 text-[11px] uppercase tracking-wider text-gray-500">
              <tr><th className="text-left px-4 py-3">Symbol</th><th>Qty</th><th>Avg</th><th>LTP</th><th>P&amp;L</th><th>%</th><th>Product</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {isLoading && <tr><td colSpan={7} className="text-center text-gray-500 py-12">Loading…</td></tr>}
              {!isLoading && (data?.no_live_data || positions.length === 0) && (
                <tr><td colSpan={7} className="text-center py-14" data-testid="positions-empty">
                  <Plug className="h-6 w-6 text-gray-600 mx-auto mb-3" />
                  <p className="text-gray-500 text-sm mb-3">No live data available.</p>
                  <Link href="/broker-settings" className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-950 rounded-xl text-sm font-bold">Connect Broker</Link>
                </td></tr>
              )}
              {positions.map((p) => (
                <tr key={p.symbol} className="hover:bg-gray-800/30" data-testid={`pos-row-${p.symbol}`}>
                  <td className="px-4 py-3 font-bold text-white">{p.symbol}<span className="text-gray-600 text-xs ml-2">{p.exchange}</span></td>
                  <td className="text-center text-gray-300 tabular-nums">{p.quantity}</td>
                  <td className="text-center text-gray-300 tabular-nums">₹{p.average_price?.toFixed(2)}</td>
                  <td className="text-center text-white tabular-nums">₹{p.ltp?.toFixed(2)}</td>
                  <td className={cn("text-center tabular-nums font-semibold", (p.pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {(p.pnl ?? 0) >= 0 ? "+" : "-"}₹{Math.abs(p.pnl ?? 0).toLocaleString("en-IN")}
                  </td>
                  <td className={cn("text-center tabular-nums font-semibold", (p.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {(p.pnl_pct ?? 0) >= 0 ? <ArrowUpRight className="h-3 w-3 inline" /> : <ArrowDownRight className="h-3 w-3 inline" />} {p.pnl_pct?.toFixed(2)}%
                  </td>
                  <td className="text-center text-gray-400 text-xs">{p.product_type ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Stat({ testid, label, value, color = "text-white" }: any) {
  return (
    <div data-testid={testid} className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
      <p className="text-gray-500 text-[11px] font-bold uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-black mt-1 ${color}`}>{value}</p>
    </div>
  );
}
