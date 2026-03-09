// GutAgent Service Worker
// Provides offline caching and background sync

const CACHE_NAME = 'gutagent-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/app.jsx',
    '/manifest.json',
];

// External CDN assets to cache
const CDN_ASSETS = [
    'https://cdn.tailwindcss.com',
    'https://unpkg.com/react@18/umd/react.production.min.js',
    'https://unpkg.com/react-dom@18/umd/react-dom.production.min.js',
    'https://unpkg.com/@babel/standalone/babel.min.js',
    'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
];

// Install: cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            // Cache local assets
            cache.addAll(STATIC_ASSETS);
            // Cache CDN assets (these might fail, that's ok)
            CDN_ASSETS.forEach(url => {
                fetch(url).then(response => {
                    if (response.ok) {
                        cache.put(url, response);
                    }
                }).catch(() => {});
            });
        })
    );
    // Activate immediately
    self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            );
        })
    );
    // Take control immediately
    self.clients.claim();
});

// Fetch: serve from cache, fall back to network
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // Don't cache API calls - they need to be live
    if (url.pathname.startsWith('/api/')) {
        return;
    }
    
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                // Return cached version, but also update cache in background
                fetch(event.request).then((response) => {
                    if (response.ok) {
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, response);
                        });
                    }
                }).catch(() => {});
                return cachedResponse;
            }
            
            // Not in cache - fetch from network
            return fetch(event.request).then((response) => {
                // Cache successful responses for static assets
                if (response.ok && event.request.method === 'GET') {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            }).catch(() => {
                // Network failed and not in cache
                // Return a simple offline page for navigation requests
                if (event.request.mode === 'navigate') {
                    return new Response(
                        `<!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>GutAgent - Offline</title>
                            <style>
                                body {
                                    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                                    display: flex;
                                    flex-direction: column;
                                    align-items: center;
                                    justify-content: center;
                                    height: 100vh;
                                    margin: 0;
                                    background: #f9fafb;
                                    color: #374151;
                                    text-align: center;
                                    padding: 20px;
                                }
                                .emoji { font-size: 4rem; margin-bottom: 1rem; }
                                h1 { margin: 0 0 0.5rem; }
                                p { color: #6b7280; margin: 0 0 1.5rem; }
                                button {
                                    background: #065f46;
                                    color: white;
                                    border: none;
                                    padding: 12px 24px;
                                    border-radius: 8px;
                                    font-size: 1rem;
                                    cursor: pointer;
                                }
                            </style>
                        </head>
                        <body>
                            <div class="emoji">📡</div>
                            <h1>You're offline</h1>
                            <p>GutAgent needs an internet connection to chat.</p>
                            <button onclick="location.reload()">Try again</button>
                        </body>
                        </html>`,
                        { headers: { 'Content-Type': 'text/html' } }
                    );
                }
            });
        })
    );
});

// Handle messages from the app
self.addEventListener('message', (event) => {
    if (event.data === 'skipWaiting') {
        self.skipWaiting();
    }
});
