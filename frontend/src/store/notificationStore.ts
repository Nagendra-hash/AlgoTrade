// Real-time notification state
// Path: frontend/src/store/notificationStore.ts
"use client";
import { create } from "zustand";

interface LiveAlert {
  id:         string;
  title:      string;
  message:    string;
  symbol:     string;
  ltp:        number;
  change_pct: number;
  created_at: string;
}

interface NotificationState {
  unreadCount:    number;
  liveAlerts:     LiveAlert[];
  isDropdownOpen: boolean;
  setUnreadCount: (n: number) => void;
  incrementUnread:() => void;
  addLiveAlert:   (a: LiveAlert) => void;
  clearLiveAlerts:() => void;
  setDropdown:    (o: boolean) => void;
  markAllRead:    () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  unreadCount: 0,
  liveAlerts:  [],
  isDropdownOpen: false,
  setUnreadCount: (n) => set({ unreadCount: Math.max(0, n) }),
  incrementUnread:()  => set((s) => ({ unreadCount: s.unreadCount + 1 })),
  addLiveAlert: (a)   => set((s) => ({ liveAlerts: [a, ...s.liveAlerts].slice(0, 20), unreadCount: s.unreadCount + 1 })),
  clearLiveAlerts:()  => set({ liveAlerts: [] }),
  setDropdown: (o)    => set({ isDropdownOpen: o }),
  markAllRead: ()     => set({ unreadCount: 0 }),
}));
