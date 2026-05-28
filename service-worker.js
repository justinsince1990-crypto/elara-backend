self.addEventListener('push', function(event) {
    let data = { title: 'Elara', body: 'New message received' };
    if (event.data) {
        try { data = event.data.json(); }
        except (e) { data = { title: 'Elara', body: event.data.text() }; }
    }
    const options = {
        body: data.body,
        icon: '/icon.png',
        badge: '/badge.png',
        data: data.data || {}
    };
    event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(clients.openWindow('/'));
});
