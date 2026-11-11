//! TEz desktop shell: hosts the web UI and runs the Python backend as a sidecar (ADR 0001).
//! One instance only: a second launch (`tez <file>`, "Open with", a `tez://` link) hands its
//! arguments to the running window and exits (Task 22, ADR 0017).

mod backend;
#[cfg(windows)]
mod job;
mod open;

use backend::{Backend, BackendStatus};
use open::{OpenQueue, OpenRequest};
use tauri::{Manager, RunEvent, State};
use tauri_plugin_deep_link::DeepLinkExt;

#[tauri::command]
fn backend_status(backend: State<'_, Backend>) -> BackendStatus {
    backend.status()
}

/// The requests waiting for the UI: from this launch's arguments, or from later launches.
#[tauri::command]
fn take_open_requests(queue: State<'_, OpenQueue>) -> Vec<OpenRequest> {
    queue.take()
}

fn cwd() -> std::path::PathBuf {
    std::env::current_dir().unwrap_or_default()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        // First, so a second launch is caught before anything else starts.
        .plugin(tauri_plugin_single_instance::init(|app, argv, cwd| {
            let args: Vec<String> = argv.into_iter().skip(1).collect();
            open::deliver(app, open::classify(&args, std::path::Path::new(&cwd)));
        }))
        .plugin(tauri_plugin_deep_link::init())
        // Outside links (DOI, open-access PDFs) open in the user's browser.
        .plugin(tauri_plugin_opener::init())
        .manage(Backend::new())
        .manage(OpenQueue::default())
        .invoke_handler(tauri::generate_handler![backend_status, take_open_requests])
        .setup(|app| {
            backend::spawn(app.handle());
            // This launch's own arguments wait until the UI asks for them.
            let args: Vec<String> = std::env::args().skip(1).collect();
            app.state::<OpenQueue>().push(open::classify(&args, &cwd()));
            // On macOS links arrive as events rather than arguments.
            let handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                let urls: Vec<String> = event.urls().into_iter().map(|u| u.to_string()).collect();
                open::deliver(&handle, open::classify(&urls, &cwd()));
            });
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
