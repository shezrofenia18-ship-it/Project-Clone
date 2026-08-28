import React, { createContext, useContext, useEffect, useState, useCallback, useRef, useMemo } from "react";
import api from "@/lib/api";
import {
  getQueue, enqueueSale, syncQueue, removeQueued, retryQueued,
  countPending, countFailed, getLastSync,
} from "@/lib/offline";
import { toast } from "sonner";

const Ctx = createContext(null);

export function OfflineProvider({ children }) {
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  const [syncing, setSyncing] = useState(false);
  const [queue, setQueueState] = useState(getQueue);
  const [lastSync, setLastSync] = useState(getLastSync);
  const busy = useRef(false);

  const refresh = useCallback(() => setQueueState(getQueue()), []);

  const doSync = useCallback(async (manual = false) => {
    if (busy.current) return;
    if (!countPending(getQueue())) {
      if (manual) toast.info("Tidak ada transaksi yang menunggu sinkron");
      return;
    }
    busy.current = true;
    setSyncing(true);
    const res = await syncQueue(api);
    setSyncing(false);
    busy.current = false;
    setQueueState(res.queue);
    setLastSync(getLastSync());
    if (res.synced > 0) toast.success(`${res.synced} transaksi offline berhasil tersinkron`);
    if (res.failed > 0) toast.error(`${res.failed} transaksi ditolak server — cek daftar antrean`);
    if (res.offline && manual) toast.warning("Masih offline — antrean tetap aman tersimpan");
    return res;
  }, []);

  const enqueue = useCallback((body, summary) => {
    setQueueState(enqueueSale(body, summary));
  }, []);

  const remove = useCallback((id) => {
    setQueueState(removeQueued(id));
    toast.success("Transaksi antrean dihapus");
  }, []);

  const retry = useCallback(async (id) => {
    setQueueState(retryQueued(id));
    await doSync(true);
  }, [doSync]);

  useEffect(() => {
    const on = () => { setOnline(true); doSync(); };
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, [doSync]);

  useEffect(() => {
    const id = setInterval(() => {
      const ol = navigator.onLine;
      setOnline(ol);
      if (ol && countPending(getQueue())) doSync();
    }, 6000);
    return () => clearInterval(id);
  }, [doSync]);

  // Keep several open tabs/devices-on-same-browser consistent.
  useEffect(() => {
    const onStorage = (e) => { if (e.key === "bam_offline_queue") refresh(); };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [refresh]);

  const pending = countPending(queue);
  const failed = countFailed(queue);
  const syncNow = useCallback(() => doSync(true), [doSync]);

  const value = useMemo(
    () => ({ online, syncing, queue, pending, failed, lastSync, enqueue, syncNow, remove, retry, refresh }),
    [online, syncing, queue, pending, failed, lastSync, enqueue, syncNow, remove, retry, refresh]
  );

  return (
    <Ctx.Provider value={value}>
      {children}
    </Ctx.Provider>
  );
}

export const useOffline = () => useContext(Ctx);
