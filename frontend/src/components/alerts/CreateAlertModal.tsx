"use client";
// Path: frontend/src/components/alerts/CreateAlertModal.tsx
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X, Bell, TrendingUp, TrendingDown, Percent, Activity, Loader2, Globe, SmilePlus, Frown } from "lucide-react";
import { useCreateAlert, useUpdateAlert } from "@/hooks/useAlerts";
import { cn } from "@/lib/utils";
import type { Alert, AlertCondition } from "@/types";
import { CONDITION_LABELS, CONDITION_UNITS } from "@/types";

const baseSchema = z.object({
  symbol:       z.string().min(1).max(20).transform((v) => v.toUpperCase()),
  exchange:     z.string().default("NSE"),
  name:         z.string().max(200).optional(),
  condition:    z.enum(["above","below","percent_change","volume_spike","rsi_overbought","rsi_oversold","news_mention","sentiment_above","sentiment_below"]),
  target_value: z.number({ invalid_type_error: "Enter a number" }).default(1),
  is_repeating: z.boolean().default(false),
  repeat_interval_minutes: z.number().min(5).max(10080).default(60),
  news_sources: z.array(z.string()).default([]),
  notes:        z.string().max(500).optional(),
  channels:     z.array(z.string()).default(["in_app"]),
}).superRefine((data, ctx) => {
  if (data.condition === "sentiment_below" && data.target_value > 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["target_value"],
      message: "Should be negative or zero for sentiment_below (e.g. -30)",
    });
  } else if (
    data.condition !== "sentiment_below" &&
    data.condition !== "news_mention" &&
    data.target_value <= 0
  ) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["target_value"],
      message: "Must be a positive number",
    });
  }
});
type FormData = z.infer<typeof baseSchema>;

const CONDITIONS: { value: AlertCondition; icon: React.ElementType; hint: string }[] = [
  { value: "above",          icon: TrendingUp,   hint: "Price ≥ value"         },
  { value: "below",          icon: TrendingDown, hint: "Price ≤ value"         },
  { value: "percent_change", icon: Percent,      hint: "Daily % move"          },
  { value: "volume_spike",   icon: Activity,     hint: "Volume × average"      },
  { value: "rsi_overbought", icon: TrendingUp,   hint: "RSI ≥ value (70)"      },
  { value: "rsi_oversold",   icon: TrendingDown, hint: "RSI ≤ value (30)"      },
  { value: "news_mention",   icon: Globe,        hint: "Mentioned in source"   },
  { value: "sentiment_above",icon: SmilePlus,    hint: "Sentiment ≥ value"    },
  { value: "sentiment_below",icon: Frown,        hint: "Sentiment ≤ value"    },
];

const SYMBOLS = ["RELIANCE","TCS","INFY","HDFCBANK","SBIN","NIFTY50","BANKNIFTY","ICICIBANK"];

const NEWS_SOURCE_CHIPS = ["Foreign Policy", "The Economist", "Geopolitical Monitor", "Moneycontrol", "Economic Times"];

interface Props { open: boolean; onClose: () => void; editAlert?: Alert | null; defaultSymbol?: string; }

