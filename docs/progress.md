# İlerleme

Durum değerleri: bekliyor · sürüyor · incelemede · bitti · ertelendi

| Görev | Durum | Branch/PR | Not |
| --- | --- | --- | --- |
| S1 · Tauri + Python sidecar (risk denemesi) | bitti | `task/S1-tauri-sidecar` · #1 | 13/13 kontrol geçti. Kurulum paketi 15,2 MB, onedir 30,3 MB, ilk `/health` ~1,1 sn, `tez --help` 16 ms. Ayrıntı: ADR 0001 |
| 1 · Monorepo ve araçlar | bitti | `task/1-monorepo-tooling` · #2 | `pnpm check`: ruff, pyright, pytest, ESLint, tsc, Vitest, Prettier, cargo fmt/clippy. Tauri iskeleti burada kuruldu. Ayrıntı: ADR 0002 |
| 2 · CI | incelemede | `task/2-ci` | GitHub Actions: python (3.12, 3.13), web, rust işleri; her biri `pnpm check <grup>` çalıştırır |
| 3 · Arka uç çekirdeği | bekliyor | | |
| 4 · Veritabanı | bekliyor | | |
| 5 · Kütüphane klasörü | bekliyor | | |
| 6 · Aşama 1 tabloları | bekliyor | | |
| 6b · İş kuyruğu ve işçi süreci | bekliyor | | |
| 7 · API istemci üretimi | bekliyor | | |
| 8 · Ön yüz kabuğu | bekliyor | | |
| 9 · HTTP katmanı | bekliyor | | |
| 10 · Ortak kayıt şeması | bekliyor | | |
| 11 · Sağlayıcılar | bekliyor | | OpenAlex, Semantic Scholar, arXiv, Crossref — her biri ayrı PR |
| 12 · Tekilleştirme | bekliyor | | |
| 13 · Federe arama servisi | bekliyor | | |
| 14 · Arama arayüzü | bekliyor | | |
| 15 · BibTeX/RIS içe aktarma | bekliyor | | |
| 16 · PDF ekleme | bekliyor | | |
| 17 · Açık erişim PDF | bekliyor | | |
| 18 · Koleksiyon ve etiketler | bekliyor | | |
| 19 · Kütüphane listesi | bekliyor | | |
| 20 · PDF görüntüleyici | bekliyor | | |
| 21 · Kapanış | bekliyor | | |
| 22 · Tek örnek ve argüman iletimi | bekliyor | | |
| 23 · Başsız CLI çekirdeği | bekliyor | | |

## Sonraya

- Tasarımda olup Aşama 1'de gizlenecekler: YZ öğeleri, vurgu/not, kart/zaman/atıf grafiği görünümleri, tam metin arama, Zotero, "Yeni makale uyarısı", sistem entegrasyonu adımı (Aşama 6).
- Eksik tasarımlar: 4.1 karşılama ve yeni review formu, 4.6'nın tamamı, bileşen sayfası, daraltılmış kabuk, boş/yükleniyor/çevrimdışı durumları, İngilizce sürümler, koyu tema (yalnız matris var).
- Lisans kaydı: PyInstaller GPL + bootloader istisnası (dağıtıma engel değil) — ADR 0001'de yazıldı, Görev 21'deki lisans notlarına da eklenecek.
- (S1) Sidecar'ı Tauri eklentileri yüklenmeden, `run()` başında `std::process` ile başlatmak ~300 ms kazandırır (Görev 3/8).
- (S1) Açılışta "süreç → Rust main" ~600 ms; imzalı paketle yeniden ölçülmeli (Aşama 6, kod imzalama).
- (S1) Görev 20'de pdf.js belleği gerçek makalelerle tekrar ölçülmeli (spike: boşta 170 MB → 300 sayfa kaydırma sonrası ~410 MB private).
- (S1) Görev 23 belgeleri: PowerShell 5.1 boru hatlarında UTF-8 için `[Console]::OutputEncoding` notu.
- (2) Branch koruması (CI geçmeden `main`'e birleştirme yok): özel repoda GitHub Pro gerekiyor; repo açık olunca veya Pro ile açılmalı.
- (2) Windows'ta da CI (geliştirme Windows'ta; yol/satır sonu hatalarını yakalar). Paketleme işiyle birlikte (Aşama 6) veya daha önce.
- (2) Dependabot ile GitHub Actions ve kilit dosyası güncellemeleri.
- (2) pre-commit'in boşluk / büyük dosya / YAML kontrolleri CI'da da çalışsın (şimdilik yalnız yerelde).
- (1) Görev 9: Starlette `httpx` yerine `httpx2`'ye geçti; dış HTTP istemcisi seçimi yeniden değerlendirilmeli (ADR 0002).
- (1) TypeScript 7'ye geçiş: typescript-eslint desteği gelince.
- (1) Playwright (`pnpm e2e`) hangi görevde kurulacak belli değil; şimdilik yer tutucu.
- (S1) macOS/Linux'ta Job Object yerine stdin-EOF bekçisi + Linux'ta `PR_SET_PDEATHSIG` (Aşama 6).

## Açık sorular

Karar ilgili göreve gelindiğinde verilir.

1. **Review oluşturma ve ilk kurulum sihirbazı** (tasarım 4.1) hiçbir göreve atanmamış; Görev 13–14 bir review gerektiriyor. Yeni görev mi, Görev 14'ün parçası mı?
2. **Ayarlar ve keyring API'si** için arka uç görevi yok; Görev 8'deki Ayarlar ekranı API anahtarı kaydediyor.
3. **DBLP sağlayıcısı** Görev 11'de yok; varsayılan kararlarda öncelikli kaynak ve tasarımda çip olarak var.
4. ~~**Tauri iskeleti**~~ — Karar: Görev 1'de küçük iskelet (ADR 0002).
5. **6b kabulü** "ilerleme arayüzde görünür" UI'dan önce doğrulanamaz; Aşama 1'de API + SSE testiyle sınırlansın mı?
6. **`paper_fts`** Görev 6'da yok; Görev 19 kendi migration'ıyla ekleyecek (öneri).
7. **Görev 16 UI'ı** (sürükle-bırak) kütüphane listesinden (19) önce geliyor; UI kısmı 19'a kaysın mı?
8. **Görev 22** `tez <klasör>` içe aktarma önizlemesi ve `.bib` sihirbazı tanımsız; Aşama 1'de "öne getir + basit yanıt" ile sınırlı tutulsun mu?
9. ~~**`pnpm setup`**~~ — Karar: `pnpm bootstrap`; CLAUDE.md güncellendi (ADR 0002).
10. **Koyu tema tokenları** tek ekrandan türetilmiş taslak (`docs/design/tokens.json`); onay gerekiyor. Ayrıca açık temada YZ (`#7c3aed`) ve "tekrar bakılacak" (`#9333ea`) renkleri neredeyse aynı — ayırt edilmeli.
11. **Kısayol çakışması:** eleme ekranında J/K önceki/sonraki kayıt ve Space "Atla"; design prompt'ta "Atla" `→`. Görev 8'de kısayol haritası netleştirilmeli.
12. Plan "24 adım" diyor, liste 25 (S1 + 1–23 + 6b) — plan metninde düzeltilecek.
