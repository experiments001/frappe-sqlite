use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command as TokioCommand;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{AppHandle, Emitter, Manager, State};

const PORT: u16 = 8765;
const PRODUCT_DIR: &str = "FrappeSQLite";
const CONFIG_FILE: &str = "config.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopConfig {
  pub site_name: String,
  pub admin_email: String,
  pub admin_password: String,
  pub display_name: Option<String>,
  pub data_dir: String,
}

pub struct SidecarState(pub Mutex<Option<Child>>);

fn default_data_dir() -> PathBuf {
  dirs::home_dir()
    .unwrap_or_else(|| PathBuf::from("."))
    .join("Library")
    .join("Application Support")
    .join(PRODUCT_DIR)
}

fn config_path() -> PathBuf {
  default_data_dir().join(CONFIG_FILE)
}

fn site_path(config: &DesktopConfig) -> PathBuf {
  PathBuf::from(&config.data_dir).join("sites").join(&config.site_name)
}

fn read_config() -> Result<Option<DesktopConfig>, String> {
  let path = config_path();
  if !path.exists() {
    return Ok(None);
  }

  let raw = fs::read_to_string(&path).map_err(|err| format!("Failed to read config: {err}"))?;
  let config: DesktopConfig =
    serde_json::from_str(&raw).map_err(|err| format!("Failed to parse config: {err}"))?;
  Ok(Some(config))
}

fn write_config(config: &DesktopConfig) -> Result<(), String> {
  let path = config_path();
  if let Some(parent) = path.parent() {
    fs::create_dir_all(parent).map_err(|err| format!("Failed to create config directory: {err}"))?;
  }
  fs::create_dir_all(PathBuf::from(&config.data_dir).join("sites"))
    .map_err(|err| format!("Failed to create data directory: {err}"))?;

  let raw = serde_json::to_string_pretty(config)
    .map_err(|err| format!("Failed to serialize config: {err}"))?;
  fs::write(path, raw).map_err(|err| format!("Failed to write config: {err}"))
}

fn open_path(path: &Path) -> Result<(), String> {
  fs::create_dir_all(path).map_err(|err| format!("Failed to create folder: {err}"))?;
  Command::new("open")
    .arg(path)
    .spawn()
    .map_err(|err| format!("Failed to open folder: {err}"))?;
  Ok(())
}

fn sidecar_binary_path() -> Result<PathBuf, String> {
  let exe_path = env::current_exe().map_err(|err| format!("Failed to get current exe: {err}"))?;
  let exe_dir = exe_path
    .parent()
    .ok_or("Failed to get executable directory")?;
  let sidecar_path = exe_dir.join("frappe-sqlite");

  if !sidecar_path.exists() {
    return Err(format!("Sidecar not found at {}", sidecar_path.display()));
  }

  Ok(sidecar_path)
}

fn start_sidecar_process(app: &AppHandle, config: &DesktopConfig) -> Result<(), String> {
  let state: State<SidecarState> = app.state();
  if state.0.lock().map_err(|_| "Sidecar lock poisoned")?.is_some() {
    return Ok(());
  }

  let sidecar_path = sidecar_binary_path()?;

  println!("[tauri] Sidecar path: {:?}", sidecar_path);

  let child = Command::new(&sidecar_path)
    .args(["--port", &PORT.to_string(), "--no-browser"])
    .env("PYTHONUNBUFFERED", "1")
    .env("FRAPPE_SQLITE_DATA_DIR", &config.data_dir)
    .env("FRAPPE_SITE_NAME", &config.site_name)
    .env("FRAPPE_ADMIN_EMAIL", &config.admin_email)
    .env("FRAPPE_ADMIN_PASSWORD", &config.admin_password)
    .stdout(Stdio::inherit())
    .stderr(Stdio::inherit())
    .spawn()
    .map_err(|err| format!("Failed to spawn sidecar: {err}"))?;

  *state.0.lock().map_err(|_| "Sidecar lock poisoned")? = Some(child);
  println!("[tauri] Sidecar spawned successfully");
  Ok(())
}

