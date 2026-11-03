//! TEz desktop shell: hosts the web UI and runs the Python backend as a sidecar (ADR 0001).
//! Single instance and `tez://` links arrive in Task 22.

mod backend;
#[cfg(windows)]
mod job;

use backend::{Backend, BackendStatus};
use tauri::{Manager, RunEvent, State};

#[tauri::command]
fn backend_status(backend: State<'_, Backend>) -> BackendStatus {
    backend.status()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(Backend::new())
        .invoke_handler(tauri::generate_handler![backend_status])
        .setup(|app| {
            backend::spawn(app.handle());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building TEz");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            app.state::<Backend>().shut_down();
        }
    });
}
