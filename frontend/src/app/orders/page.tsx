"use client";
// Path: frontend/src/app/orders/page.tsx
import { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useOrders, usePlaceOrder, useCancelOrder } from "@/hooks/useOrders";
import { useAuthStore } from "@/store/authStore";
import { cn, getPnLColor } from "@/lib/utils";
import { ShoppingCart, ArrowUpRight, ArrowDownLeft, CheckCircle2, Clock, XCircle, AlertCircle, X, Loader2, Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { Order } from "@/types";

const STATUS_CFG: Record<string, { color: string; bg: string; border: string; icon: React.ElementType }> = {
  COMPLETE:  { color: "text-green-400",  bg: "bg-green-400/10",  border: "border-green-500/20",  icon: CheckCircle2 },
  PENDING:   { color: "text-yellow-400", bg: "bg-yellow-400/10", border: "border-yellow-500/20", icon: Clock        },
  OPEN:      { color: "text-blue-400",   bg: "bg-blue-400/10",   border: "border-blue-500/20",   icon: Clock        },
  CANCELLED: { color: "text-gray-400",   bg: "bg-gray-400/10",   border: "border-gray-500/20",   icon: XCircle      },
  REJECTED:  { color: "text-red-400",    bg: "bg-red-400/10",    border: "border-red-500/20",     icon: AlertCircle  },
};

const orderSchema = z.object({
  symbol:       z.string().min(1).transform((v) => v.toUpperCase()),
  side:         z.enum(["BUY","SELL"]),
  order_type:   z.enum(["MARKET","LIMIT"]),
  product_type: z.enum(["INTRADAY","DELIVERY"]),
  quantity:     z.number({ invalid_type_error: "Enter qty" }).int().positive(),
  price:        z.number().optional(),
  stop_loss:    z.number().optional(),
  take_profit:  z.number().optional(),
  is_paper_trade: z.boolean().default(true),
});
type OrderForm = z.infer<typeof orderSchema>;

function PlaceOrderPanel({ onClose }: { onClose: () => void }) {
  const placeOrder = usePlaceOrder();
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<OrderForm>({
    resolver: zodResolver(orderSchema),
    defaultValues: { side: "BUY", order_type: "MARKET", product_type: "INTRADAY", is_paper_trade: true },
  });
  const side      = watch("side");
  const orderType = watch("order_type");
  const isPaper   = watch("is_paper_trade");

  const onSubmit = async (data: OrderForm) => {
    await placeOrder.mutateAsync({ ...data, exchange: "NSE" } as Parameters<typeof placeOrder.mutateAsync>[0]);
    onClose();
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-white font-bold text-lg">Place Order</h3>
        <button onClick={onClose} className="text-gray-500 hover:text-white"><X className="h-5 w-5" /></button>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* Buy/Sell toggle */}
        <div className="flex gap-2">
          {(["BUY","SELL"] as const).map((s) => (
            <button key={s} type="button" onClick={() => setValue("side", s)}
              className={cn("flex-1 py-2.5 rounded-xl text-sm font-bold transition-all border",
                side === s && s === "BUY"  ? "bg-green-600 border-green-600 text-white" :
                side === s && s === "SELL" ? "bg-red-600 border-red-600 text-white"     :
                "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600")}>
              {s === "BUY" ? <><ArrowDownLeft className="h-4 w-4 inline mr-1" />BUY</> : <><ArrowUpRight className="h-4 w-4 inline mr-1" />SELL</>}
            </button>
          ))}
        </div>

        {/* Symbol */}
        <div>
          <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Symbol</label>
          <input {...register("symbol")} placeholder="e.g. RELIANCE" className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 uppercase" />
          {errors.symbol && <p className="text-red-400 text-xs mt-1">{errors.symbol.message}</p>}
        </div>

        {/* Order type */}
        <div className="grid grid-cols-2 gap-2">
          {(["MARKET","LIMIT"] as const).map((t) => (
            <button key={t} type="button" onClick={() => setValue("order_type", t)}
              className={cn("py-2 rounded-xl text-xs font-semibold transition-all border",
                orderType === t ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-800 border-gray-700 text-gray-500 hover:text-white")}>
              {t}
            </button>
          ))}
        </div>

        {/* Quantity */}
        <div>
          <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Quantity</label>
          <input {...register("quantity", { valueAsNumber: true })} type="number" min={1} placeholder="e.g. 10"
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
          {errors.quantity && <p className="text-red-400 text-xs mt-1">{errors.quantity.message}</p>}
        </div>

        {/* Price (limit only) */}
        {orderType === "LIMIT" && (
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Limit Price (₹)</label>
            <input {...register("price", { valueAsNumber: true })} type="number" step="0.05" placeholder="e.g. 2450"
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
          </div>
        )}

        {/* SL/TP */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Stop Loss ₹</label>
            <input {...register("stop_loss", { valueAsNumber: true })} type="number" step="0.05" placeholder="Optional"
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-1.5 uppercase tracking-wide">Take Profit ₹</label>
            <input {...register("take_profit", { valueAsNumber: true })} type="number" step="0.05" placeholder="Optional"
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
          </div>
        </div>

        {/* Paper toggle */}
        <div className="flex items-center justify-between p-3 bg-gray-800 rounded-xl border border-gray-700">
          <div>
            <p className="text-white text-sm font-medium">Paper Trading</p>
            <p className="text-gray-500 text-xs">Safe practice mode — no real money</p>
          </div>
          <button type="button" onClick={() => setValue("is_paper_trade", !isPaper)}
            className={cn("h-6 w-11 rounded-full transition-colors relative", isPaper ? "bg-blue-600" : "bg-orange-600")}>
            <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all", isPaper ? "left-5" : "left-0.5")} />
          </button>
        </div>

        <button type="submit" disabled={isSubmitting}
          className={cn("w-full py-3 rounded-xl text-sm font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-2",
            side === "BUY" ? "bg-green-600 hover:bg-green-700 text-white" : "bg-red-600 hover:bg-red-700 text-white")}>
          {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" />Placing...</> : `Place ${side} Order ${!isPaper ? "(LIVE)" : "(Paper)"}`}
        </button>
      </form>
    </div>
  );
}

const FILTERS = ["ALL","COMPLETE","PENDING","OPEN","CANCELLED","REJECTED"];

export default function OrdersPage() {
  const [filter, setFilter]   = useState("ALL");
  const [showPanel, setPanel] = useState(false);
  const { data: orders = [], isLoading } = useOrders();
  const cancelOrder = useCancelOrder();

  const filtered = filter === "ALL" ? orders : orders.filter((o: Order) => o.status === filter);
  const stats = {
    total:    orders.length,
    complete: orders.filter((o: Order) => o.status === "COMPLETE").length,
    pending:  orders.filter((o: Order) => ["PENDING","OPEN"].includes(o.status)).length,
    rejected: orders.filter((o: Order) => o.status === "REJECTED").length,
  };

  return (
    <DashboardLayout>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-white">Orders</h2>
            <p className="text-gray-400 text-sm mt-0.5">Place and manage your trades</p>
          </div>
          <button onClick={() => setPanel(!showPanel)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition-all">
            <Plus className="h-4 w-4" /> New Order
          </button>
        </div>

        {showPanel && <PlaceOrderPanel onClose={() => setPanel(false)} />}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[["Total Orders", stats.total,"text-white"],["Executed", stats.complete,"text-green-400"],["Pending/Open", stats.pending,"text-yellow-400"],["Rejected", stats.rejected,"text-red-400"]].map(([l,v,c]) => (
            <div key={String(l)} className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <p className="text-gray-400 text-xs mb-2">{l}</p>
              <p className={cn("text-3xl font-black", c)}>{v}</p>
            </div>
          ))}
        </div>

        {/* Order book */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-gray-800">
            <div className="flex items-center gap-2"><ShoppingCart className="h-5 w-5 text-blue-400" /><h3 className="text-white font-bold text-lg">Order Book</h3></div>
            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((f) => (
                <button key={f} onClick={() => setFilter(f)}
                  className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                    filter === f ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white")}>
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="h-7 w-7 text-blue-400 animate-spin" /></div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-800">
                    {["Symbol","Side","Type","Qty","Price","Avg Fill","Status","Mode","Time","Action"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((o: Order, i: number) => {
                    const isBuy = o.side === "BUY";
                    const cfg   = STATUS_CFG[o.status] ?? STATUS_CFG.PENDING;
                    const StatusIcon = cfg.icon;
                    const canCancel = ["PENDING","OPEN"].includes(o.status);
                    return (
                      <tr key={o.id} className={cn("border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors", i === filtered.length - 1 && "border-0")}>
                        <td className="px-4 py-3"><p className="text-white font-bold text-sm">{o.symbol}</p><p className="text-gray-500 text-xs">{o.exchange}</p></td>
                        <td className="px-4 py-3">
                          <span className={cn("flex items-center gap-1 text-xs font-bold px-2 py-1 rounded border w-fit",
                            isBuy ? "bg-green-400/10 text-green-400 border-green-500/20" : "bg-red-400/10 text-red-400 border-red-500/20")}>
                            {isBuy ? <ArrowDownLeft className="h-3 w-3" /> : <ArrowUpRight className="h-3 w-3" />}{o.side}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs">{o.order_type}</td>
                        <td className="px-4 py-3 text-white text-sm">{o.filled_quantity ?? 0}/{o.quantity}</td>
                        <td className="px-4 py-3 text-gray-300 text-sm">{o.price ? `₹${o.price}` : "Market"}</td>
                        <td className="px-4 py-3 text-white font-semibold text-sm">{o.average_price ? `₹${o.average_price.toLocaleString("en-IN")}` : "—"}</td>
                        <td className="px-4 py-3">
                          <div className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold w-fit", cfg.bg, cfg.color, cfg.border)}>
                            <StatusIcon className="h-3 w-3" />{o.status}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={cn("text-xs border px-2 py-0.5 rounded",
                            o.is_paper_trade === "true" ? "bg-blue-400/10 text-blue-400 border-blue-500/20" : "bg-orange-400/10 text-orange-400 border-orange-500/20")}>
                            {o.is_paper_trade === "true" ? "Paper" : "Live"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                          {new Date(o.placed_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td className="px-4 py-3">
                          {canCancel && (
                            <button onClick={() => cancelOrder.mutate(o.id)}
                              disabled={cancelOrder.isPending}
                              className="h-7 w-7 flex items-center justify-center text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all">
                              <X className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            {!isLoading && filtered.length === 0 && (
              <div className="text-center py-14 text-gray-500">
                <ShoppingCart className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="font-medium">No orders found</p>
                <p className="text-xs mt-1">Click &quot;New Order&quot; to place your first trade</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