fn run_lifecycle_command(args: &[&str]) -> Result<serde_json::Value, String> {
  let sidecar_path = sidecar_binary_path()?;
  let config = read_config()?.ok_or("Setup is required before running lifecycle commands")?;

  let mut cmd = Command::new(&sidecar_path);
  cmd.arg("lifecycle");
  cmd.args(args);
  cmd.env("PYTHONUNBUFFERED", "1");
  cmd.env("FRAPPE_SQLITE_DATA_DIR", &config.data_dir);
  cmd.env("FRAPPE_SITE_NAME", &config.site_name);
  cmd.stdout(Stdio::piped());
  cmd.stderr(Stdio::piped());

  let output = cmd
    .output()
    .map_err(|err| format!("Failed to run lifecycle command: {err}"))?;

  let stderr = String::from_utf8_lossy(&output.stderr);
  let stdout = String::from_utf8_lossy(&output.stdout);
  let trimmed = stdout.trim();

  // Strip RESULT: sentinel if present (all lifecycle commands now emit it)
  let json_str = if let Some(rest) = trimmed.strip_prefix("RESULT:") {
    rest.trim()
  } else {
    trimmed
  };

  // Try to parse as JSON even on failure so we can show clean error messages
  if !output.status.success() {
    if let Ok(json) = serde_json::from_str::<serde_json::Value>(json_str) {
      if let Some(error) = json.get("error").and_then(|v| v.as_str()) {
        return Err(error.to_string());
      }
    }
    return Err(format!(
      "Lifecycle command failed (exit code: {:?}): {}",
      output.status.code(),
      stderr
    ));
  }

  if json_str.is_empty() {
    return Ok(serde_json::Value::Null);
  }

  serde_json::from_str(json_str)
    .map_err(|err| format!("Failed to parse lifecycle output as JSON: {err}. stderr: {stderr}"))
}

async fn run_lifecycle_command_async(
  app: &tauri::AppHandle,
  args: &[&str],
  operation: &str,
) -> Result<serde_json::Value, String> {
  let sidecar_path = sidecar_binary_path()?;
  let config = read_config()?.ok_or("Setup is required before running lifecycle commands")?;

  let mut child = TokioCommand::new(&sidecar_path)
    .arg("lifecycle")
    .args(args)
    .env("PYTHONUNBUFFERED", "1")
    .env("FRAPPE_SQLITE_DATA_DIR", &config.data_dir)
    .env("FRAPPE_SITE_NAME", &config.site_name)
    .stdout(Stdio::piped())
    .stderr(Stdio::piped())
    .spawn()
    .map_err(|err| format!("Failed to spawn lifecycle command: {err}"))?;

  let stdout = child.stdout.take().expect("stdout was piped");
  let mut lines = BufReader::new(stdout).lines();
  let mut result_json: Option<serde_json::Value> = None;

  while let Some(line) = lines.next_line().await.map_err(|e| e.to_string())? {
    if let Some(json_str) = line.strip_prefix("PROGRESS:") {
      if let Ok(progress) = serde_json::from_str::<serde_json::Value>(json_str) {
        app.emit("lifecycle-progress", serde_json::json!({
          "operation": operation,
          "progress": progress,
        })).ok();
      }
    } else if let Some(json_str) = line.strip_prefix("RESULT:") {
      result_json = serde_json::from_str(json_str).ok();
    }
  }

  let status = child.wait().await.map_err(|e| e.to_string())?;

  match result_json {
    Some(v) => Ok(v),
    None if !status.success() => Err(format!("Lifecycle command failed (exit code: {:?})", status.code())),
    None => Err("Lifecycle command exited without emitting a RESULT line".into()),
  }
}

fn stop_sidecar(app: &AppHandle) -> Result<(), String> {
  let state: State<SidecarState> = app.state();
  let mut guard = state.0.lock().map_err(|_| "Sidecar lock poisoned")?;
  if let Some(mut child) = guard.take() {
    println!("[tauri] Stopping sidecar...");
    let _ = child.kill();
    let _ = child.wait();
  }
  Ok(())
}

fn restart_sidecar_with_site(app: &AppHandle, site_name: String) -> Result<(), String> {
  let mut config = read_config()?.ok_or("Setup is required before switching sites")?;
  config.site_name = site_name;
  write_config(&config)?;
  stop_sidecar(app)?;
  start_sidecar_process(app, &config)?;
  app.emit("site-switched", &config.site_name).ok();
  Ok(())
}

#[tauri::command]
fn get_setup_state() -> Result<serde_json::Value, String> {
  let config = read_config()?;
  Ok(serde_json::json!({
    "configured": config.is_some(),
    "config": config,
    "defaultDataDir": default_data_dir().to_string_lossy(),
    "port": PORT,
  }))
}