export function CreateAlertModal({ open, onClose, editAlert, defaultSymbol }: Props) {
  const createAlert = useCreateAlert();
  const updateAlert = useUpdateAlert();
  const isEdit      = Boolean(editAlert);

  const { register, handleSubmit, watch, setValue, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(baseSchema),
    defaultValues: {
      symbol: defaultSymbol || editAlert?.symbol || "",
      exchange: editAlert?.exchange || "NSE",
      condition: editAlert?.condition || "above",
      target_value: editAlert?.target_value || undefined,
      is_repeating: editAlert?.is_repeating ?? false,
      repeat_interval_minutes: editAlert?.repeat_interval_minutes ?? 60,
      news_sources: editAlert?.news_sources ?? [],
      channels: editAlert?.channels || ["in_app"],
    },
  });

  const condition   = watch("condition");
  const isRepeating = watch("is_repeating");
  const channels    = watch("channels") || [];
  const newsSources = watch("news_sources") || [];
  const unit        = CONDITION_UNITS[condition] ?? "₹";
  const isNewsMention = condition === "news_mention";
  const isSentimentCondition = condition === "sentiment_above" || condition === "sentiment_below";

  useEffect(() => {
    if (open) {
      reset({
        symbol:   editAlert?.symbol ?? (defaultSymbol || ""),
        exchange: editAlert?.exchange ?? "NSE",
        name:     editAlert?.name ?? undefined,
        condition: editAlert?.condition ?? "above",
        target_value: editAlert?.target_value ?? undefined,
        is_repeating: editAlert?.is_repeating ?? false,
        repeat_interval_minutes: editAlert?.repeat_interval_minutes ?? 60,
        news_sources: editAlert?.news_sources ?? [],
        channels: editAlert?.channels ?? ["in_app"],
        notes: editAlert?.notes ?? undefined,
      });
    }
  }, [open, editAlert, defaultSymbol, reset]);

  const onSubmit = async (data: FormData) => {
    if (isEdit && editAlert) {
      await updateAlert.mutateAsync({ id: editAlert.id, data: data as Parameters<typeof updateAlert.mutateAsync>[0]["data"] });
    } else {
      await createAlert.mutateAsync(data as Parameters<typeof createAlert.mutateAsync>[0]);
    }
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-orange-500/15 flex items-center justify-center">
              <Bell className="h-4 w-4 text-orange-400" />
            </div>
            <h2 className="text-white font-bold text-lg">{isEdit ? "Edit Alert" : "Create Alert"}</h2>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white"><X className="h-5 w-5" /></button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* Symbol */}
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Symbol</label>
            <input {...register("symbol")} placeholder="e.g. RELIANCE"
              className={cn("w-full bg-gray-800 border rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2 uppercase",
                errors.symbol ? "border-red-500 focus:ring-red-500/20" : "border-gray-700 focus:border-blue-500 focus:ring-blue-500/20")} />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {SYMBOLS.map((s) => (
                <button key={s} type="button" onClick={() => setValue("symbol", s)}
                  className="px-2 py-1 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs text-gray-400 hover:text-white transition-all">{s}</button>
              ))}
            </div>
            {errors.symbol && <p className="text-red-400 text-xs mt-1">{errors.symbol.message}</p>}
          </div>

          {/* Condition */}
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Condition</label>
            <div className="grid grid-cols-2 gap-2">
              {CONDITIONS.map((c) => {
                const Icon = c.icon;
                return (
                  <button key={c.value} type="button" onClick={() => setValue("condition", c.value)} title={c.hint}
                    className={cn("flex items-center gap-2 px-3 py-2.5 rounded-xl border text-left text-xs font-medium transition-all",
                      condition === c.value ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600")}>
                    <Icon className="h-3.5 w-3.5 flex-shrink-0" />
                    {CONDITION_LABELS[c.value]}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Target - hidden for news_mention and sentiment conditions */}
          {!isNewsMention && !isSentimentCondition && (
            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">
                Target {unit ? `(${unit})` : ""}
              </label>
              <div className="relative">
                {unit === "₹" && <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm">₹</span>}
                <input {...register("target_value", { valueAsNumber: true })} type="number" step="0.01"
                  placeholder={condition === "percent_change" ? "e.g. 2.5" : condition.includes("rsi") ? "e.g. 70" : "e.g. 2800"}
                  className={cn("w-full bg-gray-800 border rounded-xl py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:ring-2",
                    unit === "₹" ? "pl-8 pr-4" : "px-4",
                    errors.target_value ? "border-red-500 focus:ring-red-500/20" : "border-gray-700 focus:border-blue-500 focus:ring-blue-500/20")} />
              </div>
              {errors.target_value && <p className="text-red-400 text-xs mt-1">{errors.target_value.message}</p>}
            </div>
          )}

          {/* Sentiment scale indicator */}
          {isSentimentCondition && (
            <div className="bg-gray-800 rounded-xl p-3 border border-gray-700">
              <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">
                Sentiment Target
              </label>
              <p className="text-gray-500 text-xs mb-2">
                Sentiment is scored from <span className="text-red-400 font-medium">-100</span> (bearish) through <span className="text-gray-400 font-medium">0</span> (neutral) to <span className="text-green-400 font-medium">+100</span> (bullish).
              </p>
              <div className="relative">
                <input {...register("target_value", { valueAsNumber: true })} type="number" step="5" min={-100} max={100}
                  placeholder={condition === "sentiment_above" ? "e.g. 30 (bullish threshold)" : "e.g. -30 (bearish threshold)"}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20" />
              </div>
              <div className="flex items-center justify-between mt-2">
                <div className="flex items-center gap-1 text-[10px]">
                  <Frown className="h-3 w-3 text-red-400" />
                  <span className="text-red-400">Bearish</span>
                  <span className="text-gray-600 mx-1">·</span>
                  <span className="text-gray-500">-100</span>
                </div>
                <div className="flex items-center gap-1 text-[10px]">
                  <span className="text-gray-500">+100</span>
                  <span className="text-gray-600 mx-1">·</span>
                  <span className="text-green-400">Bullish</span>
                  <SmilePlus className="h-3 w-3 text-green-400" />
                </div>
              </div>
            </div>
          )}

          {/* News source selector - only for news_mention */}
          {isNewsMention && (
            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">
                News Sources <span className="text-red-400">*</span>
              </label>
              <p className="text-gray-600 text-xs mb-2">
                Alert when {watch("symbol") || "a symbol"} is mentioned in news from these sources:
              </p>
              <div className="flex flex-wrap gap-2">
                {NEWS_SOURCE_CHIPS.map((src) => {
                  const active = newsSources.includes(src);
                  const sourceColors: Record<string, string> = {
                    "Foreign Policy":      "border-indigo-500/30 text-indigo-400",
                    "The Economist":       "border-rose-500/30 text-rose-400",
                    "Geopolitical Monitor":"border-cyan-500/30 text-cyan-400",
                    "Moneycontrol":        "border-blue-500/30 text-blue-400",
                    "Economic Times":      "border-orange-500/30 text-orange-400",
                  };
                  const color = sourceColors[src] ?? "border-gray-500/30 text-gray-400";
                  return (
                    <button key={src} type="button" onClick={() => {
                      const next = active
                        ? newsSources.filter((s: string) => s !== src)
                        : [...newsSources, src];
                      setValue("news_sources", next);
                    }}
                      className={cn("px-3 py-2 rounded-xl border text-xs font-medium transition-all",
                        active
                          ? `${color} bg-opacity-15`
                          : "bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300"
                      )}>
                      {src}
                    </button>
                  );
                })}
              </div>
              {newsSources.length === 0 && (
                <p className="text-amber-400 text-xs mt-1">Select at least one news source</p>
              )}
            </div>
          )}

          {/* Name */}
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Name <span className="text-gray-600 font-normal normal-case">(optional)</span></label>
            <input {...register("name")} placeholder="e.g. RELIANCE support alert"
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20" />
          </div>

          {/* Repeat toggle */}
          <div className="flex items-center justify-between p-3 bg-gray-800 rounded-xl border border-gray-700">
            <div>
              <p className="text-white text-sm font-medium">Repeat alert</p>
              <p className="text-gray-500 text-xs">Re-trigger after cooldown</p>
            </div>
            <button type="button" onClick={() => setValue("is_repeating", !isRepeating)}
              className={cn("h-6 w-11 rounded-full transition-colors relative", isRepeating ? "bg-blue-600" : "bg-gray-700")}>
              <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all", isRepeating ? "left-5" : "left-0.5")} />
            </button>
          </div>
          {isRepeating && (
            <div>
              <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Cooldown (minutes)</label>
              <input {...register("repeat_interval_minutes", { valueAsNumber: true })} type="number" min={5} max={10080}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
          )}

          {/* Channels */}
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Notify via</label>
            <div className="flex gap-2">
              {(["in_app", "telegram", "email"] as const).map((ch) => {
                const active = channels.includes(ch);
                return (
                  <button key={ch} type="button"
                    onClick={() => {
                      const next = active ? channels.filter((c) => c !== ch) : [...channels, ch];
                      setValue("channels", next.length ? next : ["in_app"]);
                    }}
                    className={cn("px-3 py-2 rounded-xl border text-xs font-medium capitalize transition-all",
                      active ? "bg-blue-600/20 border-blue-500 text-blue-400" : "bg-gray-800 border-gray-700 text-gray-500 hover:border-gray-600")}>
                    {ch.replace("_", " ")}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-gray-400 text-xs font-semibold block mb-2 uppercase tracking-wide">Notes <span className="text-gray-600 font-normal normal-case">(optional)</span></label>
            <textarea {...register("notes")} rows={2} placeholder="Why are you setting this alert?"
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-none" />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-xl text-sm font-medium transition-all">Cancel</button>
            <button type="submit" disabled={isSubmitting}
              className="flex-1 px-4 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-xl text-sm font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2">
              {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" />Saving...</> : isEdit ? "Update Alert" : "Create Alert"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
