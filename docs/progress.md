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
| 10 · Ortak kayıt şeması | bitti | `task/10-normalized-record` · #14 | `modules/search/schemas.py`: `NormalizedRecord` + `RecordAuthor`. Bozuk isteğe bağlı alan (yıl 0, boş metin, web olmayan bağlantı, geçersiz ORCID) `None` olur, başlıksız kayıt reddedilir; tanımlayıcılar kaynağın gönderdiği gibi kalır (normalleştirme Görev 12) |
| 11 · Sağlayıcılar | bitti | `task/11-*` · #15, #16, #17, #18 | OpenAlex, Semantic Scholar, arXiv, Crossref; kaydedilmiş gerçek yanıtlarla test edildi, ağsız çalışır. Sorgu her kaynağın diline çevrilir. Kaynak hatası istisna değil sonuçtur (`ok`/`partial`/`error`). DBLP bot kontrolü yüzünden sonraya kaldı. Ayrıntı: ADR 0008 |
| 12 · Tekilleştirme | bitti | `task/12-dedup` · #19 | `shared/identifiers.py` (DOI, arXiv, ISBN normalleştirme), `modules/search/dedup.py` (`PaperIndex`): önce tanımlayıcı, sonra bulanık başlık + yıl ±1 + ilk yazar. Ön baskı ve yayın ayrı kalır, `version_of` ile bağlanır. Yanlış birleştirme kaçan tekrardan kötü sayıldı. Zor vakalar tablosu `test_dedup.py`'de |
| 13 · Federe arama servisi | bitti | `task/13-federated-search` · #20 | `modules/search/service.py`: kaynaklar paralel, her cevap geldiği anda kendi işleminde yazılır. Çöken kaynak hata kaydıyla `search_run` olur, diğerleri gelir. Ham yanıt `snapshots/*.json.gz`. API: `POST /searches`, `GET /searches/{id}`, `/results`, `/events` (SSE). Migration 0003: `search_run.search_id`. Ayrıntı: ADR 0009 |
| 14 · Arama arayüzü | bitti | `task/14-search-ui` · #21 | Sorgu formu, kaynak çipleri (bekliyor, aranıyor, hız sınırı geri sayımı, sonuç, kısmi, hata), özet şeridi, sanallaştırılmış liste, denetçide birleştirme ayrıntısı, review'a/kütüphaneye ekleme, geçmiş. Küçük review formu ve üst çubukta seçici. Migration 0004: `paper.library_added_at`. Üretim derlemesinde 1.368 satırda kaydırma adımı p95 3,8 ms (tekerlek), 10,6 ms (hızlı). Gerçek dört kaynakla denendi: 1.662 kayıt, 294 tekrar, 1.368 benzersiz |
| 15 · BibTeX/RIS içe aktarma | bitti | `task/15-bib-ris-import` · #23 | `modules/importers`: bibtexparser v2 + rispy, LaTeX → Türkçe harf, bozuk girdi (satır + anahtar + kod) rapora düşer, içe aktarma durmaz. Önizleme hiçbir şey yazmaz; içe aktarma tek işlemde, tekilleştirmeden geçer, `search_run` olarak loglanır (dosya snapshot'ta). Migration 0005: `search_run.file_name`. Arayüz: arama ekranında "Dosyadan içe aktar" diyaloğu. Ayrıntı: ADR 0010 |
| 16 · PDF ekleme | bitti | `task/16-pdf-add` · #24 | API PDF'i açmaz: başlık kontrolü, sha256, `files/<2 hex>/<sha>.pdf` (atomik), `attachment` + `pdf.inspect` işi. İşçi pypdfium2 ile sayfa sayısı ve metin katmanı (ok / needs_ocr / failed + neden). Son denemede önceden `pdf.crashed` işaretlenir, işçi çökse de dosya atlanır. Aynı içerik `duplicate`. Yeni makale "Gelen kutusu" sistem koleksiyonuna. Pencereye bırakma + köşe bildirimleri; `POST /pdfs/from-paths` (Görev 22 için). Migration 0006. Ayrıntı: ADR 0011 |
| 17 · Açık erişim PDF | bitti | `task/17-open-access-pdf` · #25 | Makale başına `pdf.fetch_open_access` işi (işçide): sıra arXiv → Unpaywall (Ayarlar'daki e-posta) → kaynağın OA bağlantısı; PDF olmayan cevap (giriş sayfası) atlanır. İndirme akışlı, ilerleme iş kuyruğundan durum çubuğuna ve İşler ekranına. `JobFailed` ile işler kendi kodlarıyla biter: `pdf.no_open_access` yeniden denenmez, ağ hataları denenir. Arama sonuçlarında "PDF'leri bul". Ayrıntı: ADR 0012 |
| 18 · Koleksiyon ve etiketler | bekliyor | | |
| 19 · Kütüphane listesi | bekliyor | | |
| 20 · PDF görüntüleyici | bekliyor | | |
| 21 · Kapanış | bekliyor | | |
| 22 · Tek örnek ve argüman iletimi | bekliyor | | |
| 23 · Başsız CLI çekirdeği | bekliyor | | |

