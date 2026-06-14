"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WS_URL } from "@/lib/api";
import type { WSMessage } from "@/types";

// ── Singleton WebSocket store ─────────────────────────────────
// Keeps ONE connection per user_id across all component re-renders
const _sockets: Map<string, WebSocket> = new Map();
const _listeners: Map<string, Set<(msg: WSMessage) => void>> = new Map();

function getOrCreateSocket(userId: string): WebSocket {
  const existing = _sockets.get(userId);
  if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
    return existing;
  }
  const ws = new WebSocket(`${WS_URL}/ws/notifications/${userId}`);
  _sockets.set(userId, ws);
  ws.onopen = () => {
    // If all listeners have already unsubscribed (e.g. component unmounted
    // during connection), close gracefully to avoid dangling connections.
    if (!_listeners.has(userId) || (_listeners.get(userId)?.size ?? 0) === 0) {
      ws.close(1000, "No listeners");
      // Only clean up the map if this socket is still the active one.
      // Prevents an old socket's onopen from deleting a newer socket
      // created during a mount→unmount→remount cycle (StrictMode).
      if (_sockets.get(userId) === ws) {
        _sockets.delete(userId);
      }
    }
  };
  ws.onmessage = (e) => {
    try {
      const msg: WSMessage = JSON.parse(e.data);
      const handlers = _listeners.get(userId);
      handlers?.forEach((fn) => fn(msg));
    } catch {}
  };
  ws.onclose = () => {
    _sockets.delete(userId);
    // Reconnect after 3 seconds if there are still active listeners
    setTimeout(() => {
      if (_listeners.has(userId) && (_listeners.get(userId)?.size ?? 0) > 0) {
        getOrCreateSocket(userId);
      }
    }, 3000);
  };
  ws.onerror = () => ws.close();
  return ws;
}

function addListener(userId: string, fn: (msg: WSMessage) => void) {
  if (!_listeners.has(userId)) _listeners.set(userId, new Set());
  _listeners.get(userId)!.add(fn);
}

function removeListener(userId: string, fn: (msg: WSMessage) => void) {
  _listeners.get(userId)?.delete(fn);
  // If no more listeners, schedule socket close.
  // If the socket is still connecting, the onopen handler will close it
  // gracefully instead of generating a "closed before connection established" warning.
  if ((_listeners.get(userId)?.size ?? 0) === 0) {
    _listeners.delete(userId);
    const ws = _sockets.get(userId);
    if (ws) {
      if (ws.readyState === WebSocket.CONNECTING) {
        // Socket hasn't finished opening yet — let onopen handle cleanup.
        // Keep it in _sockets so getOrCreateSocket can safely return it
        // to a re-mounting component.
      } else {
        ws.close(1000, "No more listeners");
        _sockets.delete(userId);
      }
    }
  }
}

// ── Hook ──────────────────────────────────────────────────────

interface Options {
  userId:     string;
  onAlert?:   (data: unknown) => void;
  onMessage?: (msg: WSMessage) => void;
}

export function useNotificationWebSocket({ userId, onAlert, onMessage }: Options) {
  const qc = useQueryClient();
  const [connected, setConnected] = useState(false);
  // Use refs for callbacks to avoid effect re-running when inline functions change
  const onAlertRef   = useRef(onAlert);
  const onMessageRef = useRef(onMessage);
  onAlertRef.current   = onAlert;
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!userId) return;

    const handler = (msg: WSMessage) => {
      onMessageRef.current?.(msg);
      if (msg.type === "alert_triggered") {
        onAlertRef.current?.(msg.data);
        qc.invalidateQueries({ queryKey: ["notifications"] });
        qc.invalidateQueries({ queryKey: ["alerts"] });
      }
      if (msg.type === "connected" || msg.type === "pong") {
        setConnected(true);
      }
    };

    addListener(userId, handler);
    const ws = getOrCreateSocket(userId);

    // Sync connected state
    const checkState = () => setConnected(ws.readyState === WebSocket.OPEN);
    const interval = setInterval(checkState, 2000);
    checkState();

    // Heartbeat ping
    const heartbeat = setInterval(() => {
      const sock = _sockets.get(userId);
      if (sock?.readyState === WebSocket.OPEN) {
        sock.send(JSON.stringify({ action: "ping" }));
      }
    }, 30_000);

    return () => {
      removeListener(userId, handler);
      clearInterval(interval);
      clearInterval(heartbeat);
    };
  }, [userId, qc]);

  return { connected };
}

// ── Market WebSocket (separate, simple) ───────────────────────

export function useMarketWebSocket(symbols: string[], onQuote?: (data: unknown) => void, userId?: string) {
  const ws        = useRef<WebSocket | null>(null);
  const destroyed = useRef(false);
  const [connected, setConnected] = useState(false);
  const symbolsKey = symbols.join(",");

  useEffect(() => {
    if (!symbols.length) return;
    destroyed.current = false;

    try {
      // Pass userId as query param so backend can use Angel One data when available
      const wsUrl = userId ? `${WS_URL}/ws/market?user_id=${userId}` : `${WS_URL}/ws/market`;
      const socket = new WebSocket(wsUrl);
      ws.current = socket;

      socket.onopen = () => {
        if (destroyed.current) { socket.close(); return; }
        setConnected(true);
        socket.send(JSON.stringify({ action: "subscribe", symbols }));
      };
      socket.onmessage = (e) => {
        if (destroyed.current) return;
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "quote") onQuote?.(msg.data);
        } catch {}
      };
      socket.onclose  = () => { if (!destroyed.current) setConnected(false); };
      socket.onerror  = () => socket.close();
    } catch {}

    return () => {
      destroyed.current = true;
      ws.current?.close(1000, "Component unmounted");
      ws.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey, userId, onQuote]);

  return { connected };
}
