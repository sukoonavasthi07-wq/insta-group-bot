// =============================
// LOG STREAM (SSE)
// =============================
const logBox = document.getElementById("logs");
const evtSrc = new EventSource("/logs");

evtSrc.onmessage = function (event) {
    logBox.textContent += event.data + "\n";
    logBox.scrollTop = logBox.scrollHeight;
};

// =============================
// START BOT
// =============================
async function startBot() {
    const data = {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
        message: document.getElementById("message").value,
        custom_name: document.getElementById("custom_name").value,
        group_ids: document.getElementById("group_ids").value.split(",").map(x => x.trim()),
        delay: document.getElementById("delay").value,
        cyclone_delay: document.getElementById("cyclone_delay").value
    };

    const res = await fetch("/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });

    const json = await res.json();
    alert(json.message || json.error);
}

// =============================
// STOP BOT
// =============================
async function stopBot() {
    const res = await fetch("/stop", { method: "POST" });
    const json = await res.json();
    alert(json.message);
}
