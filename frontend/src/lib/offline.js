// Offline transaction queue backed by localStorage. Server txn_id (unique index)
// guarantees idempotency, so re-sending a queued sale never duplicates it.
import { devWarn } from "@/lib/log";

const KEY = "bam_offline_queue";
const SYNC_KEY = "bam_last_sync";

function read(k, fallback) {
  try {
    const v = localStorage.getItem(k);
    return v ? JSON.parse(v) : fallback;
  } catch (e) {
    devWarn(`offline.read(${k})`, e);
    return fallback;
  }
}

function write(k, v) {
  try { localStorage.setItem(k, JSON.stringify(v)); }
  catch (e) { devWarn(`offline.write(${k}) - kemungkinan kuota localStorage penuh`, e); }
}

// Normalises legacy items (older builds stored only { body, queued_at }).
function normalise(item, idx) {
  return {
    id: item.id || item.body?.txn_id || `q-legacy-${idx}`,
    body: item.body,
    summary: item.summary || {},
    queued_at: item.queued_at || new Date().toISOString(),
    status: item.status === "failed" ? "failed" : "pending",
    attempts: item.attempts || 0,
    error: item.error || null,
  };
}

export function getQueue() {
  const q = read(KEY, []);
  if (!Array.isArray(q)) return [];
  return q.filter((i) => i && i.body).map(normalise);
}

export function setQueue(q) {
  write(KEY, q);
}

export function getLastSync() {
  return read(SYNC_KEY, null);
}

// `summary` keeps a human-readable snapshot (customer, total, items) so the
// pending list stays readable even though `body` only holds product ids.
export function enqueueSale(body, summary = {}) {
  const q = getQueue();
  q.push({
    id: body.txn_id || `q-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    body,
    summary,
    queued_at: new Date().toISOString(),
    status: "pending",
    attempts: 0,
    error: null,
  });
  setQueue(q);
  return q;
}

export function removeQueued(id) {
  const q = getQueue().filter((i) => i.id !== id);
  setQueue(q);
  return q;
}

export function retryQueued(id) {
  const q = getQueue().map((i) => (i.id === id ? { ...i, status: "pending", error: null } : i));
  setQueue(q);
  return q;
}

export const countPending = (q) => q.filter((i) => i.status !== "failed").length;
export const countFailed = (q) => q.filter((i) => i.status === "failed").length;

// Catalog cache so POS can open & sell even when offline from the very first load.
export function cacheCatalog(key, data) {
  try { localStorage.setItem(`bam_cache_${key}`, JSON.stringify(data)); }
  catch (e) { devWarn(`offline.cacheCatalog(${key}) - kemungkinan kuota localStorage penuh`, e); }
}

export function readCatalog(key) {
  try { const v = localStorage.getItem(`bam_cache_${key}`); return v ? JSON.parse(v) : null; }
  catch (e) { devWarn(`offline.readCatalog(${key})`, e); return null; }
}

// Sync every pending item. A network error stops the run and keeps the item
// queued; a server rejection (4xx) flags the item with the reason so the cashier
// can see WHY and decide (retry after fixing stock, or discard).
export async function syncQueue(api) {
  let current = getQueue();
  const todo = current.filter((i) => i.status !== "failed");
  if (!todo.length) return { synced: 0, failed: 0, offline: false, queue: current };

  let synced = 0;
  let failed = 0;
  let offline = false;

  for (const item of todo) {
    if (offline) break;
    try {
      await api.post("/sales", item.body);
      synced++;
      current = current.filter((i) => i.id !== item.id);
    } catch (e) {
      if (e.response) {
        failed++;
        const detail = e.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : "Ditolak server (validasi/stok)";
        current = current.map((i) =>
          i.id === item.id ? { ...i, status: "failed", attempts: (i.attempts || 0) + 1, error: msg } : i
        );
      } else {
        offline = true;
        current = current.map((i) =>
          i.id === item.id ? { ...i, attempts: (i.attempts || 0) + 1 } : i
        );
      }
    }
    setQueue(current);
  }

  if (synced > 0) write(SYNC_KEY, new Date().toISOString());
  return { synced, failed, offline, queue: getQueue() };
}
