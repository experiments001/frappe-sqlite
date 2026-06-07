use serde::{Deserialize, Serialize};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
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

fn start_sidecar_process(app: &AppHandle, config: &DesktopConfig) -> Result<(), String> {
  let state: State<SidecarState> = app.state();
  if state.0.lock().map_err(|_| "Sidecar lock poisoned")?.is_some() {
    return Ok(());
  }

  let exe_path = env::current_exe().map_err(|err| format!("Failed to get current exe: {err}"))?;
  let exe_dir = exe_path
    .parent()
    .ok_or("Failed to get executable directory")?;
  let sidecar_path = exe_dir.join("frappe-sqlite");

  println!("[tauri] Executable dir: {:?}", exe_dir);
  println!("[tauri] Sidecar path: {:?}", sidecar_path);

  if !sidecar_path.exists() {
    return Err(format!("Sidecar not found at {}", sidecar_path.display()));
  }

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
fn save_setup(app: AppHandle, config: DesktopConfig) -> Result<(), String> {
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
  start_sidecar_process(&app, &config)?;
  app.emit("setup-complete", ()).ok();
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

fn build_menu(app: &tauri::App) -> tauri::Result<Menu<tauri::Wry>> {
  let file_menu = Submenu::with_items(
    app,
    "File",
    true,
    &[
      &MenuItem::with_id(app, "open_data_folder", "Open Data Folder", true, None::<&str>)?,
      &MenuItem::with_id(app, "open_site_folder", "Open Site Folder", true, None::<&str>)?,
      &MenuItem::with_id(app, "backup_site", "Backup Site...", true, None::<&str>)?,
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
      open_data_folder,
      open_site_folder,
      backup_site,
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
