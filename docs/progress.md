# İlerleme

Durum değerleri: bekliyor · sürüyor · incelemede · bitti · ertelendi

| Görev | Durum | Branch/PR | Not |
| --- | --- | --- | --- |
| S1 · Tauri + Python sidecar (risk denemesi) | bitti | `task/S1-tauri-sidecar` · #1 | 13/13 kontrol geçti. Kurulum paketi 15,2 MB, onedir 30,3 MB, ilk `/health` ~1,1 sn, `tez --help` 16 ms. Ayrıntı: ADR 0001 |
| 1 · Monorepo ve araçlar | bitti | `task/1-monorepo-tooling` · #2 | `pnpm check`: ruff, pyright, pytest, ESLint, tsc, Vitest, Prettier, cargo fmt/clippy. Tauri iskeleti burada kuruldu. Ayrıntı: ADR 0002 |
| 2 · CI | bitti | `task/2-ci` · #3 | GitHub Actions: python (3.12, 3.13), web, rust işleri; her biri `pnpm check <grup>` çalıştırır |
| 3 · Arka uç çekirdeği | bitti | `task/3-backend-core` · #5 | `TEZ_*` ayarları (pydantic-settings), JSON log + istek kimliği, `TezError`/`ErrorCode` hata modeli, Bearer token ara katmanı, `/health`; `serve --token-stdin` sidecar sözleşmesi (ADR 0001) gerçek süreçle test edildi |
| 4 · Veritabanı | bitti | `task/4-database` · #6 | `Database`: WAL, foreign_keys, busy_timeout, synchronous=NORMAL; yazma `BEGIN IMMEDIATE`; Alembic paket içinde, tek transaction, merdiven + model–migration tutarlılık testleri. Ayrıntı: ADR 0003 |
| 5 · Kütüphane klasörü | bitti | `task/5-library-folder` · #7 | `.tez/lock` işletim sistemi kilidi (çökmede kendiliğinden kalkar), `.tez/instance.json` (yalnız kullanıcıya açık; API adresi + token), `find_instance` (CLI için), `serve --library`, `GET /library`, şema güncellemesinden önce `backups/` yedeği; ikinci açılış `library.locked` + sahibin pid'i |
| 6 · Aşama 1 tabloları | bitti | `task/6-phase1-tables` · #8 | 20 tablo (migration 0002), 6 modülde model + repository; yalnız-ekleme tetikleyicileri, `supersedes_id`, aktif işlerde benzersiz `dedupe_key`; UUIDv7, UTC metin zaman, Türkçe güvenli `title_norm`. Ayrıntı: ADR 0004 |
| 6b · İş kuyruğu ve işçi süreci | bitti | `task/6b-job-queue` · #9 | Kira tabanlı kuyruk (`attempts` = ayrıcalık jetonu, geri çekilmeli yeniden deneme), `tez-backend worker`, API'de süpervizör (yeniden başlatma), `GET /jobs/events` SSE (`Last-Event-ID` ile devam). Kabul gerçek süreçlerle: öldürülen işçinin işi kira dolunca 2. denemede biter. Ayrıntı: ADR 0005 |
| 7 · API istemci üretimi | bitti | `task/7-api-client` · #11 | `pnpm gen:api`: `python -m tez.openapi` → `openapi.json` → openapi-typescript → `schema.d.ts`; `lib/api/client.ts` (openapi-fetch + token); `pnpm check api` CI'daki python işinde |
| 8 · Ön yüz kabuğu | bitti | `task/8-frontend-shell` · #12 | Kabuk (gezinme şeridi, kenar çubuğu, denetçi, durum çubuğu), hash yönlendirme, TanStack Query, tr/en, açık/koyu (token'lardan CSS değişkenleri), platform adaptörü, Ayarlar (dil, tema, e-posta, API anahtarları → keyring). Rust tarafı sidecar'ı başlatıyor. Ayrıntı: ADR 0006 |
| 9 · HTTP katmanı | bitti | `task/9-http-layer` · #13 | `tez.shared.http.HttpClient` (httpx2 + hishel + tenacity): kaynak başına hız sınırlayıcı, `Retry-After` uyumlu geri çekilme, istek başına isteğe bağlı önbellek; anahtarlar önbelleğin altında eklenir. 429 ve zaman aşımı gerçek soketli sahte sunucuyla test edildi. Ayrıntı: ADR 0007 |