## Sonraya

- (17) Unpaywall'ın gerçek bir yanıtı kaydedilmedi (gerçek e-posta gerekir); ilk gerçek kullanımda şema doğrulanmalı, kaset eklenmeli.
- (17) JavaScript/çerez arkasındaki yayıncı sayfaları takip edilmiyor; bu makaleler `pdf.no_open_access` ile biter.
- (17) Kütüphane listesinden (Görev 19) de "PDF'leri bul" eylemi.
- (16) PDF'ten DOI okuma ve meta veri getirme (tasarım 4.6 "DOI bulundu, meta veri getiriliyor"); şimdilik başlık dosya adından.
- (16) Bırakılan tek PDF'i okuyucuda açma (tasarım 4.6) Görev 20 ile.
- (16) Çöp kutusunu boşaltırken `files/` içindeki dosyalar da silinmeli (bkz. (6) notu).
- (15) İçe aktarma hedefi olarak koleksiyon (tasarım 4.6 adım 4) Görev 18 ile.
- (15) BibTeX atıf anahtarları saklanmıyor; `citekey` üretimiyle birlikte (Görev 19 veya dışa aktarma) karar verilmeli.
- (15) `.bib`/`.ris` dosyasını pencereye veya uygulama simgesine bırakma (tasarım 4.6) Görev 22 ile; şimdilik diyaloğun bırakma alanı.
- (15) Önizleme yalnızca ilk 5 kaydı gösteriyor; tüm uyarılı kayıtları listeleme gerekirse eklenir.
- (14) Tauri'de dış bağlantılar (DOI, PDF): `target=_blank` webview'da açılmaz; `lib/platform` üzerinden opener eklentisi gerekir. Masaüstünde denenmedi.
- (14) Kaydırma, gizli tarayıcı panelinde ana iş parçacığı maliyetiyle ölçüldü; gerçek fps görünür pencerede (tercihen WebView2) doğrulanmalı.
- (14) Tasarım 4.2'den kalanlar: boolean sözdizimi renklendirmesi, kaynak başına sorguyu düzenleme, sorgu kaydetme ve uyarılar, terminal komutunu kopyalama (Görev 23), "PDF'leri bul" (Görev 17), yöntem bölümü dışa aktarımı, kenar çubuğunda kayıtlı sorgular, j/k kısayolları.
- (14) Geçmişten açılan arama sorgu formunu doldurmuyor; yeniden çalıştırmak için sorgu elle girilir.
- (14) Ücretsiz OpenAlex ve Semantic Scholar anahtarları gerçek kullanımda gerekli (ADR 0008); Ayarlar'dan eklenir.
- (14) Görev 19: kütüphane listesi `paper.library_added_at` üzerinden süzmeli; `list_papers` şu an tüm adayları döndürür.
- (13) Geçici bir PyInstaller derlemesiyle (migration klasörü `--add-data` ile eklenmeli) `serve --token-stdin` açıldı ve arXiv araması çalıştı. HTTP önbellek yolu (`hishel`/`anysqlite`) pakette henüz kullanılmadı; Görev 17'de doğrulanmalı.
- (13) Bir kaynağın yalnızca yeniden denenmesi (tasarım 4.2 "tekrar dene"): şimdilik tüm arama yeniden başlatılır.
- (11) DBLP sağlayıcısı: dblp API istemcilerine izin verirse veya koruma kalkarsa eklenir; o zamana dek çip gizli (ADR 0008).
- (11) OpenAlex'te anahtarla `cursor` sayfalaması henüz kaydedilmedi (anahtar yoktu); ilk gerçek kullanımda doğrulanmalı, sonra kaset eklenmeli.
- (11) Sağlayıcı ayarları (hız, kota) yapılandırılabilir olmalı (plan, riskler); şimdilik kodda.
- Tasarımda olup Aşama 1'de gizlenecekler: YZ öğeleri, vurgu/not, kart/zaman/atıf grafiği görünümleri, tam metin arama, Zotero, "Yeni makale uyarısı", sistem entegrasyonu adımı (Aşama 6).
- Eksik tasarımlar: 4.1 karşılama ve yeni review formu, 4.6'nın tamamı, bileşen sayfası, daraltılmış kabuk, boş/yükleniyor/çevrimdışı durumları, İngilizce sürümler, koyu tema (yalnız matris var).
- Lisans kaydı: PyInstaller GPL + bootloader istisnası (dağıtıma engel değil) — ADR 0001'de yazıldı, Görev 21'deki lisans notlarına da eklenecek.
- (S1) Sidecar'ı Tauri eklentileri yüklenmeden, `run()` başında `std::process` ile başlatmak ~300 ms kazandırır (Görev 3/8).
- (S1) Açılışta "süreç → Rust main" ~600 ms; imzalı paketle yeniden ölçülmeli (Aşama 6, kod imzalama).
- (S1) Görev 20'de pdf.js belleği gerçek makalelerle tekrar ölçülmeli (spike: boşta 170 MB → 300 sayfa kaydırma sonrası ~410 MB private).
- (S1) Görev 23 belgeleri: PowerShell 5.1 boru hatlarında UTF-8 için `[Console]::OutputEncoding` notu.
- (3) Her istek INFO düzeyinde loglanıyor; PDF Range ve SSE gelince gürültü olursa bu uçlar DEBUG'a indirilmeli.
- (4) Görev 5: kütüphane açılışında `migrate(db)` çağrılmalı; migration öncesi `backups/`'a kopya alınması değerlendirilmeli.
- (5) Arayüzden kütüphane oluştur/aç uçları ve karşılama ekranı (tasarım 4.1) — açık soru 1 ile birlikte karara bağlanmalı.
- (5) Kütüphane OneDrive/Dropbox/ağ sürücüsündeyse uyarı (SQLite WAL ve dosya kilidi bu klasörlerde güvenilmez).
- (5) Arka uç testleri ~35 sn (gerçek süreç başlatan entegrasyon testleri, her biri ~3 sn); uzarsa `pytest-xdist` ile paralel çalıştırma.
- (6) `citekey` üretimi (içe aktarma / Görev 15 veya 19) ve "Gelen kutusu" sistem koleksiyonunun oluşturulması (Görev 16).
- (6) Çöp kutusunu boşaltma: ek dosyalar (diskteki PDF'lerle) makaleden önce açıkça silinmeli (`attachment` RESTRICT).
- (6) Alembic otomatik üretimi tetikleyicileri ve kısmi indeks koşullarını görmez; bunlara dokunan migration'lar elle yazılmalı (ADR 0004).
- (6b) Arka uç testleri ~80 sn'ye çıktı (gerçek süreçli kuyruk testleri); `pytest-xdist` ile paralel çalıştırma artık değerlendirilmeli.
- (6b) İş ilerlemesi veritabanı yoklamasıyla (0,25 sn); gerekirse işçiden API'ye bildirim kanalı (API değişmeden).
- (8) Kod bölme: üretim paketi ~500 kB (Vite uyarısı); okuyucu (pdf.js, Görev 20) gelince rota bazlı `import()`.
- (8) Sürüm modu kütüphanesi şimdilik `Belgeler/TEz Library`; karşılama ekranı (açık soru 1) gelince kullanıcı seçecek, son açılan kütüphane hatırlanacak.
- (8) Ayarlar 5.11'in kalan kategorileri (yoğunluk, yedekleme, YZ, PDF/GROBID, kısayollar, sistem entegrasyonu) ilgili görevlerle.
- (8) Komut paleti (Ctrl+K), özel pencere başlığı ve panel genişliği ayarlama henüz yok.
- (8) Playwright E2E (`pnpm e2e`) hâlâ yer tutucu; ilk akış (ayarlar kalıcılığı) bununla da yazılabilir.
- (S1/8) Sidecar'ı `setup()` yerine `run()` başında başlatmak ~300 ms kazandırabilir (ölçülmedi).
- (2) Branch koruması (CI geçmeden `main`'e birleştirme yok): özel repoda GitHub Pro gerekiyor; repo açık olunca veya Pro ile açılmalı.
- (2) Windows'ta da CI (geliştirme Windows'ta; yol/satır sonu hatalarını yakalar). Paketleme işiyle birlikte (Aşama 6) veya daha önce.
- (2) Dependabot ile GitHub Actions ve kilit dosyası güncellemeleri.
- (2) pre-commit'in boşluk / büyük dosya / YAML kontrolleri CI'da da çalışsın (şimdilik yalnız yerelde).
- (1) TypeScript 7'ye geçiş: typescript-eslint desteği gelince.
- (1) Playwright (`pnpm e2e`) hangi görevde kurulacak belli değil; şimdilik yer tutucu.
- (S1) macOS/Linux'ta Job Object yerine stdin-EOF bekçisi + Linux'ta `PR_SET_PDEATHSIG` (Aşama 6).

## Açık sorular

Karar ilgili göreve gelindiğinde verilir.

1. ~~**Review oluşturma**~~ — Karar: Görev 14'te küçük form (başlık + yöntem); araştırma soruları, kriterler ve sihirbaz (tasarım 4.1) sonraya.
2. ~~**Ayarlar ve keyring API'si**~~ — Karar: Görev 8'de `/settings` ve `/secrets` (keyring) eklendi (ADR 0006).
3. ~~**DBLP sağlayıcısı**~~ — Karar: sonraya. `dblp.org` API isteklerine Anubis bot kontrolü döndürüyor (ADR 0008).
4. ~~**Tauri iskeleti**~~ — Karar: Görev 1'de küçük iskelet (ADR 0002).
5. ~~**6b kabulü**~~ — Karar: Aşama 1'de API + SSE testiyle; arayüz kısmı Görev 8'deki durum çubuğunda (ADR 0005).
6. **`paper_fts`** Görev 6'da yok; Görev 19 kendi migration'ıyla ekleyecek (öneri).
7. ~~**Görev 16 UI'ı**~~ — Karar: Görev 16'da pencereye bırakma + köşe bildirimleri geldi; eklenen PDF'lerin listede görünmesi Görev 19'da.
8. **Görev 22** `tez <klasör>` içe aktarma önizlemesi ve `.bib` sihirbazı tanımsız; Aşama 1'de "öne getir + basit yanıt" ile sınırlı tutulsun mu?
9. ~~**`pnpm setup`**~~ — Karar: `pnpm bootstrap`; CLAUDE.md güncellendi (ADR 0002).
10. **Koyu tema tokenları** tek ekrandan türetilmiş taslak (`docs/design/tokens.json`); onay gerekiyor. Ayrıca açık temada YZ (`#7c3aed`) ve "tekrar bakılacak" (`#9333ea`) renkleri neredeyse aynı — ayırt edilmeli.
11. **Kısayol çakışması:** eleme ekranında J/K önceki/sonraki kayıt ve Space "Atla"; design prompt'ta "Atla" `→`. Görev 8'de kısayol haritası netleştirilmeli.
12. Plan "24 adım" diyor, liste 25 (S1 + 1–23 + 6b) — plan metninde düzeltilecek.
