const PORT = 8765;
const FRAPPE_URL = `http://127.0.0.1:${PORT}`;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setLoadingText(text: string) {
  const el = document.getElementById("loading-text");
  if (el) el.textContent = text;
}

function showError(message: string) {
  const loading = document.getElementById("loading");
  const error = document.getElementById("error");
  if (loading) loading.style.display = "none";
  if (error) {
    error.style.display = "flex";
    error.textContent = message;
  }
}

async function waitForServer(attempts = 60): Promise<void> {
  for (let i = 0; i < attempts; i++) {
    setLoadingText(`Starting Frappe SQLite... (${i + 1}/${attempts})`);
    try {
      const res = await fetch(FRAPPE_URL, { method: "HEAD", mode: "no-cors" });
      console.log(`Healthcheck attempt ${i + 1}: reachable`);
      return;
    } catch {
      console.log(`Healthcheck attempt ${i + 1}: not ready yet`);
    }
    await sleep(1000);
  }
  throw new Error(`Frappe server did not become ready after ${attempts} seconds.`);
}

async function start(): Promise<void> {
  try {
    console.log("Waiting for Frappe server...");
    setLoadingText("Starting Frappe SQLite...");

    await waitForServer();
    console.log("Server ready, navigating to", FRAPPE_URL);

    window.location.href = FRAPPE_URL;
  } catch (err) {
    console.error("Failed to start Frappe:", err);
    showError(err instanceof Error ? err.message : String(err));
  }
}

start();
