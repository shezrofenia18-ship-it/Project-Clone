import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";

/**
 * Realtime (WebSocket) untuk Berkah Ayam Mili.
 *
 * Server hanya mengirim sinyal "topik ini berubah" (mis. "dashboard", "stock"),
 * lalu halaman yang berlangganan topik itu langsung refetch data. Kalau socket
 * gagal (jaringan/proxy memblokir), `connected` tetap false dan hooks otomatis
 * kembali ke polling cepat — jadi aplikasi TIDAK pernah berhenti bekerja.
 */
const RealtimeContext = createContext({ connected: false, subscribe: () => () => {} });

const MAX_BACKOFF = 30000;
const FLUSH_MS = 250; // gabungkan beberapa event beruntun jadi satu refetch

function wsUrl(token) {
  const base = process.env.REACT_APP_BACKEND_URL || "";
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  return `${proto}://${host}/api/ws?token=${encodeURIComponent(token)}`;
}

export function RealtimeProvider({ children }) {
  const { user } = useAuth();
  const [connected, setConnected] = useState(false);
  const subs = useRef(new Map());
  const seq = useRef(0);
  const wsRef = useRef(null);
  const retry = useRef(0);
  const timer = useRef(null);
  const flushTimer = useRef(null);
  const buffer = useRef(new Set());

  const subscribe = useCallback((topics, cb) => {
    const id = ++seq.current;
    subs.current.set(id, { topics: topics || [], cb });
    return () => { subs.current.delete(id); };
  }, []);

  const flush = useCallback(() => {
    const topics = Array.from(buffer.current);
    buffer.current.clear();
    subs.current.forEach(({ topics: want, cb }) => {
      const match = !want.length || want.some((t) => topics.includes(t));
      if (!match) return;
      try { cb(topics); } catch (e) {
        if (process.env.NODE_ENV !== "production") console.error("Realtime listener error:", e);
      }
    });
  }, []);

  const uid = user && user !== false ? user.id : null;

  useEffect(() => {
    if (!uid) return undefined;
    let disposed = false;

    const schedule = () => {
      if (disposed) return;
      retry.current += 1;
      const wait = Math.min(1000 * 2 ** Math.min(retry.current, 5), MAX_BACKOFF);
      timer.current = setTimeout(connect, wait);
    };

    function connect() {
      if (disposed) return;
      const token = localStorage.getItem("bam_token");
      if (!token) return;
      let ws;
      try { ws = new WebSocket(wsUrl(token)); } catch { schedule(); return; }
      wsRef.current = ws;

      ws.onopen = () => {
        if (disposed) return;
        retry.current = 0;
        setConnected(true);
      };
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type === "ping") { try { ws.send("ping"); } catch { /* socket sudah tutup */ } return; }
        if (msg.type !== "invalidate") return;
        (msg.topics || []).forEach((t) => buffer.current.add(t));
        if (flushTimer.current) clearTimeout(flushTimer.current);
        flushTimer.current = setTimeout(flush, FLUSH_MS);
      };
      ws.onerror = () => { /* ditangani di onclose */ };
      ws.onclose = (ev) => {
        if (wsRef.current === ws) wsRef.current = null;
        setConnected(false);
        if (disposed) return;
        // 1008 = token ditolak server. Jangan spam reconnect; polling tetap jalan.
        if (ev && ev.code === 1008) return;
        schedule();
      };
    }

    connect();
    const onOnline = () => {
      if (!wsRef.current) { retry.current = 0; connect(); }
    };
    window.addEventListener("online", onOnline);

    return () => {
      disposed = true;
      window.removeEventListener("online", onOnline);
      if (timer.current) clearTimeout(timer.current);
      if (flushTimer.current) clearTimeout(flushTimer.current);
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) { try { ws.close(); } catch { /* abaikan */ } }
      setConnected(false);
    };
  }, [uid, flush]);

  const value = useMemo(() => ({ connected, subscribe }), [connected, subscribe]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export const useRealtime = () => useContext(RealtimeContext);
