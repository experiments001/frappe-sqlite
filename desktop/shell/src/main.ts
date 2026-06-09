import { invoke } from "@tauri-apps/api/core";
import { listen, Event, type UnlistenFn } from "@tauri-apps/api/event";

const PORT = 8765;
const LOGIN_URL = `http://127.0.0.1:${PORT}/login`;

type SetupState = {
  configured: boolean;
  defaultDataDir: string;
  port: number;
  config?: DesktopConfig;
};

type DesktopConfig = {
  siteName: string;
  adminEmail: string;
  adminPassword: string;
  displayName?: string;
  dataDir: string;
};

type AppListResult = {
  available_apps?: string[];
  installed_by_site?: Record<string, string[]>;
  suggested_apps?: string[];
};

let currentConfig: DesktopConfig | null = null;
let currentSiteName = "";
let currentPort = PORT;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function forcePaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
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
  for (const id of ["setup", "loading", "error"]) {
    qs<HTMLElement>(`#${id}`).style.display = "none";
  }
  qs<HTMLElement>("#frappe-frame").style.display = "block";
  qs<HTMLIFrameElement>("#frappe-iframe").src = LOGIN_URL;
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

function getSelectedApps(): string {
  const apps: string[] = [];
  const checkboxes = document.querySelectorAll<HTMLInputElement>(".app-checkbox:checked");
  for (const cb of checkboxes) {
    if (cb.value && cb.value !== "frappe") apps.push(cb.value);
  }
  const customUrl = qs<HTMLInputElement>("#custom-app-url").value.trim();
  if (customUrl && qs<HTMLInputElement>("#app-custom").checked) {
    apps.push(customUrl);
  }
  return apps.join(",");
}

function wireSetup(defaultDataDir: string) {
  qs<HTMLInputElement>("#data-dir").value = defaultDataDir;
  qs<HTMLInputElement>("#site-name").value = "my-site.local";

  const customCheckbox = qs<HTMLInputElement>("#app-custom");
  const customUrlInput = qs<HTMLInputElement>("#custom-app-url");
  customCheckbox.addEventListener("change", () => {
    customUrlInput.style.display = customCheckbox.checked ? "block" : "none";
  });

  qs<HTMLFormElement>("#setup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    show("loading");
    const config = readSetupForm();
    const apps = getSelectedApps();
    try {
      setLoadingText("Saving configuration...");
      await invoke("save_setup", { config, skipStartServer: true });
      setLoadingText("Creating SQLite site...");
      const result = await invoke("create_site", {
        site: config.siteName,
        adminPassword: config.adminPassword,
        fullInstall: true,
      });
      const res = result as Record<string, unknown> | null;
      if (res && res.error) {
        throw new Error(String(res.error));
      }
      // Install selected apps separately (create_site doesn't accept --apps)
      if (apps) {
        const appList = apps.split(",").map((a) => a.trim()).filter(Boolean);
        for (const app of appList) {
          setLoadingText(`Installing app ${app}...`);
          await invoke("install_app", { site: config.siteName, app });
        }
      }
      setLoadingText("Starting Frappe...");
      await invoke("start_server");
      await waitForServer();
      window.location.replace(LOGIN_URL);
    } catch (err) {
      show("setup");
      qs<HTMLElement>("#setup-message").textContent = String(err);
    }
  });
}

