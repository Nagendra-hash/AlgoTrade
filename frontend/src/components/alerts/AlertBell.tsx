"use client";
// Path: frontend/src/components/alerts/AlertBell.tsx
import { useEffect, useRef, useState } from "react";
import { Bell, X, CheckCheck, AlertCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useNotifications, useMarkNotificationsRead, useUnreadCount } from "@/hooks/useAlerts";
import { useNotificationStore } from "@/store/notificationStore";
import { useNotificationWebSocket } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";
import type { Notification } from "@/types";

function NotifItem({ n, onRead }: { n: Notification; onRead: (id: string) => void }) {
  return (
    <div onClick={() => !n.is_read && onRead(n.id)}
      className={cn("flex items-start gap-3 px-4 py-3 hover:bg-white/5 cursor-pointer transition-colors",
        !n.is_read && "bg-blue-500/5 border-l-2 border-blue-500")}>
      <div className="h-8 w-8 rounded-full bg-orange-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
        <AlertCircle className="h-4 w-4 text-orange-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm leading-snug", n.is_read ? "text-gray-400" : "text-white font-medium")}>{n.title}</p>
        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.message}</p>
        <p className="text-xs text-gray-600 mt-1">{formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}</p>
      </div>
      {!n.is_read && <div className="h-2 w-2 rounded-full bg-blue-400 flex-shrink-0 mt-2" />}
    </div>
  );
}

export function AlertBell({ userId }: { userId: string }) {
  const [open, setOpen]   = useState(false);
  const [pulse, setPulse] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data: unreadData }  = useUnreadCount();
  const { data: notifsData }  = useNotifications();
  const markRead = useMarkNotificationsRead();
  const unreadCount   = useNotificationStore((s) => s.unreadCount);
  const liveAlerts     = useNotificationStore((s) => s.liveAlerts);
  const addLiveAlert   = useNotificationStore((s) => s.addLiveAlert);
  const setUnreadCount = useNotificationStore((s) => s.setUnreadCount);
  const markAllRead     = useNotificationStore((s) => s.markAllRead);
  const unread          = unreadData?.unread ?? unreadCount;

  useNotificationWebSocket({
    userId,
    onAlert: (data) => {
      addLiveAlert(data as Parameters<typeof addLiveAlert>[0]);
      setPulse(true);
      setTimeout(() => setPulse(false), 3000);
    },
  });

  useEffect(() => {
    if (unreadData?.unread !== undefined) setUnreadCount(unreadData.unread);
  }, [unreadData?.unread, setUnreadCount]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const notifications = notifsData?.notifications ?? [];

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)}
        className={cn("relative flex items-center justify-center h-9 w-9 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 transition-all", open && "bg-gray-700 border-gray-600")}>
        <Bell className={cn("h-4 w-4", unread > 0 ? "text-white" : "text-gray-400")} />
        {unread > 0 && (
          <span className={cn("absolute -top-1.5 -right-1.5 h-5 min-w-5 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center", pulse && "animate-bounce")}>
            {unread > 99 ? "99+" : unread}
          </span>
        )}
        {pulse && <span className="absolute inset-0 rounded-xl border-2 border-orange-400 animate-ping" />}
      </button>

      {open && (
        <div className="absolute right-0 top-11 w-96 max-h-[520px] flex flex-col bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden z-50 animate-fade-in">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 flex-shrink-0">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-gray-400" />
              <span className="text-white font-semibold text-sm">Notifications</span>
              {unread > 0 && <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full font-bold">{unread}</span>}
            </div>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <button onClick={() => { markRead.mutate(undefined); markAllRead(); }}
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
                  <CheckCheck className="h-3.5 w-3.5" /> Mark all read
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-gray-500 hover:text-white"><X className="h-4 w-4" /></button>
            </div>
          </div>              {liveAlerts.length > 0 && (
            <div className="border-b border-gray-800 bg-orange-500/5 px-4 py-2 flex-shrink-0">
              <p className="text-xs text-orange-400 font-semibold mb-1">🔔 Just triggered</p>
              {liveAlerts.slice(0, 3).map((a) => (
                <div key={a.id} className="text-xs text-gray-300 py-0.5">
                  <span className="text-orange-400 font-medium">{a.symbol}</span> · {a.message}
                </div>
              ))}
            </div>
          )}

          <div className="overflow-y-auto flex-1 divide-y divide-gray-800/60">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Bell className="h-10 w-10 text-gray-700 mb-3" />
                <p className="text-gray-500 text-sm">No notifications yet</p>
              </div>
            ) : notifications.map((n) => (
              <NotifItem key={n.id} n={n} onRead={(id) => markRead.mutate([id])} />
            ))}
          </div>

          <div className="border-t border-gray-800 px-4 py-2.5 flex-shrink-0 text-center">
            <a href="/alerts-news" className="text-xs text-blue-400 hover:text-blue-300">View all alerts →</a>
          </div>
        </div>
      )}
    </div>
  );
}
