import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { cacheCatalog, readCatalog } from "@/lib/offline";
import { useRealtime } from "@/context/RealtimeContext";

export function useFetch(path, deps = [], cacheKey = null) {
  const [data, setData] = useState(cacheKey ? readCatalog(cacheKey) : null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try {
      const r = await api.get(path);
      setData(r.data);
      if (cacheKey) cacheCatalog(cacheKey, r.data);
    } catch (e) {
      if (cacheKey) {
        const cached = readCatalog(cacheKey);
        if (cached) setData(cached);
      }
      if (process.env.NODE_ENV !== "production") console.error(`useFetch(${path}) gagal:`, e);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line
  }, deps);
  useEffect(() => { load(); }, [load]);
  return { data, loading, reload: load, setData };
}

// Identitas toko untuk kop struk & laporan. Di-cache supaya struk tetap benar
// walau kasir sedang offline.
export function useStore() {
  const { data } = useFetch("/settings", [], "settings");
  return {
    name: data?.store_name || "Berkah Ayam Mili",
    tagline: data?.store_tagline || "Ayam Potong & Fillet",
    address: data?.store_address || "",
    phone: data?.store_phone || "",
  };
}

export function usePoll(path, interval = 8000, topics = []) {
  const [data, setData] = useState(null);
  const [online, setOnline] = useState(true);
  const { connected, subscribe } = useRealtime();

  const tick = useCallback(async () => {
    try {
      const r = await api.get(path);
      setData(r.data);
      setOnline(true);
    } catch (e) {
      if (!e.response) setOnline(false);
    }
  }, [path]);

  useEffect(() => {
    tick();
    // Saat WebSocket hidup, polling hanya jaring pengaman (60s) karena data
    // sudah didorong server. Kalau socket mati, kembali ke interval cepat.
    const id = setInterval(tick, connected ? 60000 : interval);
    return () => clearInterval(id);
  }, [tick, interval, connected]);

  const topicKey = JSON.stringify(topics);
  useEffect(() => subscribe(JSON.parse(topicKey), tick), [subscribe, tick, topicKey]);

  return { data, online, reload: tick, live: connected };
}

// Refetch instan ketika server memberi tahu ada perubahan pada topik tertentu.
export function useRealtimeReload(topics, reload) {
  const { subscribe, connected } = useRealtime();
  const topicKey = JSON.stringify(topics);
  useEffect(() => subscribe(JSON.parse(topicKey), reload), [subscribe, reload, topicKey]);
  return connected;
}
