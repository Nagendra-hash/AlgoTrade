"use client";
// Path: frontend/src/components/alerts/AlertCard.tsx
import { useState } from "react";
import { Bell, BellOff, Trash2, Edit2, TrendingUp, TrendingDown, Percent, Activity, Clock, RotateCcw, CheckCircle2, Globe, SmilePlus, Frown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { usePauseAlert, useResumeAlert, useDeleteAlert } from "@/hooks/useAlerts";
import { cn } from "@/lib/utils";
import type { Alert, AlertCondition } from "@/types";
import { CONDITION_LABELS, CONDITION_UNITS } from "@/types";

const COND_ICONS: Record<AlertCondition, React.ElementType> = {
  above: TrendingUp, below: TrendingDown, percent_change: Percent,
  volume_spike: Activity, rsi_overbought: TrendingUp, rsi_oversold: TrendingDown,
  news_mention: Globe, sentiment_above: SmilePlus, sentiment_below: Frown,
};

const STATUS_STYLES: Record<string, string> = {
  active:    "text-green-400  bg-green-400/10  border-green-500/20",
  triggered: "text-blue-400   bg-blue-400/10   border-blue-500/20",
  paused:    "text-yellow-400 bg-yellow-400/10 border-yellow-500/20",
  expired:   "text-gray-400   bg-gray-400/10   border-gray-500/20",
};

interface Props { alert: Alert; onEdit: (a: Alert) => void; onSymbolClick?: (symbol: string) => void; }

export function AlertCard({ alert, onEdit, onSymbolClick }: Props) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const pause  = usePauseAlert();
  const resume = useResumeAlert();
  const del    = useDeleteAlert();

  const isActive    = alert.status === "active";
  const isTriggered = alert.status === "triggered";
  const isPaused    = alert.status === "paused";
  const isExpired   = alert.status === "expired";
  const Icon        = COND_ICONS[alert.condition] ?? Bell;
  const unit        = CONDITION_UNITS[alert.condition] ?? "₹";

  const handleDelete = async () => {
    if (!confirmDelete) { setConfirmDelete(true); setTimeout(() => setConfirmDelete(false), 3000); return; }
    await del.mutateAsync(alert.id);
  };

  // Progress bar: how close is current price to target?
  const progress = (() => {
    if (!alert.current_value || !["above","below"].includes(alert.condition)) return null;
    const { condition, target_value, current_value } = alert;
    const range = target_value * 0.1;
    let pct = 0;
    if (condition === "above") pct = Math.min(100, Math.max(0, ((current_value - (target_value - range)) / range) * 100));
    else pct = Math.min(100, Math.max(0, (((target_value + range) - current_value) / range) * 100));
    return pct;
  })();

  return (
    <div className={cn("bg-gray-900 border rounded-2xl p-5 transition-all hover:border-gray-600",
      isActive    && "border-gray-800",
      isTriggered && "border-blue-500/40 bg-blue-500/5",
      isPaused    && "border-yellow-500/30 opacity-75",
      isExpired   && "border-gray-800 opacity-50")}>

      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className={cn("h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0",
            isTriggered ? "bg-blue-500/15 text-blue-400" : isActive ? "bg-orange-500/15 text-orange-400" : "bg-gray-800 text-gray-500")}>
            <Icon className="h-4 w-4" />
          </div>            <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onSymbolClick?.(alert.symbol);
                }}
                className="text-white font-bold hover:text-cyan-400 transition-colors"
                title={`View ${alert.symbol} in stock screener`}
              >
                {alert.symbol}
              </button>
              <span className="text-gray-500 text-xs">{alert.exchange}</span>
              {alert.is_repeating && (
                <span className="flex items-center gap-0.5 text-xs text-purple-400 bg-purple-400/10 px-1.5 py-0.5 rounded-full border border-purple-500/20">
                  <RotateCcw className="h-2.5 w-2.5" /> Repeating
                </span>
              )}
              {alert.condition === "news_mention" && alert.news_sources && alert.news_sources.length > 0 && (
                <span className="flex items-center gap-0.5 text-xs text-cyan-400 bg-cyan-400/10 px-1.5 py-0.5 rounded-full border border-cyan-500/20">
                  <Globe className="h-2.5 w-2.5" />
                  {alert.news_sources.slice(0, 2).join(", ")}
                  {alert.news_sources.length > 2 && ` +${alert.news_sources.length - 2}`}
                </span>
              )}
            </div>
            <p className="text-gray-400 text-xs mt-0.5 truncate">
              {alert.name || `${CONDITION_LABELS[alert.condition]} ${unit}${alert.target_value.toLocaleString("en-IN")}`}
            </p>
          </div>
        </div>
        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold border flex-shrink-0 capitalize", STATUS_STYLES[alert.status])}>
          {isTriggered && <CheckCircle2 className="h-3 w-3 inline mr-1" />}
          {isPaused    && <BellOff      className="h-3 w-3 inline mr-1" />}
          {alert.status}
        </span>
      </div>

      {/* Condition detail */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-gray-500 text-sm">{CONDITION_LABELS[alert.condition]}</span>
          <span className="text-white font-semibold">{unit}{alert.target_value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</span>
        </div>
        {alert.current_value && (
          <div className="text-right">
            <p className="text-gray-500 text-xs">Current</p>
            <p className="text-white text-sm font-medium">₹{alert.current_value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</p>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {progress !== null && (
        <div className="mb-3">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-500">Distance to target</span>
            <span className="text-gray-400">{progress.toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div className={cn("h-full rounded-full transition-all duration-500", progress >= 90 ? "bg-orange-400" : progress >= 70 ? "bg-yellow-400" : "bg-blue-500")}
              style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* Triggered info */}
      {isTriggered && alert.triggered_at && (
        <div className="mb-3 flex items-center gap-1.5 text-xs text-blue-400 bg-blue-400/5 rounded-lg px-3 py-2">
          <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" />
          Triggered {formatDistanceToNow(new Date(alert.triggered_at), { addSuffix: true })}
          {alert.trigger_count > 1 && ` · ${alert.trigger_count}× total`}
        </div>
      )}

      {/* Last checked */}
      {alert.last_checked_at && isActive && (
        <div className="flex items-center gap-1 text-xs text-gray-600 mb-3">
          <Clock className="h-3 w-3" />
          Checked {formatDistanceToNow(new Date(alert.last_checked_at), { addSuffix: true })}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-gray-800">
        {!isExpired && !isTriggered && (
          <button onClick={() => onEdit(alert)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-400 hover:text-white rounded-lg text-xs font-medium transition-all">
            <Edit2 className="h-3.5 w-3.5" /> Edit
          </button>
        )}
        {(isActive || isPaused) && (
          <button onClick={() => isPaused ? resume.mutate(alert.id) : pause.mutate(alert.id)}
            disabled={pause.isPending || resume.isPending}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
              isPaused ? "bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20" : "bg-yellow-500/10 border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/20")}>
            {isPaused ? <><Bell className="h-3.5 w-3.5" /> Resume</> : <><BellOff className="h-3.5 w-3.5" /> Pause</>}
          </button>
        )}
        <div className="flex-1" />
        <button onClick={handleDelete} disabled={del.isPending}
          className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border",
            confirmDelete ? "bg-red-500/20 border-red-500 text-red-400 animate-pulse" : "bg-gray-800 border-gray-700 text-gray-500 hover:text-red-400 hover:border-red-500/30 hover:bg-red-500/10")}>
          <Trash2 className="h-3.5 w-3.5" /> {confirmDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
    </div>
  );
}
