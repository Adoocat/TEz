//! S1 spike: start the Python sidecar with a token, discover its port from
//! stdout, tie its lifetime to ours with a Windows Job Object, and forward
//! second-instance arguments / tez:// links to the running window.

use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use serde_json::{json, Map, Value};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[cfg(windows)]
mod job;

#[derive(Serialize, Clone)]
struct BackendInfo {
    port: u16,
    token: String,
    pid: u32,
}

#[derive(Serialize, Clone)]
struct Forwarded {
    source: &'static str,
    args: Vec<String>,
    cwd: String,
}

struct AppState {
    start: Instant,
    backend: Mutex<Option<BackendInfo>>,
    child: Mutex<Option<CommandChild>>,
    results: Mutex<Map<String, Value>>,
    initial_args: Vec<String>,
    #[cfg(windows)]
    job: Option<job::Job>,
}

impl AppState {
    fn since_start_ms(&self) -> f64 {
        self.start.elapsed().as_secs_f64() * 1000.0
    }

    fn record(&self, key: &str, value: Value) {
        let mut results = self.results.lock().unwrap();
        results.insert(key.to_string(), value);
        let path = results_path();
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        if let Err(e) = std::fs::write(&path, serde_json::to_vec_pretty(&*results).unwrap()) {
            eprintln!("cannot write {}: {e}", path.display());
        }
    }
}

fn results_path() -> PathBuf {
    std::env::temp_dir().join("tez-s1").join("run.json")
}

fn new_token() -> String {
    let mut buf = [0u8; 32];
    getrandom::fill(&mut buf).expect("OS random generator unavailable");
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

#[tauri::command]
fn backend_info(state: State<'_, AppState>) -> Option<BackendInfo> {
    state.backend.lock().unwrap().clone()
}

#[tauri::command]
fn initial_args(state: State<'_, AppState>) -> Vec<String> {
    state.initial_args.clone()
}

/// Record a timing mark (ms since process start) under `name`.
#[tauri::command]
fn mark(state: State<'_, AppState>, name: String) -> f64 {
    let ms = state.since_start_ms();
    state.record(&name, json!(ms));
    ms
}

#[tauri::command]
fn report(state: State<'_, AppState>, key: String, value: Value) {
    state.record(&key, value);
}

fn spawn_backend(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let state = app.state::<AppState>();
    let token = new_token();
    let t_spawn = state.since_start_ms();
    let (mut rx, mut child) = app.shell().sidecar("tez-backend")?.args(["serve"]).spawn()?;
    let pid = child.pid();

    #[cfg(windows)]
    match &state.job {
        Some(job) => {
            if let Err(e) = job.assign(pid) {
                eprintln!("job assignment failed for pid {pid}: {e}");
                state.record("job_assign_error", json!(e.to_string()));
            }
        }
        None => state.record("job_assign_error", json!("no job object")),
    }

    // The token goes over stdin so it never appears in the process list.
    child.write(format!("{token}\n").as_bytes())?;
    *state.child.lock().unwrap() = Some(child);
    state.record("sidecar_spawn_ms", json!(t_spawn));
    state.record("sidecar_pid", json!(pid));

    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            let state = app.state::<AppState>();
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    let Some(payload) = line.trim().strip_prefix("TEZ_READY ") else {
                        continue;
                    };
                    let port = serde_json::from_str::<Value>(payload)
                        .ok()
                        .and_then(|v| v["port"].as_u64())
                        .map(|p| p as u16);
                    match port {
                        Some(port) => {
                            let info = BackendInfo { port, token: token.clone(), pid };
                            *state.backend.lock().unwrap() = Some(info.clone());
                            state.record("sidecar_ready_ms", json!(state.since_start_ms()));
                            state.record("sidecar_port", json!(port));
                            let _ = app.emit("backend-ready", info);
                        }
                        None => state.record("sidecar_bad_ready", json!(line.trim())),
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    eprintln!("[tez-backend] {}", String::from_utf8_lossy(&bytes).trim_end());
                }
                CommandEvent::Terminated(payload) => {
                    state.record("sidecar_terminated", json!({ "code": payload.code }));
                    let _ = app.emit("backend-exited", payload.code);
                }
                _ => {}
            }
        }
    });
    Ok(())
}

fn focus_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let start = Instant::now();
    let started_unix_ms = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis() as u64;
    let _ = std::fs::remove_file(results_path());

    let state = AppState {
        start,
        backend: Mutex::new(None),
        child: Mutex::new(None),
        results: Mutex::new(Map::new()),
        initial_args: std::env::args().skip(1).collect(),
        #[cfg(windows)]
        job: match job::Job::new() {
            Ok(j) => Some(j),
            Err(e) => {
                eprintln!("cannot create job object: {e}");
                None
            }
        },
    };
    state.record("app_start_unix_ms", json!(started_unix_ms));
    state.record("app_pid", json!(std::process::id()));

    state.record("builder_start_ms", json!(state.since_start_ms()));
    let mut builder = tauri::Builder::default();

    // single-instance must be registered first (and before deep-link).
    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, args, cwd| {
            let fwd = Forwarded { source: "second-instance", args: args.into_iter().skip(1).collect(), cwd };
            app.state::<AppState>().record("last_forwarded", json!(fwd));
            let _ = app.emit("forwarded", fwd);
            focus_main(app);
        }));
    }

    let app = builder
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_shell::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![backend_info, initial_args, mark, report])
        .setup(|app| {
            use tauri_plugin_deep_link::DeepLinkExt;
            let st = app.state::<AppState>();
            st.record("setup_start_ms", json!(st.since_start_ms()));
            // Debug builds are not installed, so register the scheme for this user.
            #[cfg(all(debug_assertions, windows))]
            app.deep_link().register_all()?;

            let handle = app.handle().clone();
            app.deep_link().on_open_url(move |event| {
                let urls: Vec<String> = event.urls().iter().map(|u| u.to_string()).collect();
                let fwd = Forwarded { source: "deep-link", args: urls, cwd: String::new() };
                handle.state::<AppState>().record("last_deep_link", json!(fwd));
                let _ = handle.emit("forwarded", fwd);
                focus_main(&handle);
            });

            spawn_backend(app.handle())?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            // Graceful path. The job object covers crashes and forced kills.
            if let Some(child) = app.state::<AppState>().child.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