#[tauri::command]
fn save_setup(app: AppHandle, config: DesktopConfig, skip_start_server: Option<bool>) -> Result<(), String> {
  if config.site_name.trim().is_empty() {
    return Err("Site name is required".into());
  }
  if config.admin_email.trim().is_empty() {
    return Err("Administrator email is required".into());
  }
  if config.admin_password.trim().is_empty() {
    return Err("Administrator password is required".into());
  }
  if config.data_dir.trim().is_empty() {
    return Err("Data folder is required".into());
  }

  write_config(&config)?;
  if !skip_start_server.unwrap_or(false) {
    start_sidecar_process(&app, &config)?;
    app.emit("setup-complete", ()).ok();
  }
  Ok(())
}

#[tauri::command]
fn start_server(app: AppHandle) -> Result<(), String> {
  match read_config()? {
    Some(config) => start_sidecar_process(&app, &config),
    None => Err("Setup is required before starting Frappe".into()),
  }
}

#[tauri::command]
fn stop_server(app: AppHandle) -> Result<(), String> {
  stop_sidecar(&app)
}

#[tauri::command]
fn open_data_folder() -> Result<(), String> {
  let config = read_config()?.ok_or("Setup is required before opening data folder")?;
  open_path(Path::new(&config.data_dir))
}

#[tauri::command]
fn open_site_folder() -> Result<(), String> {
  let config = read_config()?.ok_or("Setup is required before opening site folder")?;
  open_path(&site_path(&config))
}

#[tauri::command]
fn backup_site() -> Result<String, String> {
  let config = read_config()?.ok_or("Setup is required before backup")?;
  let site_dir = site_path(&config);
  if !site_dir.exists() {
    return Err(format!("Site folder not found: {}", site_dir.display()));
  }

  let backup_dir = PathBuf::from(&config.data_dir).join("backups");
  fs::create_dir_all(&backup_dir).map_err(|err| format!("Failed to create backup folder: {err}"))?;
  let stamp = Command::new("date")
    .arg("+%Y%m%d-%H%M%S")
    .output()
    .map_err(|err| format!("Failed to create timestamp: {err}"))?;
  let stamp = String::from_utf8_lossy(&stamp.stdout).trim().to_string();
  let backup_path = backup_dir.join(format!("{}-backup-{}.zip", config.site_name, stamp));

  let status = Command::new("ditto")
    .arg("-c")
    .arg("-k")
    .arg("--sequesterRsrc")
    .arg("--keepParent")
    .arg(&site_dir)
    .arg(&backup_path)
    .status()
    .map_err(|err| format!("Failed to run backup: {err}"))?;
  if !status.success() {
    return Err("Backup command failed".into());
  }
  Ok(backup_path.to_string_lossy().to_string())
}

// Lifecycle commands

#[tauri::command]
fn list_sites() -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["site", "list"])
}

#[tauri::command]
async fn create_site(
  app: tauri::AppHandle,
  site: String,
  admin_password: Option<String>,
  apps: Option<String>,
  full_install: Option<bool>,
) -> Result<serde_json::Value, String> {
  let mut args = vec!["site", "create", &site];
  if let Some(true) = full_install {
    args.push("--full-install");
  }
  if let Some(pw) = &admin_password {
    args.push("--admin-password");
    args.push(pw);
  }
  // NOTE: --apps is not supported by lifecycle_cli.py create subcommand.
  // App installation must be done separately via install_app after site creation.
  run_lifecycle_command_async(&app, &args, "create_site").await
}

