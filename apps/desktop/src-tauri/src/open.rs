//! What TEz was asked to open: `tez`, `tez <file.pdf>`, `tez <refs.bib>`, `tez <folder>` and
//! `tez://` links (plan, "Terminal ve sistem entegrasyonu"; Task 22).
//!
//! Arguments are turned into requests here, where the paths can still be resolved against the
//! caller's working directory. Requests wait in a queue; the window is only told that there are
//! some (`open-requests`) and takes them with `take_open_requests`. So the first window, which
//! takes them when its UI starts, and a running window, told by a second launch, handle the
//! same command the same way.

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

/// Folders are searched this deep, and for at most this many PDFs: a home folder passed by
/// mistake must not freeze the app.
const MAX_DEPTH: usize = 4;
const MAX_PDFS: usize = 500;
pub const EVENT: &str = "open-requests";

#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum OpenRequest {
    /// Plain `tez`: bring the window forward.
    Focus,
    Pdf {
        path: String,
    },
    Import {
        path: String,
    },
    Folder {
        path: String,
        is_library: bool,
        pdfs: Vec<String>,
        truncated: bool,
    },
    /// A `tez://` link. Links only navigate; they never import or delete (plan, "Güvenlik").
    Link {
        url: String,
    },
    Missing {
        path: String,
    },
    Unsupported {
        path: String,
    },
}

fn display(path: &Path) -> String {
    path.to_string_lossy().into_owned()
}

fn extension(path: &Path) -> String {
    path.extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default()
}

fn collect_pdfs(folder: &Path, depth: usize, found: &mut Vec<PathBuf>) -> bool {
    let Ok(entries) = std::fs::read_dir(folder) else {
        return false;
    };
    let mut entries: Vec<PathBuf> = entries.filter_map(|e| e.ok().map(|e| e.path())).collect();
    entries.sort();
    for path in entries {
        if found.len() >= MAX_PDFS {
            return true;
        }
        if path.is_dir() {
            if depth < MAX_DEPTH && collect_pdfs(&path, depth + 1, found) {
                return true;
            }
        } else if extension(&path) == "pdf" {
            found.push(path);
        }
    }
    false
}

fn classify_one(argument: &str, cwd: &Path) -> OpenRequest {
    if argument.to_ascii_lowercase().starts_with("tez:") {
        return OpenRequest::Link {
            url: argument.to_string(),
        };
    }
    let given = PathBuf::from(argument);
    let path = if given.is_absolute() {
        given
    } else {
        cwd.join(given)
    };
    if path.is_dir() {
        let is_library = path.join("library.sqlite").is_file();
        let mut pdfs = Vec::new();
        let truncated = !is_library && collect_pdfs(&path, 0, &mut pdfs);
        return OpenRequest::Folder {
            path: display(&path),
            is_library,
            pdfs: pdfs.iter().map(|p| display(p)).collect(),
            truncated,
        };
    }
    if !path.is_file() {
        return OpenRequest::Missing {
            path: display(&path),
        };
    }
    match extension(&path).as_str() {
        "pdf" => OpenRequest::Pdf {
            path: display(&path),
        },
        "bib" | "bibtex" | "ris" => OpenRequest::Import {
            path: display(&path),
        },
        _ => OpenRequest::Unsupported {
            path: display(&path),
        },
    }
}

/// The requests in a command line. `args` excludes the program itself; options are skipped.
pub fn classify(args: &[String], cwd: &Path) -> Vec<OpenRequest> {
    let requests: Vec<OpenRequest> = args
        .iter()
        .filter(|a| !a.starts_with('-'))
        .map(|a| classify_one(a, cwd))
        .collect();
    if requests.is_empty() {
        vec![OpenRequest::Focus]
    } else {
        requests
    }
}

#[derive(Default)]
pub struct OpenQueue(Mutex<Vec<OpenRequest>>);

impl OpenQueue {
    pub fn push(&self, requests: Vec<OpenRequest>) {
        self.0.lock().unwrap().extend(requests);
    }

    pub fn take(&self) -> Vec<OpenRequest> {
        std::mem::take(&mut *self.0.lock().unwrap())
    }
}

