// Offline transaction queue backed by localStorage. Server txn_id (unique index)
// guarantees idempotency, so re-sending a queued sale never duplicates it.
const KEY = "bam_offline_queue";

export function getQueue() {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
  catch { return []; }
}

export function setQueue(q) {
  localStorage.setItem(KEY, JSON.stringify(q));
}

export function enqueueSale(body) {
  const q = getQueue();
  q.push({ body, queued_at: Date.now() });
  setQueue(q);
  return q.length;
}

// Sync all queued sales. Network errors keep the item; server responses (2xx via
// idempotency, or 4xx genuine errors) remove it so we never loop forever.
export async function syncQueue(api) {
  const q = getQueue();
  if (!q.length) return { synced: 0, failed: 0, remaining: 0 };
  const remaining = [];
  let synced = 0, failed = 0;
  for (const item of q) {
    try {
      await api.post("/sales", item.body);
      synced++;
    } catch (e) {
      if (e.response) failed++;       // server rejected -> drop
      else remaining.push(item);      // no connection -> keep
    }
  }
  setQueue(remaining);
  return { synced, failed, remaining: remaining.length };
}
