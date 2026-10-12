/* Portal PWA service worker — shell only; never cache API/PDF/uploads */
const CACHE = "portal-pwa-shell-v4";
const PRECACHE = [
  "/m/",
  "/m/login",
  "/static/pwa/app.css",
  "/static/pwa/app.js",
  "/static/pwa/icons/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

function isUnsafe(url) {
  const p = url.pathname;
  if (p.startsWith("/api/")) return true;
  if (p.startsWith("/uploads/")) return true;
  if (p.startsWith("/m/pdf/")) return true;
  if (p.includes("/pdf")) return true;
  return false;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (isUnsafe(url)) return;

  // Network-first for HTML navigations; cache fallback for offline shell
  if (req.mode === "navigate" || (url.pathname === "/m/" || url.pathname === "/m/login")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match("/m/login")))
    );
    return;
  }

  // Static PWA assets: cache-first
  if (url.pathname.startsWith("/static/pwa/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
            return res;
          })
      )
    );
  }
});
