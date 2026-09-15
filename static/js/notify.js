function checkReminders(events) {
    const now = new Date();
    events.forEach(ev => {
        const eventTime = new Date(ev.date + "T" + ev.time);
        const diff = (eventTime - now) / 60000; 

        if (diff > 0 && diff < 10) { // 10 minute warning
            if (Notification.permission === "granted") {
                new Notification("⛪ Church Alert", { body: ev.title + " starts soon!" });
            }
        }
    });
}

// Request permissions on load
if ("Notification" in window) { Notification.requestPermission(); }