/// Queue the requests and tell the window; bring it forward like `code .` does.
pub fn deliver(app: &AppHandle, requests: Vec<OpenRequest>) {
    app.state::<OpenQueue>().push(requests);
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
    if let Err(error) = app.emit(EVENT, ()) {
        eprintln!("tez: cannot tell the window about open requests: {error}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("tez-open-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn no_arguments_only_focus_the_window() {
        assert_eq!(classify(&[], Path::new(".")), vec![OpenRequest::Focus]);
        assert_eq!(
            classify(&["--flag".into()], Path::new(".")),
            vec![OpenRequest::Focus]
        );
    }

    #[test]
    fn files_are_resolved_against_the_callers_folder() {
        let dir = temp_dir("files");
        std::fs::write(dir.join("Kim 2024.PDF"), b"%PDF-1.4").unwrap();
        std::fs::write(dir.join("refs.bib"), b"@article{a,}").unwrap();
        std::fs::write(dir.join("scopus.ris"), b"TY  - JOUR").unwrap();
        std::fs::write(dir.join("notes.txt"), b"hi").unwrap();

        let got = classify(
            &[
                "Kim 2024.PDF".into(),
                "refs.bib".into(),
                "scopus.ris".into(),
                "notes.txt".into(),
                "gone.pdf".into(),
            ],
            &dir,
        );

        assert_eq!(
            got,
            vec![
                OpenRequest::Pdf {
                    path: display(&dir.join("Kim 2024.PDF"))
                },
                OpenRequest::Import {
                    path: display(&dir.join("refs.bib"))
                },
                OpenRequest::Import {
                    path: display(&dir.join("scopus.ris"))
                },
                OpenRequest::Unsupported {
                    path: display(&dir.join("notes.txt"))
                },
                OpenRequest::Missing {
                    path: display(&dir.join("gone.pdf"))
                },
            ]
        );
    }

    #[test]
    fn a_folder_lists_its_pdfs_and_a_library_is_recognised() {
        let dir = temp_dir("folder");
        std::fs::create_dir_all(dir.join("papers/2024")).unwrap();
        std::fs::write(dir.join("papers/a.pdf"), b"%PDF").unwrap();
        std::fs::write(dir.join("papers/2024/b.pdf"), b"%PDF").unwrap();
        std::fs::write(dir.join("papers/readme.md"), b"#").unwrap();
        let library = dir.join("lib");
        std::fs::create_dir_all(&library).unwrap();
        std::fs::write(library.join("library.sqlite"), b"").unwrap();

        let got = classify(&["papers".into(), display(&library)], &dir);

        assert_eq!(
            got,
            vec![
                OpenRequest::Folder {
                    path: display(&dir.join("papers")),
                    is_library: false,
                    pdfs: vec![
                        display(&dir.join("papers").join("2024").join("b.pdf")),
                        display(&dir.join("papers").join("a.pdf")),
                    ],
                    truncated: false,
                },
                OpenRequest::Folder {
                    path: display(&library),
                    is_library: true,
                    pdfs: vec![],
                    truncated: false,
                },
            ]
        );
    }

    #[test]
    fn links_pass_through_untouched() {
        assert_eq!(
            classify(&["tez://reader/abc?page=4".into()], Path::new(".")),
            vec![OpenRequest::Link {
                url: "tez://reader/abc?page=4".into()
            }]
        );
    }

    #[test]
    fn the_queue_hands_requests_out_once() {
        let queue = OpenQueue::default();
        queue.push(vec![OpenRequest::Focus]);
        queue.push(vec![OpenRequest::Link {
            url: "tez://library".into(),
        }]);

        assert_eq!(queue.take().len(), 2);
        assert!(queue.take().is_empty());
    }

    #[test]
    fn requests_serialize_for_the_ui() {
        let json = serde_json::to_value(OpenRequest::Pdf {
            path: "C:/a.pdf".into(),
        })
        .unwrap();
        assert_eq!(json, serde_json::json!({"kind": "pdf", "path": "C:/a.pdf"}));
    }
}
