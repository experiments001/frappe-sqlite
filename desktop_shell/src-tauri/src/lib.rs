use std::process::{Command, Stdio, Child};
use std::env;
use std::sync::Mutex;
use tauri::Manager;

pub struct SidecarState(pub Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .manage(SidecarState(Mutex::new(None)))
    .setup(|app| {
      let exe_path = env::current_exe().expect("Failed to get current executable path");
      let exe_dir = exe_path.parent().expect("Failed to get executable directory");
      let sidecar_path = exe_dir.join("frappe-sqlite");
      
      println!("[tauri] Executable dir: {:?}", exe_dir);
      println!("[tauri] Sidecar path: {:?}", sidecar_path);
      
      if !sidecar_path.exists() {
        eprintln!("[tauri] ERROR: Sidecar not found at {:?}", sidecar_path);
      } else {
        println!("[tauri] Spawning sidecar...");
        let child = Command::new(&sidecar_path)
          .args(["--port", "8765", "--no-browser"])
          .env("PYTHONUNBUFFERED", "1")
          .stdout(Stdio::inherit())
          .stderr(Stdio::inherit())
          .spawn()
          .expect("Failed to spawn sidecar");
        
        let state: tauri::State<SidecarState> = app.state();
        *state.0.lock().unwrap() = Some(child);
        println!("[tauri] Sidecar spawned successfully");
      }
      
      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(|_app_handle, event| {
    if let tauri::RunEvent::ExitRequested { .. } = event {
      let state: tauri::State<SidecarState> = _app_handle.state();
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
