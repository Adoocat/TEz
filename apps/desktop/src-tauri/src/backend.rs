//! Starts the Python backend and reports its state to the UI (ADR 0001).
//!
//! Contract with `tez-backend serve --token-stdin`: we write a fresh token as the first stdin
//! line (never argv or env, which other processes can read); it answers on stdout with
//! `TEZ_READY {"port": N}` or `TEZ_ERROR {"code": ..., "params": {...}}`, and shuts down
//! when its stdin closes. The UI asks with the `backend_status` command and follows the
//! `backend-status` event.

use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::Mutex;

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};

#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum BackendStatus {
    Starting,
    Ready { port: u16, token: String },
    Failed { code: String, params: Value },
}

impl BackendStatus {
    fn failed(code: &str, params: Value) -> Self {
        BackendStatus::Failed {
            code: code.to_string(),
            params,
        }
    }
}

/// What a line on the backend's stdout means, if anything.
pub fn parse_handshake(line: &str, token: &str) -> Option<BackendStatus> {
    let line = line.trim();
    if let Some(payload) = line.strip_prefix("TEZ_READY ") {
        let port = serde_json::from_str::<Value>(payload).ok()?["port"].as_u64()?;
        return Some(BackendStatus::Ready {
            port: u16::try_from(port).ok()?,
            token: token.to_string(),
        });
    }
    if let Some(payload) = line.strip_prefix("TEZ_ERROR ") {
        let value: Value = serde_json::from_str(payload).ok()?;
        let code = value["code"].as_str()?.to_string();
        let params = value.get("params").cloned().unwrap_or_else(|| json!({}));
        return Some(BackendStatus::Failed { code, params });
    }
    None
}

pub struct Backend {
    status: Mutex<BackendStatus>,
    // Kept open for the life of the app: closing it tells the backend to shut down.
    stdin: Mutex<Option<ChildStdin>>,
    #[cfg(windows)]
    job: Option<crate::job::Job>,
}

impl Backend {
    pub fn new() -> Self {
        Backend {
            status: Mutex::new(BackendStatus::Starting),
            stdin: Mutex::new(None),
            #[cfg(windows)]
            job: match crate::job::Job::new() {
                Ok(job) => Some(job),
                Err(error) => {
                    eprintln!("tez: cannot create a job object: {error}");
                    None
                }
            },
        }
    }

    pub fn status(&self) -> BackendStatus {
        self.status.lock().unwrap().clone()
    }

    /// Graceful shutdown: EOF on stdin. The job object covers crashes and forced kills.
    pub fn shut_down(&self) {
        self.stdin.lock().unwrap().take();
    }
}

fn set_status(app: &AppHandle, status: BackendStatus) {
    *app.state::<Backend>().status.lock().unwrap() = status.clone();
    let _ = app.emit("backend-status", status);
}

fn new_token() -> String {
    let mut buf = [0u8; 32];
    getrandom::fill(&mut buf).expect("OS random generator unavailable");
    buf.iter().map(|b| format!("{b:02x}")).collect()
}

/// Debug builds run the backend from the source tree with uv and the development library
/// that `pnpm dev` uses; release builds run the bundled `tez-backend` next to the app on the
/// user's library.
fn backend_command(library: &Path) -> Command {
    let mut command = if cfg!(debug_assertions) {
        let backend = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../backend");
        let mut c = Command::new("uv");
        c.args(["run", "--project"]).arg(backend).arg("tez-backend");
        c
    } else {
        let exe = std::env::current_exe().unwrap_or_default();
        let name = if cfg!(windows) {
            "tez-backend.exe"
        } else {
            "tez-backend"
        };
        Command::new(exe.with_file_name(name))
    };
    command
        .args(["serve", "--token-stdin", "--create", "--library"])
        .arg(library)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    command
}

pub fn library_path(app: &AppHandle) -> PathBuf {
    if cfg!(debug_assertions) {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../backend/.dev/TEz Library")
    } else {
        // Until the welcome screen lets the user choose (docs/progress.md, open question 1).
        app.path()
            .document_dir()
            .unwrap_or_else(|_| std::env::temp_dir())
            .join("TEz Library")
    }
}

pub fn spawn(app: &AppHandle) {
    let library = library_path(app);
    let token = new_token();
    let mut child: Child = match backend_command(&library).spawn() {
        Ok(child) => child,
        Err(error) => {
            set_status(
                app,
                BackendStatus::failed(
                    "backend.start_failed",
                    json!({ "reason": error.to_string() }),
                ),
            );
            return;
        }
    };

    let backend = app.state::<Backend>();
    #[cfg(windows)]
    if let Some(job) = &backend.job {
        if let Err(error) = job.assign(child.id()) {
            eprintln!("tez: job assignment failed for pid {}: {error}", child.id());
        }
    }

    let mut stdin = child.stdin.take().expect("stdin is piped");
    if let Err(error) = writeln!(stdin, "{token}").and_then(|_| stdin.flush()) {
        set_status(
            app,
            BackendStatus::failed(
                "backend.start_failed",
                json!({ "reason": error.to_string() }),
            ),
        );
        return;
    }
    *backend.stdin.lock().unwrap() = Some(stdin);

    let stdout = child.stdout.take().expect("stdout is piped");
    let app = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            let Ok(line) = line else { break };
            if let Some(status) = parse_handshake(&line, &token) {
                set_status(&app, status);
            }
        }
        // stdout closed: the backend exited. Unless it said why, report it.
        let code = child.wait().ok().and_then(|s| s.code());
        let shutting_down = app.state::<Backend>().stdin.lock().unwrap().is_none();
        let current = app.state::<Backend>().status();
        if !shutting_down && !matches!(current, BackendStatus::Failed { .. }) {
            set_status(
                &app,
                BackendStatus::failed("backend.exited", json!({ "exit_code": code })),
            );
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ready_line_gives_port_and_our_token() {
        assert_eq!(
            parse_handshake("TEZ_READY {\"port\": 5123, \"pid\": 9}\n", "tok"),
            Some(BackendStatus::Ready {
                port: 5123,
                token: "tok".into()
            })
        );
    }

    #[test]
    fn error_line_gives_code_and_params() {
        let line = r#"TEZ_ERROR {"code": "library.locked", "params": {"pid": 42}}"#;
        assert_eq!(
            parse_handshake(line, "tok"),
            Some(BackendStatus::Failed {
                code: "library.locked".into(),
                params: json!({"pid": 42})
            })
        );
    }

    #[test]
    fn other_or_broken_lines_are_ignored() {
        assert_eq!(parse_handshake("hello", "tok"), None);
        assert_eq!(parse_handshake("TEZ_READY not-json", "tok"), None);
        assert_eq!(parse_handshake("TEZ_READY {\"port\": 70000}", "tok"), None);
        assert_eq!(parse_handshake("TEZ_ERROR {\"params\": {}}", "tok"), None);
    }

    #[test]
    fn status_serializes_for_the_ui() {
        let ready = serde_json::to_value(BackendStatus::Ready {
            port: 1,
            token: "t".into(),
        })
        .unwrap();
        assert_eq!(ready, json!({"status": "ready", "port": 1, "token": "t"}));
        let starting = serde_json::to_value(BackendStatus::Starting).unwrap();
        assert_eq!(starting, json!({"status": "starting"}));
    }
}
