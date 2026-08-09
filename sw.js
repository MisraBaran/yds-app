// sw.js
// Uygulamayi tamamen cevrimdisi calisir hale getirir. CACHE_VERSION
// degistiginde eski onbellekler otomatik temizlenir.
const CACHE_VERSION = "yds-v2";
const CACHE_NAME = `yds-app-${CACHE_VERSION}`;

const APP_SHELL = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "css/styles.css",
  "js/app.js",
  "js/quiz.js",
  "js/dictionary.js",
  "js/storage.js",
  "js/srs.js",
  "js/stats.js",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-180.png",
  "icons/icon-192-maskable.png",
  "icons/icon-512-maskable.png",
  "data/questions/index.json",
  "data/dictionary.json",
  "data/vocab-frequency.json",
];

async function buildDataFileList() {
  const urls = [];
  try {
    const res = await fetch("data/questions/index.json");
    const index = await res.json();
    for (const s of index.sessions || []) {
      urls.push(`data/questions/${s.id}.json`);
    }
    for (const t of Object.keys(index.types || {})) {
      urls.push(`data/questions/by-type/${t}.json`);
    }
  } catch (e) {
    console.error("sw: index.json okunamadi, sadece app kabugu onbelleklenecek", e);
  }
  return urls;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await cache.addAll(APP_SHELL.map((u) => new Request(u, { cache: "reload" })));
      const dataFiles = await buildDataFileList();
      for (const url of dataFiles) {
        try {
          await cache.add(new Request(url, { cache: "reload" }));
        } catch (e) {
          console.error("sw: onbelleklenemedi", url, e);
        }
      }
      self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k.startsWith("yds-app-") && k !== CACHE_NAME).map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    (async () => {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      try {
        const network = await fetch(event.request);
        if (network.ok && event.request.url.startsWith(self.location.origin)) {
          const cache = await caches.open(CACHE_NAME);
          cache.put(event.request, network.clone());
        }
        return network;
      } catch (e) {
        if (event.request.mode === "navigate") {
          return caches.match("index.html");
        }
        throw e;
      }
    })()
  );
});
