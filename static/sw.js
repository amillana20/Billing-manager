const CACHE = "expenses-v1";

const ARCHIVOS = [
    "/",
    "/static/manifest.json"
];

self.addEventListener("install", function(e) {
    e.waitUntil(
        caches.open(CACHE).then(function(cache) {
            return cache.addAll(ARCHIVOS);
        })
    );
});

self.addEventListener("fetch", function(e) {
    e.respondWith(
        fetch(e.request)
            .then(function(res) {
                var copia = res.clone();
                caches.open(CACHE).then(function(cache) {
                    cache.put(e.request, copia);
                });
                return res;
            })
            .catch(function() {
                return caches.match(e.request);
            })
    );
});