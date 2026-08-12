const CACHE = "normoscan-v1";
const ASSETS = ["/", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  // Offline queue for uploads: if POST /api/checks/upload fails due to offline, store in IndexedDB (simplified: return offline response)
  if (e.request.method === "GET" && url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(e.request).catch(()=> caches.match(e.request).then(r => r || new Response(JSON.stringify({offline:true}), {headers:{"Content-Type":"application/json"}})))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      if(e.request.method==="GET" && resp.ok) caches.open(CACHE).then(c=>c.put(e.request, resp.clone()));
      return resp;
    }).catch(()=> cached))
  );
});

// Background sync for offline uploads (simplified)
self.addEventListener("sync", e => {
  if(e.tag==="normoscan-uploads"){
    e.waitUntil((async()=>{
      // In real app, read IndexedDB and retry
      console.log("[SW] sync uploads");
    })());
  }
});
