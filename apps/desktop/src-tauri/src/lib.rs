//! TEz desktop shell. For now it only hosts the web UI; the backend sidecar (ADR 0001)
//! is wired in a later task.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running TEz");
}
