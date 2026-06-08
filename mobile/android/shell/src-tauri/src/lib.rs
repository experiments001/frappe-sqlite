use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Emitter, Manager};

const PORT: u16 = 8765;
const PRODUCT_DIR: &str = "FrappeSQLite";
const CONFIG_FILE: &str = "config.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppConfig {
  pub site_name: String,
  pub admin_email: String,
  pub admin_password: String,
  pub display_name: Option<String>,
  pub data_dir: String,
}

fn default_data_dir() -> PathBuf {
  #[cfg(target_os = "android")]
  {
    // On Android, Tauri injects the app's filesDir
    PathBuf::from(
      std::env::var("FRAPPE_SQLITE_DATA_DIR")
        .unwrap_or_else(|_| "/data/data/com.frappe.sqlite-mobile/files".into())
    )
  }
  #[cfg(not(target_os = "android"))]
  {
    dirs::home_dir()
      .unwrap_or_else(|| PathBuf::from("."))
      .join("Library")
      .join("Application Support")
      .join(PRODUCT_DIR)
  }
}

fn config_path() -> PathBuf {
  default_data_dir().join(CONFIG_FILE)
}

fn read_config() -> Result<Option<AppConfig>, String> {
  let path = config_path();
  if !path.exists() {
    return Ok(None);
  }

  let raw = fs::read_to_string(&path).map_err(|err| format!("Failed to read config: {err}"))?;
  let config: AppConfig =
    serde_json::from_str(&raw).map_err(|err| format!("Failed to parse config: {err}"))?;
  Ok(Some(config))
}

fn write_config(config: &AppConfig) -> Result<(), String> {
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
fn save_setup(app: AppHandle, config: AppConfig) -> Result<(), String> {
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
  // Phase 1 stub: real server start happens in Phase 3 via Kotlin/Chaquopy bridge
  app.emit("setup-complete", ()).ok();
  Ok(())
}

#[tauri::command]
fn start_server(_app: AppHandle) -> Result<(), String> {
  // Phase 1 stub: on Android the server is started from Kotlin via Chaquopy
  // On desktop this would spawn the sidecar
  Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .invoke_handler(tauri::generate_handler![
      get_setup_state,
      save_setup,
      start_server,
    ])
    .setup(|app| {
      // On mobile we don't auto-start the sidecar — Kotlin handles it
      #[cfg(not(target_os = "android"))]
      {
        if let Some(config) = read_config().map_err(anyhow::Error::msg)? {
          // Desktop only: would start sidecar here
          let _ = config;
        }
      }
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
