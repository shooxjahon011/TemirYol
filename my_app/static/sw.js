// Service Worker: sw.js
self.addEventListener('install', (event) => {
    console.log("Service Worker o'rnatilmoqda..."");
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('Service Worker faollashdi.');
});

// Fondagi xabarlarni tutish (ixtiyoriy)
self.addEventListener('fetch', (event) => {
    // Bu yer bo'sh tursa ham bo'ladi, lekin funksiya bo'lishi shart
});