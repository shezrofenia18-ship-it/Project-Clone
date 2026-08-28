/* Berkah Ayam Mili service worker — app-shell + catalog offline cache */
const CACHE = "bam-v1";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
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
  e.respondWith(cacheFirst(req));
});

async function cacheFirst(req) {
  const c = await caches.open(CACHE);
  const hit = await c.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res && res.ok) c.put(req, res.clone());
    return res;
  } catch {
    return hit || Response.error();
  }
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
    return (await c.match("/")) || (await c.match(req)) || Response.error();
  }
}
