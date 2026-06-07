import { invoke } from "@tauri-apps/api/core";

const PORT = 8765;
const LOGIN_URL = `http://127.0.0.1:${PORT}/login`;

type SetupState = {
  configured: boolean;
  defaultDataDir: string;
};

type DesktopConfig = {
  siteName: string;
  adminEmail: string;
  adminPassword: string;
  displayName?: string;
  dataDir: string;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function qs<T extends HTMLElement>(selector: string): T {
  const el = document.querySelector<T>(selector);
  if (!el) throw new Error(`Missing element: ${selector}`);
  return el;
}

function show(view: "setup" | "loading" | "error") {
  for (const id of ["setup", "loading", "error"]) {
    qs<HTMLElement>(`#${id}`).style.display = id === view ? "flex" : "none";
  }
}

function setLoadingText(text: string) {
  qs<HTMLElement>("#loading-text").textContent = text;
}

function showError(message: string) {
  show("error");
  qs<HTMLElement>("#error").textContent = message;
}

function normalizeSiteName(value: string) {
  const cleaned = value.trim().toLowerCase().replace(/[^a-z0-9.-]/g, "-");
  return cleaned.includes(".") ? cleaned : `${cleaned || "site"}.local`;
}

async function waitForServer(attempts = 180): Promise<void> {
  for (let i = 0; i < attempts; i++) {
    setLoadingText(`Starting Frappe SQLite... (${i + 1}/${attempts})`);
    try {
      await fetch(LOGIN_URL, { method: "GET", mode: "no-cors", cache: "no-store" });
      return;
    } catch {
      await sleep(1000);
    }
  }
  throw new Error(`Frappe server did not become ready after ${attempts} seconds.`);
}

async function launchFrappe() {
  show("loading");
  await invoke("start_server");
  await waitForServer();
  window.location.replace(LOGIN_URL);
}

function readSetupForm(): DesktopConfig {
  return {
    siteName: normalizeSiteName(qs<HTMLInputElement>("#site-name").value),
    adminEmail: qs<HTMLInputElement>("#admin-email").value.trim(),
    adminPassword: qs<HTMLInputElement>("#admin-password").value,
    displayName: qs<HTMLInputElement>("#display-name").value.trim() || undefined,
    dataDir: qs<HTMLInputElement>("#data-dir").value.trim(),
  };
}

function wireSetup(defaultDataDir: string) {
  qs<HTMLInputElement>("#data-dir").value = defaultDataDir;
  qs<HTMLInputElement>("#site-name").value = "my-site.local";
  qs<HTMLFormElement>("#setup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    show("loading");
    setLoadingText("Creating local site...");
    try {
      await invoke("save_setup", { config: readSetupForm() });
      await waitForServer();
      window.location.replace(LOGIN_URL);
    } catch (err) {
      show("setup");
      qs<HTMLElement>("#setup-message").textContent = String(err);
    }
  });
}

async function start() {
  try {
    const state = await invoke<SetupState>("get_setup_state");
    if (!state.configured) {
      wireSetup(state.defaultDataDir);
      show("setup");
      return;
    }
    await launchFrappe();
  } catch (err) {
    showError(err instanceof Error ? err.message : String(err));
  }
}

start();
