import { Command } from "@tauri-apps/plugin-shell";

const PORT = 8765;
const URL = `http://127.0.0.1:${PORT}`;

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
      const res = await fetch(URL, { method: "HEAD", mode: "no-cors" });
      // no-cors means we can't read status, but if it doesn't throw, server is up
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
    console.log("Starting sidecar...");
    setLoadingText("Starting Frappe SQLite...");

    const cmd = Command.sidecar("binaries/frappe-sqlite", [
      "--port",
      String(PORT),
      "--no-browser",
    ]);

    cmd.on("close", (data) => {
      console.log(`Sidecar exited with code ${data.code}`);
    });

    cmd.on("error", (error) => {
      console.error("Sidecar error:", error);
    });

    cmd.stdout.on("data", (line) => {
      console.log("[sidecar stdout]", line);
    });

    cmd.stderr.on("data", (line) => {
      console.error("[sidecar stderr]", line);
    });

    await cmd.spawn();
    console.log("Sidecar spawned");

    await waitForServer();
    console.log("Server ready, navigating to", URL);

    window.location.href = URL;
  } catch (err) {
    console.error("Failed to start Frappe:", err);
    showError(err instanceof Error ? err.message : String(err));
  }
}

start();
