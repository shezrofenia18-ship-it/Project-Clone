/* Berkah Ayam Mili service worker — app-shell + catalog offline cache */
const CACHE = "bam-v3";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

// The very first page load is NOT controlled by this worker, so nothing it
// fetched (index.html + JS/CSS bundles) ever reached the cache — a reload while
// offline then showed a blank page. The page therefore reports back the list of
// resources it actually loaded and we warm the cache with them. This is also why
// we cannot hardcode a precache list: bundle filenames differ between dev & prod.
self.addEventListener("message", (e) => {
  const data = e.data || {};
  if (data.type !== "WARM_CACHE" || !Array.isArray(data.urls)) return;
  e.waitUntil(
    caches.open(CACHE).then(async (c) => {
      await Promise.all(
        data.urls.map(async (u) => {
          try {
            if (await c.match(u)) return;
            await c.add(u);
          } catch { /* skip unreachable asset */ }
        })
      );
    })
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.includes("/api/")) {
    if (url.pathname.includes("/api/products") || url.pathname.includes("/api/customers") || url.pathname.includes("/api/files/")) {
      e.respondWith(networkFirst(req));
    }
    return; // other API calls: let them go to network, don't cache
  }
  if (req.mode === "navigate") {
    e.respondWith(navHandler(req));
    return;
  }
  e.respondWith(staleWhileRevalidate(req));
});

// Serve from cache instantly (works offline) but refresh in the background so a
// new deploy is picked up on the next load instead of being stuck forever.
async function staleWhileRevalidate(req) {
  const c = await caches.open(CACHE);
  const hit = await c.match(req);
  const fetching = fetch(req)
    .then((res) => {
      if (res && res.ok) c.put(req, res.clone());
      return res;
    })
    .catch(() => null);
  if (hit) return hit;
  const res = await fetching;
  return res || Response.error();
}

async function networkFirst(req) {
  const c = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res && res.ok) c.put(req, res.clone());
    return res;
  } catch {
    const hit = await c.match(req);
    if (hit) return hit;
    throw new Error("offline");
  }
}

async function navHandler(req) {
  const c = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res && res.ok) c.put("/", res.clone());
    return res;
  } catch {
    // Offline: every SPA route must fall back to the cached app shell.
    return (
      (await c.match("/")) ||
      (await c.match("/index.html")) ||
      (await c.match(req)) ||
      new Response(
        "<!doctype html><meta charset=utf-8><title>Berkah Ayam Mili</title>" +
          "<body style=\"font-family:system-ui;padding:2rem;text-align:center\">" +
          "<h2>Sedang offline</h2><p>Aplikasi belum selesai disimpan untuk mode offline. " +
          "Sambungkan internet sekali lagi, lalu coba kembali.</p></body>",
        { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
      )
    );
  }
}
