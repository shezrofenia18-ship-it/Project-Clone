import { createContext, useContext, useEffect, useState, useCallback, useRef, useMemo } from "react";
import api from "@/lib/api";
import { getQueue, enqueueSale, syncQueue } from "@/lib/offline";
import { toast } from "sonner";

const Ctx = createContext(null);

export function OfflineProvider({ children }) {
  const [online, setOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  const [syncing, setSyncing] = useState(false);
  const [pending, setPending] = useState(getQueue().length);
  const busy = useRef(false);

  const refresh = useCallback(() => setPending(getQueue().length), []);

  const doSync = useCallback(async () => {
    if (busy.current || !getQueue().length) return;
    busy.current = true;
    setSyncing(true);
    const res = await syncQueue(api);
    setSyncing(false);
    busy.current = false;
    refresh();
    if (res.synced > 0) toast.success(`${res.synced} transaksi offline tersinkronisasi`);
    if (res.failed > 0) toast.error(`${res.failed} transaksi gagal disinkronkan (stok/validasi)`);
  }, [refresh]);

  const enqueue = useCallback((body) => {
    const n = enqueueSale(body);
    setPending(n);
    return n;
  }, []);

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
      if (ol && getQueue().length) doSync();
    }, 6000);
    return () => clearInterval(id);
  }, [doSync]);

  const value = useMemo(
    () => ({ online, syncing, pending, enqueue, syncNow: doSync, refresh }),
    [online, syncing, pending, enqueue, doSync, refresh]
  );

  return (
    <Ctx.Provider value={value}>
      {children}
    </Ctx.Provider>
  );
}

export const useOffline = () => useContext(Ctx);
