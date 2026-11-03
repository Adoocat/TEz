//! `tez` console launcher (S1 spike).
//!
//! Windows GUI programs cannot write to the terminal, so `tez` is a separate
//! console program:
//! - window commands (`tez`, `tez <path>`, `tez tez://...`) start TEz.exe with
//!   absolute paths; the single-instance plugin forwards them to a running
//!   window, otherwise a new one opens;
//! - headless commands are delegated to `tez-backend cli` with inherited stdio.
//!
//! Installed layout (VS Code style, because `tez.exe` and `TEz.exe` would
//! collide on a case-insensitive file system):
//!   <install>/TEz.exe
//!   <install>/tez-backend.exe
//!   <install>/bin/tez.exe          <- this program, the folder that goes on PATH

use std::env;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};

const HEADLESS: &[&str] = &["hello", "search", "import", "add", "export", "list", "jobs", "backup", "prisma"];

const HELP: &str = "\
TEz — sistematik literatür taraması

Kullanım:
  tez                      Uygulamayı açar veya öne getirir
  tez <dosya.pdf|klasör>   Uygulamada açar (çalışan pencereye iletilir)
  tez tez://...            Bağlantıyı uygulamada açar
  tez hello [ad]           Başsız komut örneği (tez-backend cli)

Bayraklar:
  -h, --help               Bu yardımı gösterir
  -V, --version            Sürümü gösterir
";

fn install_dir() -> PathBuf {
    let exe = env::current_exe().unwrap_or_default();
    let dir = exe.parent().unwrap_or(Path::new("."));
    // bin/tez.exe -> install dir is the parent of bin/
    if dir.file_name().is_some_and(|n| n.eq_ignore_ascii_case("bin")) {
        dir.parent().unwrap_or(dir).to_path_buf()
    } else {
        dir.to_path_buf()
    }
}

fn locate(var: &str, file: &str) -> PathBuf {
    env::var_os(var).map(PathBuf::from).unwrap_or_else(|| install_dir().join(file))
}

/// `canonicalize` on Windows returns `\\?\C:\...`; strip it for readability.
fn absolute(p: &Path) -> std::io::Result<String> {
    let c = p.canonicalize()?;
    let s = c.to_string_lossy().into_owned();
    Ok(s.strip_prefix(r"\\?\").map(str::to_owned).unwrap_or(s))
}

fn launch_window(args: Vec<OsString>) -> ExitCode {
    let app = locate("TEZ_APP", "TEz.exe");
    let mut cmd = Command::new(&app);
    cmd.args(&args).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const DETACHED_PROCESS: u32 = 0x0000_0008;
        const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
        cmd.creation_flags(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP);
    }
    match cmd.spawn() {
        Ok(_) => {
            let shown: Vec<_> = args.iter().map(|a| a.to_string_lossy()).collect();
            if shown.is_empty() {
                println!("TEz açılıyor…");
            } else {
                println!("TEz'e gönderildi: {}", shown.join(" "));
            }
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("hata: TEz başlatılamadı ({}): {e}", app.display());
            eprintln!("ne yapmalı: kurulumu kontrol edin veya TEZ_APP ile yolu belirtin");
            ExitCode::FAILURE
        }
    }
}

fn run_headless(args: Vec<OsString>) -> ExitCode {
    let backend = locate("TEZ_BACKEND", "tez-backend.exe");
    match Command::new(&backend).arg("cli").args(args).status() {
        Ok(status) => ExitCode::from(status.code().unwrap_or(1).clamp(0, 255) as u8),
        Err(e) => {
            eprintln!("hata: tez-backend çalıştırılamadı ({}): {e}", backend.display());
            ExitCode::FAILURE
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    let Some(first) = args.first().map(|a| a.to_string_lossy().into_owned()) else {
        return launch_window(vec![]);
    };
    match first.as_str() {
        "-h" | "--help" => {
            print!("{HELP}");
            ExitCode::SUCCESS
        }
        "-V" | "--version" => {
            println!("tez {}", env!("CARGO_PKG_VERSION"));
            ExitCode::SUCCESS
        }
        cmd if HEADLESS.contains(&cmd) => run_headless(args),
        _ => {
            let mut out = Vec::with_capacity(args.len());
            for a in &args {
                let s = a.to_string_lossy();
                if s.starts_with("tez://") || s.starts_with("--") {
                    out.push(a.clone());
                    continue;
                }
                match absolute(Path::new(a)) {
                    Ok(p) => out.push(p.into()),
                    Err(_) => {
                        eprintln!("hata: dosya veya klasör bulunamadı: {s}");
                        eprintln!("ne yapmalı: yolu kontrol edin; yardım için `tez --help`");
                        return ExitCode::FAILURE;
                    }
                }
            }
            launch_window(out)
        }
    }
}
