import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { cacheCatalog, readCatalog } from "@/lib/offline";

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

export function usePoll(path, interval = 8000) {
  const [data, setData] = useState(null);
  const [online, setOnline] = useState(true);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await api.get(path);
        if (alive) { setData(r.data); setOnline(true); }
      } catch (e) {
        if (alive && !e.response) setOnline(false);
      }
    };
    tick();
    const id = setInterval(tick, interval);
    return () => { alive = false; clearInterval(id); };
  }, [path, interval]);
  return { data, online };
}