#[tauri::command]
fn drop_site(site: String, force: Option<bool>) -> Result<serde_json::Value, String> {
  let mut args = vec!["site", "drop", &site];
  if let Some(true) = force {
    args.push("--force");
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn clone_site(
  source: String,
  target: String,
  force: Option<bool>,
) -> Result<serde_json::Value, String> {
  let mut args = vec!["site", "clone", &source, &target];
  if let Some(true) = force {
    args.push("--force");
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn export_site(site: String, output: String) -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["site", "export", &site, "--output", &output])
}

#[tauri::command]
fn import_site(
  input: String,
  site: Option<String>,
  force: Option<bool>,
) -> Result<serde_json::Value, String> {
  let mut args = vec!["site", "import", &input];
  if let Some(s) = &site {
    args.push("--site");
    args.push(s);
  }
  if let Some(true) = force {
    args.push("--force");
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn list_apps() -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["app", "list"])
}

#[tauri::command]
fn add_app(source: String, branch: Option<String>) -> Result<serde_json::Value, String> {
  let mut args = vec!["app", "add", &source];
  if let Some(b) = &branch {
    args.push("--branch");
    args.push(b);
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn install_app(site: String, app: String) -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["app", "install", &site, &app])
}

#[tauri::command]
fn uninstall_app(
  site: String,
  app: String,
  force: Option<bool>,
) -> Result<serde_json::Value, String> {
  let mut args = vec!["app", "uninstall", &site, &app];
  if let Some(true) = force {
    args.push("--force");
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn update_app(app: Option<String>) -> Result<serde_json::Value, String> {
  let mut args = vec!["app", "update"];
  if let Some(a) = &app {
    args.push("--app");
    args.push(a);
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn remove_app(app: String, force: Option<bool>) -> Result<serde_json::Value, String> {
  let mut args = vec!["app", "remove", &app];
  if let Some(true) = force {
    args.push("--force");
  }
  run_lifecycle_command(&args)
}

#[tauri::command]
fn migrate_site(site: String) -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["site", "migrate", &site])
}

#[tauri::command]
fn migrate_all_sites() -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["migrate", "all"])
}

#[tauri::command]
fn check_rebuild_needed() -> Result<serde_json::Value, String> {
  run_lifecycle_command(&["check-rebuild"])
}

fn build_menu(app: &tauri::App) -> tauri::Result<Menu<tauri::Wry>> {
  let file_menu = Submenu::with_items(
    app,
    "File",
    true,
    &[
      &MenuItem::with_id(app, "manage_sites", "Sites...", true, None::<&str>)?,
      &MenuItem::with_id(app, "manage_apps", "Apps...", true, None::<&str>)?,
      &MenuItem::with_id(app, "maintenance", "Maintenance...", true, None::<&str>)?,
      &PredefinedMenuItem::separator(app)?,
      &MenuItem::with_id(app, "open_data_folder", "Open Data Folder", true, None::<&str>)?,
      &MenuItem::with_id(app, "open_site_folder", "Open Current Site Folder", true, None::<&str>)?,
      &MenuItem::with_id(app, "export_current_site", "Export Current Site...", true, None::<&str>)?,
      &PredefinedMenuItem::separator(app)?,
      &PredefinedMenuItem::quit(app, Some("Quit"))?,
    ],
  )?;
  Menu::with_items(app, &[&file_menu])
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .manage(SidecarState(Mutex::new(None)))
    .invoke_handler(tauri::generate_handler![
      get_setup_state,
      save_setup,
      start_server,
      stop_server,
      open_data_folder,
      open_site_folder,
      backup_site,
      list_sites,
      create_site,
      drop_site,
      clone_site,
      export_site,
      import_site,
      list_apps,
      add_app,
      install_app,
      uninstall_app,
      update_app,
      remove_app,
      migrate_site,
      migrate_all_sites,
      check_rebuild_needed,
    ])
    .setup(|app| {
      let menu = build_menu(app)?;
      app.set_menu(menu)?;
      if let Some(config) = read_config().map_err(anyhow::Error::msg)? {
        start_sidecar_process(app.handle(), &config).map_err(anyhow::Error::msg)?;
      }
      Ok(())
    })
    .on_menu_event(|app, event| {
      let result = match event.id().as_ref() {
        "open_data_folder" => open_data_folder(),
        "open_site_folder" => open_site_folder(),
        "backup_site" => backup_site().map(|path| {
          let _ = Command::new("open").arg("-R").arg(path).spawn();
        }),
        "manage_sites" => {
          app.emit("open-manage-sites", ()).ok();
          Ok(())
        }
        "manage_apps" => {
          app.emit("open-manage-apps", ()).ok();
          Ok(())
        }
        "maintenance" => {
          app.emit("open-maintenance", ()).ok();
          Ok(())
        }
        "export_current_site" => {
          if let Ok(Some(config)) = read_config() {
            app.emit("export-site-requested", &config.site_name).ok();
          }
          Ok(())
        }
        _ => Ok(()),
      };
      if let Err(err) = result {
        eprintln!("[tauri] menu action failed: {err}");
        app.emit("desktop-error", err).ok();
      }
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(|app_handle, event| {
    if let tauri::RunEvent::ExitRequested { .. } = event {
      let state: State<SidecarState> = app_handle.state();
      if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
          println!("[tauri] Killing sidecar on exit...");
          let _ = child.kill();
          let _ = child.wait();
        }
      };
    }
  });
}