// Toast notifications
function showToast(message: string, type: "error" | "success" = "error") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}-toast`;
  toast.textContent = message;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, type === "error" ? 6000 : 3000);
}

function showErrorToast(message: string) {
  showToast(message, "error");
}

function showSuccessToast(message: string) {
  showToast(message, "success");
}

// Dialog utilities
function openDialog(selector: string) {
  qs<HTMLElement>(selector).style.display = "flex";
}

function closeDialog(selector: string) {
  qs<HTMLElement>(selector).style.display = "none";
}

function clearDialogMessages(dialogSelector: string) {
  const dialog = qs<HTMLElement>(dialogSelector);
  dialog.querySelector<HTMLElement>(".error-block")!.style.display = "none";
  dialog.querySelector<HTMLElement>(".error-block")!.textContent = "";
  dialog.querySelector<HTMLElement>(".success-block")!.style.display = "none";
  dialog.querySelector<HTMLElement>(".success-block")!.textContent = "";
}

function setDialogProgress(dialogSelector: string, active: boolean, text?: string) {
  const dialog = qs<HTMLElement>(dialogSelector);
  const progress = dialog.querySelector<HTMLElement>(".progress-panel")!;
  const progressText = dialog.querySelector<HTMLElement>(".progress-text")!;
  progress.style.display = active ? "flex" : "none";
  if (text) progressText.textContent = text;

  // Hide sub-forms while working so only the spinner is visible
  if (active) {
    hideAllSubForms(dialogSelector);
    clearDialogMessages(dialogSelector);
    dialog.querySelectorAll<HTMLButtonElement>(".sub-form-actions button, .dialog-footer button").forEach((b) => {
      b.disabled = true;
    });
  } else {
    dialog.querySelectorAll<HTMLButtonElement>(".sub-form-actions button, .dialog-footer button").forEach((b) => {
      b.disabled = false;
    });
  }
}

function showDialogError(dialogSelector: string, message: string) {
  const dialog = qs<HTMLElement>(dialogSelector);
  const el = dialog.querySelector<HTMLElement>(".error-block")!;
  el.textContent = message;
  el.style.display = "block";
}

function showDialogSuccess(dialogSelector: string, message: string) {
  const dialog = qs<HTMLElement>(dialogSelector);
  const el = dialog.querySelector<HTMLElement>(".success-block")!;
  el.textContent = message;
  el.style.display = "block";
}

function hideAllSubForms(dialogSelector: string) {
  const dialog = qs<HTMLElement>(dialogSelector);
  dialog.querySelectorAll<HTMLElement>(".sub-form").forEach((el) => {
    el.style.display = "none";
  });
}

function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Sites Dialog
async function loadSites() {
  const list = qs<HTMLElement>("#sites-list");
  const current = qs<HTMLElement>("#sites-current");
  list.innerHTML = "";
  current.textContent = `Current site: ${escapeHtml(currentSiteName || "—")}`;

  try {
    const sites = (await invoke("list_sites")) as unknown[];
    if (!Array.isArray(sites) || sites.length === 0) {
      list.innerHTML = '<p class="empty-list">No sites found.</p>';
      return;
    }
    for (const site of sites) {
      const name = typeof site === "string" ? site : (site as Record<string, unknown>).site_name || String(site);
      const health = typeof site === "object" && site !== null ? (site as Record<string, unknown>).health || "" : "";
      const installedApps =
        typeof site === "object" && site !== null && Array.isArray((site as Record<string, unknown>).installed_apps)
          ? ((site as Record<string, unknown>).installed_apps as string[]).join(", ")
          : "";

      const row = document.createElement("div");
      row.className = "site-row";
      row.innerHTML = `
        <div class="site-info">
          <strong>${escapeHtml(String(name))}</strong>
          ${health ? `<span class="site-health">${escapeHtml(String(health))}</span>` : ""}
          ${installedApps ? `<div class="site-apps">Apps: ${escapeHtml(installedApps)}</div>` : ""}
        </div>
        <div class="site-actions">
          <button type="button" class="secondary btn-switch-site" data-site="${escapeHtml(String(name))}">Switch</button>
          <button type="button" class="secondary btn-export-site" data-site="${escapeHtml(String(name))}">Export</button>
          <button type="button" class="destructive btn-drop-site" data-site="${escapeHtml(String(name))}">Drop</button>
        </div>
      `;
      list.appendChild(row);
    }

    list.querySelectorAll<HTMLButtonElement>(".btn-switch-site").forEach((btn) => {
      btn.addEventListener("click", () => switchSite(btn.dataset.site!));
    });
    list.querySelectorAll<HTMLButtonElement>(".btn-export-site").forEach((btn) => {
      btn.addEventListener("click", () => {
        qs<HTMLInputElement>("#export-site-name").value = btn.dataset.site!;
        hideAllSubForms("#sites-dialog");
        qs<HTMLElement>("#sites-export-form").style.display = "block";
      });
    });
    list.querySelectorAll<HTMLButtonElement>(".btn-drop-site").forEach((btn) => {
      btn.addEventListener("click", () => handleDropSite(btn));
    });
  } catch (err) {
    list.innerHTML = `<div class="error-block">${escapeHtml(String(err))}</div>`;
  }
}

async function switchSite(siteName: string) {
  if (!currentConfig) {
    showErrorToast("No current configuration available.");
    return;
  }
  setDialogProgress("#sites-dialog", true, "Switching site...");
  try {
    const newConfig = { ...currentConfig, siteName };
    await invoke("save_setup", { config: newConfig, skipStartServer: true });
    await invoke("stop_server");
    await invoke("start_server");
    setDialogProgress("#sites-dialog", false);
    window.location.reload();
  } catch (err) {
    setDialogProgress("#sites-dialog", false);
    showDialogError("#sites-dialog", String(err));
  }
}

function handleDropSite(btn: HTMLButtonElement) {
  const siteName = btn.dataset.site!;
  if (!btn.dataset.confirm) {
    btn.textContent = "Confirm Archive";
    btn.dataset.confirm = "1";
    setTimeout(() => {
      btn.textContent = "Drop";
      delete btn.dataset.confirm;
    }, 5000);
    return;
  }
  dropSite(siteName, false);
}

async function dropSite(siteName: string, force: boolean) {
  setDialogProgress("#sites-dialog", true, force ? "Permanently deleting site..." : "Dropping site...");
  try {
    const result = await invoke("drop_site", { site: siteName, force });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#sites-dialog", false);
    showDialogSuccess("#sites-dialog", `Site ${siteName} dropped.`);
    await loadSites();
  } catch (err) {
    setDialogProgress("#sites-dialog", false);
    showDialogError("#sites-dialog", String(err));
  }
}

async function createSite() {
  const siteName = normalizeSiteName(qs<HTMLInputElement>("#new-site-name").value);
  const password = qs<HTMLInputElement>("#new-site-password").value;
  if (!siteName) return;
  setDialogProgress("#sites-dialog", true, "Creating site...");
  await forcePaint();

  let unlisten: UnlistenFn | null = null;
  try {
    unlisten = await listen<{ operation: string; progress: { stage: string; message: string; pct?: number } }>(
      "lifecycle-progress",
      ({ payload }) => {
        if (payload.operation === "create_site") {
          const pct = payload.progress.pct;
          const text = pct !== undefined
            ? `${payload.progress.message} (${pct}%)`
            : payload.progress.message;
          setDialogProgress("#sites-dialog", true, text);
        }
      }
    );

    const result = await invoke("create_site", {
      site: siteName,
      adminPassword: password || undefined,
      fullInstall: true,
    });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#sites-dialog", false);
    showDialogSuccess("#sites-dialog", `Site ${siteName} created.`);
    hideAllSubForms("#sites-dialog");
    await loadSites();
  } catch (err) {
    setDialogProgress("#sites-dialog", false);
    showDialogError("#sites-dialog", String(err));
  } finally {
    unlisten?.();
  }
}

async function cloneSite() {
  const source = qs<HTMLInputElement>("#clone-source").value.trim();
  const target = qs<HTMLInputElement>("#clone-target").value.trim();
  if (!source || !target) return;
  setDialogProgress("#sites-dialog", true, "Cloning site...");
  try {
    const result = await invoke("clone_site", { source, target });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#sites-dialog", false);
    showDialogSuccess("#sites-dialog", `Site cloned to ${target}.`);
    hideAllSubForms("#sites-dialog");
    await loadSites();
  } catch (err) {
    setDialogProgress("#sites-dialog", false);
    showDialogError("#sites-dialog", String(err));
  }
}

async function exportSite() {
  const siteName = qs<HTMLInputElement>("#export-site-name").value.trim();
  let output = qs<HTMLInputElement>("#export-site-output").value.trim();
  if (!siteName) return;
  if (!output) {
    output = `${currentConfig?.dataDir || "."}/backups/${siteName}-${Date.now()}.tar.gz`;
    qs<HTMLInputElement>("#export-site-output").value = output;
  }
  setDialogProgress("#sites-dialog", true, "Exporting site...");
  try {
    const result = await invoke("export_site", { site: siteName, output });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#sites-dialog", false);
    showDialogSuccess("#sites-dialog", `Site exported to ${output}.`);
    hideAllSubForms("#sites-dialog");
  } catch (err) {
    setDialogProgress("#sites-dialog", false);
    showDialogError("#sites-dialog", String(err));
  }
}

async function importSite() {
  const input = qs<HTMLInputElement>("#import-site-input").value.trim();
  const site = qs<HTMLInputElement>("#import-site-target").value.trim() || undefined;
  if (!input) return;
  setDialogProgress("#sites-dialog", true, "Importing site...");
  try {
    const result = await invoke("import_site", { input, site });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#sites-dialog", false);
    showDialogSuccess("#sites-dialog", "Site imported.");
    hideAllSubForms("#sites-dialog");
    await loadSites();
  } catch (err) {
    setDialogProgress("#sites-dialog", false);
    showDialogError("#sites-dialog", String(err));
  }
}

function showSitesDialog() {
  openDialog("#sites-dialog");
  clearDialogMessages("#sites-dialog");
  hideAllSubForms("#sites-dialog");
  loadSites();
}

// Apps Dialog
async function loadApps() {
  const container = qs<HTMLElement>("#apps-content");
  container.innerHTML = "";

  try {
    const data = (await invoke("list_apps")) as AppListResult;
    const available = data.available_apps || [];
    const installed = data.installed_by_site?.[currentSiteName] || [];
    const suggested = data.suggested_apps || [];

    let html = "";

    if (installed.length > 0) {
      html += `<h3>Installed on ${escapeHtml(currentSiteName)}</h3>`;
      html += `<div class="app-list">`;
      for (const app of installed) {
        html += `<div class="app-row"><span>${escapeHtml(app)}</span><button type="button" class="secondary btn-uninstall-app" data-app="${escapeHtml(app)}">Uninstall</button></div>`;
      }
      html += `</div>`;
    }

    if (available.length > 0) {
      html += `<h3>Available Apps</h3>`;
      html += `<div class="app-list">`;
      for (const entry of available) {
        const appName = typeof entry === "string" ? entry : (entry as Record<string, unknown>).app || String(entry);
        html += `<div class="app-row"><span>${escapeHtml(String(appName))}</span><button type="button" class="secondary btn-install-app" data-app="${escapeHtml(String(appName))}">Install</button></div>`;
      }
      html += `</div>`;
    }

    if (suggested.length > 0) {
      html += `<h3>Suggested Apps</h3>`;
      html += `<div class="app-list">`;
      for (const entry of suggested) {
        const appName = typeof entry === "string" ? entry : (entry as Record<string, unknown>).app || String(entry);
        html += `<div class="app-row"><span>${escapeHtml(String(appName))}</span><button type="button" class="secondary btn-install-app" data-app="${escapeHtml(String(appName))}">Install</button></div>`;
      }
      html += `</div>`;
    }

    container.innerHTML = html || '<p class="empty-list">No apps found.</p>';

    container.querySelectorAll<HTMLButtonElement>(".btn-install-app").forEach((btn) => {
      btn.addEventListener("click", () => installApp(btn.dataset.app!));
    });
    container.querySelectorAll<HTMLButtonElement>(".btn-uninstall-app").forEach((btn) => {
      btn.addEventListener("click", () => uninstallApp(btn.dataset.app!));
    });
  } catch (err) {
    container.innerHTML = `<div class="error-block">${escapeHtml(String(err))}</div>`;
  }
}

async function installApp(app: string) {
  setDialogProgress("#apps-dialog", true, `Installing ${app}...`);
  try {
    const result = await invoke("install_app", { site: currentSiteName, app });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#apps-dialog", false);
    showDialogSuccess("#apps-dialog", `${app} installed.`);
    await loadApps();
  } catch (err) {
    setDialogProgress("#apps-dialog", false);
    showDialogError("#apps-dialog", String(err));
  }
}

async function uninstallApp(app: string) {
  setDialogProgress("#apps-dialog", true, `Uninstalling ${app}...`);
  try {
    const result = await invoke("uninstall_app", { site: currentSiteName, app });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#apps-dialog", false);
    showDialogSuccess("#apps-dialog", `${app} uninstalled.`);
    await loadApps();
  } catch (err) {
    setDialogProgress("#apps-dialog", false);
    showDialogError("#apps-dialog", String(err));
  }
}

async function addApp() {
  const source = qs<HTMLInputElement>("#add-app-source").value.trim();
  const branch = qs<HTMLInputElement>("#add-app-branch").value.trim() || undefined;
  if (!source) return;
  setDialogProgress("#apps-dialog", true, `Adding ${source}...`);
  try {
    const result = await invoke("add_app", { source, branch });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#apps-dialog", false);
    showDialogSuccess("#apps-dialog", `${source} added.`);
    hideAllSubForms("#apps-dialog");
    await loadApps();
  } catch (err) {
    setDialogProgress("#apps-dialog", false);
    showDialogError("#apps-dialog", String(err));
  }
}

async function updateApp() {
  const app = qs<HTMLInputElement>("#update-app-name").value.trim() || undefined;
  setDialogProgress("#apps-dialog", true, app ? `Updating ${app}...` : "Updating all apps...");
  try {
    const result = await invoke("update_app", { app });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#apps-dialog", false);
    showDialogSuccess("#apps-dialog", app ? `${app} updated.` : "All apps updated.");
    hideAllSubForms("#apps-dialog");
    await loadApps();
  } catch (err) {
    setDialogProgress("#apps-dialog", false);
    showDialogError("#apps-dialog", String(err));
  }
}

async function removeApp() {
  const app = qs<HTMLInputElement>("#remove-app-name").value.trim();
  if (!app) return;
  setDialogProgress("#apps-dialog", true, `Removing ${app}...`);
  try {
    const result = await invoke("remove_app", { app });
    const res = result as Record<string, unknown> | null;
    if (res && res.error) {
      throw new Error(String(res.error));
    }
    setDialogProgress("#apps-dialog", false);
    showDialogSuccess("#apps-dialog", `${app} removed.`);
    hideAllSubForms("#apps-dialog");
    await loadApps();
  } catch (err) {
    setDialogProgress("#apps-dialog", false);
    showDialogError("#apps-dialog", String(err));
  }
}

function showAppsDialog() {
  openDialog("#apps-dialog");
  clearDialogMessages("#apps-dialog");
  hideAllSubForms("#apps-dialog");
  loadApps();
}

// Maintenance Dialog
function appendMaintenanceOutput(text: string) {
  const output = qs<HTMLElement>("#maintenance-output");
  const line = document.createElement("pre");
  line.textContent = text;
  output.appendChild(line);
  output.scrollTop = output.scrollHeight;
}

async function runMaintenance(action: () => Promise<unknown>, label: string) {
  setDialogProgress("#maintenance-dialog", true, label);
  try {
    const result = await action();
    const text = typeof result === "string" ? result : JSON.stringify(result, null, 2);
    appendMaintenanceOutput(`[${new Date().toLocaleTimeString()}] ${label}\n${text}`);
  } catch (err) {
    appendMaintenanceOutput(`[${new Date().toLocaleTimeString()}] ERROR: ${String(err)}`);
  } finally {
    setDialogProgress("#maintenance-dialog", false);
  }
}

function showMaintenanceDialog() {
  openDialog("#maintenance-dialog");
  clearDialogMessages("#maintenance-dialog");
  hideAllSubForms("#maintenance-dialog");
}

// Dialog wiring
function wireDialogs() {
  // Close buttons
  document.querySelectorAll<HTMLElement>(".dialog-close").forEach((btn) => {
    const dialog = btn.closest<HTMLElement>(".dialog-overlay");
    if (dialog) {
      btn.addEventListener("click", () => {
        dialog.style.display = "none";
      });
    }
  });

  // Cancel sub-form buttons
  document.querySelectorAll<HTMLElement>(".btn-cancel-subform").forEach((btn) => {
    btn.addEventListener("click", () => {
      const subForm = btn.closest<HTMLElement>(".sub-form");
      if (subForm) subForm.style.display = "none";
    });
  });

  // Sites dialog
  qs<HTMLButtonElement>("#btn-show-create-site").addEventListener("click", () => {
    hideAllSubForms("#sites-dialog");
    qs<HTMLElement>("#sites-create-form").style.display = "block";
  });
  qs<HTMLButtonElement>("#btn-do-create-site").addEventListener("click", createSite);

  qs<HTMLButtonElement>("#btn-show-clone-site").addEventListener("click", () => {
    hideAllSubForms("#sites-dialog");
    qs<HTMLElement>("#sites-clone-form").style.display = "block";
  });
  qs<HTMLButtonElement>("#btn-do-clone-site").addEventListener("click", cloneSite);

  qs<HTMLButtonElement>("#btn-show-import-site").addEventListener("click", () => {
    hideAllSubForms("#sites-dialog");
    qs<HTMLElement>("#sites-import-form").style.display = "block";
  });
  qs<HTMLButtonElement>("#btn-do-import-site").addEventListener("click", importSite);

  qs<HTMLButtonElement>("#btn-do-export-site").addEventListener("click", exportSite);

  // Apps dialog
  qs<HTMLButtonElement>("#btn-show-add-app").addEventListener("click", () => {
    hideAllSubForms("#apps-dialog");
    qs<HTMLElement>("#apps-add-form").style.display = "block";
  });
  qs<HTMLButtonElement>("#btn-do-add-app").addEventListener("click", addApp);

  qs<HTMLButtonElement>("#btn-show-update-app").addEventListener("click", () => {
    hideAllSubForms("#apps-dialog");
    qs<HTMLElement>("#apps-update-form").style.display = "block";
  });
  qs<HTMLButtonElement>("#btn-do-update-app").addEventListener("click", updateApp);

  qs<HTMLButtonElement>("#btn-show-remove-app").addEventListener("click", () => {
    hideAllSubForms("#apps-dialog");
    qs<HTMLElement>("#apps-remove-form").style.display = "block";
  });
  qs<HTMLButtonElement>("#btn-do-remove-app").addEventListener("click", removeApp);

  // Maintenance dialog
  qs<HTMLButtonElement>("#btn-migrate-site").addEventListener("click", () => {
    runMaintenance(() => invoke("migrate_site", { site: currentSiteName }), `Migrate ${currentSiteName}`);
  });
  qs<HTMLButtonElement>("#btn-migrate-all").addEventListener("click", () => {
    runMaintenance(() => invoke("migrate_all_sites"), "Migrate all sites");
  });
  qs<HTMLButtonElement>("#btn-check-rebuild").addEventListener("click", () => {
    runMaintenance(() => invoke("check_rebuild_needed"), "Check rebuild needed");
  });
  qs<HTMLButtonElement>("#btn-export-current").addEventListener("click", () => {
    const output = `${currentConfig?.dataDir || "."}/backups/${currentSiteName}-${Date.now()}.tar.gz`;
    runMaintenance(() => invoke("export_site", { site: currentSiteName, output }), `Export ${currentSiteName}`);
  });
}

// Main flow
async function start() {
  try {
    const state = await invoke<SetupState>("get_setup_state");
    currentPort = state.port || PORT;

    // Wire event listeners early
    await listen("open-manage-sites", () => showSitesDialog());
    await listen("open-manage-apps", () => showAppsDialog());
    await listen("open-maintenance", () => showMaintenanceDialog());
    await listen("export-site-requested", (event: Event<string>) => {
      showSitesDialog();
      const siteName = event.payload || currentSiteName;
      qs<HTMLInputElement>("#export-site-name").value = siteName;
      hideAllSubForms("#sites-dialog");
      qs<HTMLElement>("#sites-export-form").style.display = "block";
    });
    await listen("site-switched", () => window.location.reload());
    await listen("desktop-error", (event: Event<string>) => showErrorToast(event.payload));

    wireDialogs();

    if (!state.configured) {
      wireSetup(state.defaultDataDir);
      show("setup");
      return;
    }

    currentConfig = state.config || null;
    currentSiteName = currentConfig?.siteName || "";

    await launchFrappe();
  } catch (err) {
    showError(err instanceof Error ? err.message : String(err));
  }
}

start();
