// v2: ya no se guardan en caché las respuestas de la API (gastos,
// presupuestos...) ni el login. Solo la página principal y los
// ficheros estáticos, para que la app abra aunque no haya red.
const CACHE = "expenses-v2";

const ARCHIVOS = [
    "/static/manifest.json"
];

self.addEventListener("install", function(e) {
    e.waitUntil(
        caches.open(CACHE).then(function(cache) {
            return cache.addAll(ARCHIVOS);
        })
    );
    self.skipWaiting();
});

// Borra las cachés antiguas (la v1 contenía datos de la API)
self.addEventListener("activate", function(e) {
    e.waitUntil(
        caches.keys().then(function(claves) {
            return Promise.all(
                claves.filter(function(k) { return k !== CACHE; })
                      .map(function(k) { return caches.delete(k); })
            );
        }).then(function() { return self.clients.claim(); })
    );
});

function sePuedeCachear(url) {
    return url.origin === self.location.origin &&
           (url.pathname === "/" || url.pathname.startsWith("/static/"));
}

self.addEventListener("fetch", function(e) {
    const url = new URL(e.request.url);

    // Peticiones que no son GET o que van a la API: directas a la red
    if (e.request.method !== "GET" || !sePuedeCachear(url)) return;

    e.respondWith(
        fetch(e.request)
            .then(function(res) {
                // No guardamos redirecciones (p. ej. "/" → "/login") ni errores
                if (res.ok && !res.redirected) {
                    var copia = res.clone();
                    caches.open(CACHE).then(function(cache) {
                        cache.put(e.request, copia);
                    });
                }
                return res;
            })
            .catch(function() {
                return caches.match(e.request);
            })
    );
});
