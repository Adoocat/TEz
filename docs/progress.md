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
| 16 · PDF ekleme | bitti | `task/16-pdf-add` · #25 | API PDF'i açmaz: başlık kontrolü, sha256, `files/<2 hex>/<sha>.pdf` (atomik), `attachment` + `pdf.inspect` işi. İşçi pypdfium2 ile sayfa sayısı ve metin katmanı (ok / needs_ocr / failed + neden). Son denemede önceden `pdf.crashed` işaretlenir, işçi çökse de dosya atlanır. Aynı içerik `duplicate`. Yeni makale "Gelen kutusu" sistem koleksiyonuna. Pencereye bırakma + köşe bildirimleri; `POST /pdfs/from-paths` (Görev 22 için). Migration 0006. Ayrıntı: ADR 0011 |
| 17 · Açık erişim PDF | bitti | `task/17-open-access-pdf` · #26 | Makale başına `pdf.fetch_open_access` işi (işçide): sıra arXiv → Unpaywall (Ayarlar'daki e-posta) → kaynağın OA bağlantısı; PDF olmayan cevap (giriş sayfası) atlanır. İndirme akışlı, ilerleme iş kuyruğundan durum çubuğuna ve İşler ekranına. `JobFailed` ile işler kendi kodlarıyla biter: `pdf.no_open_access` yeniden denenmez, ağ hataları denenir. Arama sonuçlarında "PDF'leri bul". Ayrıntı: ADR 0012 |
| 18 · Koleksiyon ve etiketler | bitti | `task/18-collections-tags` · #27 | Koleksiyon ağacı (oluştur, yeniden adlandır, taşı, sil; döngü ve kardeş ad kontrolü, Türkçe katlama), çoklu koleksiyon, etiketler (renkler token adı), toplu okuma durumu; sayılar türetilir. Kenar çubuğu: Gelen kutusu, Tüm makaleler, ağaç, etiketler; satırlar koleksiyona/etikete, koleksiyonlar birbirine sürüklenir. Playwright kuruldu: `pnpm e2e` gerçek arka uç + geçici kütüphaneyle; CI'da `e2e` işi. Ayrıntı: ADR 0013 |
| 19 · Kütüphane listesi | bitti | `task/19-library-list` · #28 | `paper_fts` (migration 0007) Türkçe katlanmış metinle; ORM `after_flush` ile aynı işlemde güncellenir, kütüphane açılışında eksikse yeniden kurulur. `GET /papers/search` (her kelime, önek), detay ve atıf anahtarı (`yilmaz2024automated`, düzenlenebilir). TanStack Table v8 + Virtual tablo: sıralama, yıl/okuma/etiket/PDF filtreleri, denetçi. Demo kütüphane: `python -m tez.devtools.demo`. Kabul: 2000 makalede sunucu ~1–2 ms, tarayıcı gidiş-dönüş medyan ~5 ms. Ayrıntı: ADR 0014 |
| 20 · PDF görüntüleyici | bitti | `task/20-pdf-viewer` · #29 | `GET /attachments/{id}/file` (Range → 206, başarılı aralık istekleri DEBUG). pdf.js ilk kullanımda yüklenir, yalnız aralıklar (autoFetch kapalı), sanallaştırılmış sayfalar (görünen ±2), metin katmanı, yakınlaştırma, `#/reader/<id>?page=N`. Kabul (300 sayfa, 6,1 MB, headless Chromium): 150. sayfada açılış 1,7 MB, DOM'da en çok 3 tuval, JS yığını 35 MB sabit, kaydırma adımı p95 34 ms. Ayrıntı: ADR 0015 |
| 21 · Kapanış | bitti | `task/21-closing` · #30 | Yedek: SQLite backup API ile tutarlı veritabanı kopyası + `files/` + `snapshots/` + SHA-256'lı manifest, tek zip; işçide iş, Ayarlar › Yedekleme. `tez-backend restore <zip> <klasör>`: yalnızca boş klasöre, her girdi doğrulanır, `..` reddedilir, bozuksa yarım klasör silinir. Kabul testi: geri yüklenen kütüphanede makaleler, atıf anahtarları, koleksiyonlar, arama, arama geçmişi ve PDF baytları aynı. README, `docs/architecture.md`, `docs/licenses.md`; Playwright duman testi (ekranlar, dil kalıcılığı, gerçek işçiyle yedek). Ayrıntı: ADR 0016 |
| 22 · Tek örnek ve argüman iletimi | bitti | `task/22-single-instance` · #31 | `single-instance` + `deep-link` eklentileri. Argümanlar Rust'ta sınıflandırılır (PDF, .bib/.ris, klasör, `tez://`, yok/desteklenmeyen) ve bir kuyruğa yazılır; pencere yalnızca dürtülür ve kuyruğu kendisi alır, böylece açık ve kapalı uygulamada aynı yol. PDF Gelen kutusuna + okuyucuda açılır; klasördeki PDF'ler tek özet bildirimle; .bib/.ris içe aktarma diyaloğunda (arka uç yoldan okur); kütüphane klasörü yalnız bildirim; `tez://` yalnız gezinir. Windows hata ayıklama derlemesiyle denendi: açıkken ikinci çağrı 150 ms'de çıktı, tek süreç kaldı, PDF eklendi; kapalıyken aynı komut aynı sonucu verdi. Ayrıntı: ADR 0017 |
| 23 · Başsız CLI çekirdeği | bitti | `task/23-headless-cli` · #32 | `tez search / import / add / export` (Typer). Kütüphane açık bir pencerede kullanılıyorsa onun API'si (`.tez/instance.json`), değilse kilit alınıp doğrudan servisler; iki yol aynı yanıt modellerini döndürür. Çıkış kodları 0/1/2, `--json` (İngilizce alanlar), çıktı hep UTF-8. `--help` ve mesajlar Türkçe/İngilizce (`--lang`, `TEZ_LANG`, sistem dili). Yeni: `modules/export` (BibTeX/RIS, içe aktarıcıyla gidiş-dönüş testi), `GET /export`. Kabul: 16 uçtan uca test iki modda da (gerçek uvicorn sunucusu ve doğrudan) geçiyor. Ayrıntı: ADR 0018 |

**Aşama 2:** görevler 24–42 `docs/plan.md` → "Aşama 2 görevleri (taslak)" bölümünde; onaylanınca bu tabloya eklenecek.

## Sonraya

- (ADR 0019) Kapsam her daldan araştırma ve tez olarak netleşti; Aşama 2+ işlerinin aşamalara dağılımı `docs/plan.md` → "Aşama 1 sonrası kararlar" bölümünde.
- (ADR 0019) Review formunda varsayılan yöntem hâlâ `kitchenham_slr` (`ReviewForm.tsx`); Görev 24'te PRISMA 2020 olacak.
- (ADR 0019) TR Dizin arayüzünden alınan BibTeX dışa aktarımıyla içe aktarma denemesi (Türkçe karakterler, alan adları); küçük bir örnek dosya test verisine eklenmeli.
- (ADR 0019) YÖK Tez'in arama sonuçlarını dosyaya (RIS/BibTeX/CSV) aktarıp aktarmadığı kontrol edilmeli; aktarıyorsa ön ayarlı içe aktarmaya eklenir.
- (ADR 0019) Zotero Connector'ın YÖK Tez sayfalarını tanıyıp tanımadığı bir kez denenmeli; tanıyorsa Zotero → RIS → TEz yolu bugün kullanılabilir ve dışa aktarma rehberine yazılır.
- (ADR 0019) Tarayıcı bağlayıcısı (Zotero Connector benzeri): kullanıcı açtığı sonuç sayfasını tek tıkla TEz'e gönderir; YÖK Tez, Google Scholar, JSTOR. Yeni mimari bileşen; Aşama 6 sonrası, onay + ADR ile.
- (23) BibTeX yazıcısı her tezi `@phdthesis` yazıyor (`writers.py`); yüksek lisans tezi `@mastersthesis` olmalı (RIS'te ikisi de `THES`). Tez türü (yüksek lisans/doktora) şimdilik saklanmıyor. → Görev 28.
- (23) Planın komut tablosundaki `tez list`, `tez jobs`, `tez backup`, `tez prisma` ve pencere komutları (`tez <dosya>` masaüstünü başlatır) Aşama 6'daki konsol kabuğuyla.
- (23) Typer'ın gömülü Click'inde "Usage:" ve "Try … for help." sabit yazılı; Türkçe yardımda İngilizce kalıyor.
- (23) Dışa aktarma ekranı (tasarım 5.10): kapsam seçimi, atıf anahtarı biçimi önizlemesi.
- (22) `tez://` şemasının işletim sistemine kaydı, PATH'teki `tez` komutu ve "Open with TEz" kurulum paketiyle (Aşama 6).
- (22) Klasör için içe aktarma önizleme diyaloğu (tasarım 4.6) ve kütüphane değiştirme (açık soru 1).
- (22) `lib/platform/tauri.ts` açma istekleri yolunun otomatik testi yok (Tauri API taklidi gerekir); masaüstünde elle doğrulandı.
- (21) Otomatik/zamanlanmış yedek ve son *n* yedeği tutma; durum çubuğunda "son yedek" (tasarım).
- (21) Arayüzden geri yükleme: kütüphane seçici/karşılama ekranı (açık soru 1) ile birlikte.
- (20) Belge içi arama, vurgular, ana hat/küçük resim kenar çubuğu, döndürme; farklı boyutlu sayfalar (şimdi hepsi 1. sayfa boyutunda).
- (20) pdf.js `standardFontDataUrl` ve `wasmUrl` (JPEG 2000 vb.) ayarlanmadı; gömülmemiş standart yazı tipli PDF'ler yedek yazı tipiyle çizilir.
- (20) Ana paket ~760 kB (pdf.js ayrı parçada); rota bazlı kod bölme hâlâ yapılabilir (bkz. (8)).
- (19) Sütun gizleme/yeniden sıralama, kart/zaman çizelgesi/atıf grafiği görünümleri (tasarım 4.3).
- (19) Toplu SQL ile makale silme `paper_fts`'i atlar; çöp kutusunu boşaltma ORM ile yapılmalı veya ardından yeniden indekslemeli.
- (19) Web modunda token'lı bağlantı aynı sekmede yalnızca hash değişirse alınmıyor (sayfa yeniden yüklenmeli); `tez serve` bağlantısı yeni sekmede açıldığı için sorun değil, istenirse `hashchange` dinlenebilir.
- (18) Koleksiyonları elle sıralama (`sort_order` var, arayüz yok); akıllı koleksiyonlar (tasarım 4.3).
- (18) Kenar çubuğu klavyeyle ağaç gezintisi (ok tuşları, `role="tree"`).
- (CI) 2026-11-11'de GitHub runner'larında `azure.archive.ubuntu.com` DNS'te çözülemedi; Rust işi `apt-get`'te takıldı. Tekrarlarsa apt adımına zaman aşımı/ayna değişikliği eklenmeli.
- (17) Unpaywall'ın gerçek bir yanıtı kaydedilmedi (gerçek e-posta gerekir); ilk gerçek kullanımda şema doğrulanmalı, kaset eklenmeli.
- (17) JavaScript/çerez arkasındaki yayıncı sayfaları takip edilmiyor; bu makaleler `pdf.no_open_access` ile biter.
- (17) Kütüphane listesinden (Görev 19) de "PDF'leri bul" eylemi.
- (16) PDF'ten DOI okuma ve meta veri getirme (tasarım 4.6 "DOI bulundu, meta veri getiriliyor"); şimdilik başlık dosya adından.
- (16) Çöp kutusunu boşaltırken `files/` içindeki dosyalar da silinmeli (bkz. (6) notu).
- (15) İçe aktarma hedefi olarak koleksiyon (tasarım 4.6 adım 4) Görev 18 ile.
- (15) İçe aktarılan BibTeX anahtarları kullanılmıyor; anahtarlar Görev 19'dan beri uygulamada üretiliyor (ADR 0014). İstenirse içe aktarmada dosyadaki anahtar korunabilir.
- (15) `.bib`/`.ris` dosyasını pencereye veya uygulama simgesine bırakma (tasarım 4.6) Görev 22 ile; şimdilik diyaloğun bırakma alanı.
- (15) Önizleme yalnızca ilk 5 kaydı gösteriyor; tüm uyarılı kayıtları listeleme gerekirse eklenir.
- ~~(14) Tauri'de dış bağlantılar (DOI, PDF)~~ — Düzeltildi (`task/fix-external-links`): `platform.openExternal`, masaüstünde `tauri-plugin-opener` (yalnız http/https). Yeni dış bağlantı eklenirse bu yoldan açılmalı.
- (14) Kaydırma, gizli tarayıcı panelinde ana iş parçacığı maliyetiyle ölçüldü; gerçek fps görünür pencerede (tercihen WebView2) doğrulanmalı.
- (14) Tasarım 4.2'den kalanlar: boolean sözdizimi renklendirmesi, kaynak başına sorguyu düzenleme, sorgu kaydetme ve uyarılar, terminal komutunu kopyalama (Görev 23), "PDF'leri bul" (Görev 17), yöntem bölümü dışa aktarımı, kenar çubuğunda kayıtlı sorgular, j/k kısayolları.
- (14) Geçmişten açılan arama sorgu formunu doldurmuyor; yeniden çalıştırmak için sorgu elle girilir.
- (14) Ücretsiz OpenAlex ve Semantic Scholar anahtarları gerçek kullanımda gerekli (ADR 0008); Ayarlar'dan eklenir.
- (13) Geçici bir PyInstaller derlemesiyle (migration klasörü `--add-data` ile eklenmeli) `serve --token-stdin` açıldı ve arXiv araması çalıştı. HTTP önbellek yolu (`hishel`/`anysqlite`) pakette henüz kullanılmadı; Görev 17'de doğrulanmalı.
- (13) Bir kaynağın yalnızca yeniden denenmesi (tasarım 4.2 "tekrar dene"): şimdilik tüm arama yeniden başlatılır.
- (11) DBLP sağlayıcısı: dblp API istemcilerine izin verirse veya koruma kalkarsa eklenir; o zamana dek çip gizli (ADR 0008).
- (11) OpenAlex'te anahtarla `cursor` sayfalaması henüz kaydedilmedi (anahtar yoktu); ilk gerçek kullanımda doğrulanmalı, sonra kaset eklenmeli.
- (11) Sağlayıcı ayarları (hız, kota) yapılandırılabilir olmalı (plan, riskler); şimdilik kodda.
- Tasarımda olup Aşama 1'de gizlenecekler: YZ öğeleri, vurgu/not, kart/zaman/atıf grafiği görünümleri, tam metin arama, Zotero, "Yeni makale uyarısı", sistem entegrasyonu adımı (Aşama 6).
- Eksik tasarımlar: 4.1 karşılama ve yeni review formu, 4.6'nın tamamı, bileşen sayfası, daraltılmış kabuk, boş/yükleniyor/çevrimdışı durumları, İngilizce sürümler, koyu tema (yalnız matris var).
- (S1) Sidecar'ı Tauri eklentileri yüklenmeden, `run()` başında `std::process` ile başlatmak ~300 ms kazandırır (Görev 3/8).
- (S1) Açılışta "süreç → Rust main" ~600 ms; imzalı paketle yeniden ölçülmeli (Aşama 6, kod imzalama).
- (S1/20) pdf.js belleği WebView2'de gerçek makalelerle ölçülmeli (spike: 170 → ~410 MB; Görev 20 headless Chromium'da JS yığını 35 MB sabit, tuval en çok 3).
- (3) SSE uçları uzun yaşadığı için tek satır log; PDF aralık istekleri Görev 20'de DEBUG'a indirildi.
- (4) Görev 5: kütüphane açılışında `migrate(db)` çağrılmalı; migration öncesi `backups/`'a kopya alınması değerlendirilmeli.
- (5) Arayüzden kütüphane oluştur/aç uçları ve karşılama ekranı (tasarım 4.1) — açık soru 1 ile birlikte karara bağlanmalı.
- (5) Kütüphane OneDrive/Dropbox/ağ sürücüsündeyse uyarı (SQLite WAL ve dosya kilidi bu klasörlerde güvenilmez).
- (5) Arka uç testleri ~35 sn (gerçek süreç başlatan entegrasyon testleri, her biri ~3 sn); uzarsa `pytest-xdist` ile paralel çalıştırma.
- (6) Çöp kutusunu boşaltma: ek dosyalar (diskteki PDF'lerle) makaleden önce açıkça silinmeli (`attachment` RESTRICT).
- (6) Alembic otomatik üretimi tetikleyicileri ve kısmi indeks koşullarını görmez; bunlara dokunan migration'lar elle yazılmalı (ADR 0004).
- (6b) Arka uç testleri ~80 sn'ye çıktı (gerçek süreçli kuyruk testleri); `pytest-xdist` ile paralel çalıştırma artık değerlendirilmeli.
- (6b) İş ilerlemesi veritabanı yoklamasıyla (0,25 sn); gerekirse işçiden API'ye bildirim kanalı (API değişmeden).
- (8) Kod bölme: üretim paketi ~500 kB (Vite uyarısı); okuyucu (pdf.js, Görev 20) gelince rota bazlı `import()`.
- (8) Sürüm modu kütüphanesi şimdilik `Belgeler/TEz Library`; karşılama ekranı (açık soru 1) gelince kullanıcı seçecek, son açılan kütüphane hatırlanacak.
- (8) Ayarlar 5.11'in kalan kategorileri (yoğunluk, yedekleme, YZ, PDF/GROBID, kısayollar, sistem entegrasyonu) ilgili görevlerle.
- (8) Komut paleti (Ctrl+K), özel pencere başlığı ve panel genişliği ayarlama henüz yok.
- (S1/8) Sidecar'ı `setup()` yerine `run()` başında başlatmak ~300 ms kazandırabilir (ölçülmedi).
- (2) Branch koruması (CI geçmeden `main`'e birleştirme yok): özel repoda GitHub Pro gerekiyor; repo açık olunca veya Pro ile açılmalı.
- (2) Windows'ta da CI (geliştirme Windows'ta; yol/satır sonu hatalarını yakalar). Paketleme işiyle birlikte (Aşama 6) veya daha önce.
- (2) Dependabot ile GitHub Actions ve kilit dosyası güncellemeleri.
- (2) pre-commit'in boşluk / büyük dosya / YAML kontrolleri CI'da da çalışsın (şimdilik yalnız yerelde).
- (1) TypeScript 7'ye geçiş: typescript-eslint desteği gelince.
- (S1) macOS/Linux'ta Job Object yerine stdin-EOF bekçisi + Linux'ta `PR_SET_PDEATHSIG` (Aşama 6).

## Açık sorular

Karar ilgili göreve gelindiğinde verilir.

1. ~~**Review oluşturma**~~ — Karar: Görev 14'te küçük form (başlık + yöntem); araştırma soruları, kriterler ve sihirbaz (tasarım 4.1) sonraya.
2. ~~**Ayarlar ve keyring API'si**~~ — Karar: Görev 8'de `/settings` ve `/secrets` (keyring) eklendi (ADR 0006).
3. ~~**DBLP sağlayıcısı**~~ — Karar: sonraya. `dblp.org` API isteklerine Anubis bot kontrolü döndürüyor (ADR 0008).
4. ~~**Tauri iskeleti**~~ — Karar: Görev 1'de küçük iskelet (ADR 0002).
5. ~~**6b kabulü**~~ — Karar: Aşama 1'de API + SSE testiyle; arayüz kısmı Görev 8'deki durum çubuğunda (ADR 0005).
6. ~~**`paper_fts`**~~ — Karar: Görev 19'da migration 0007 ile (ADR 0014).
7. ~~**Görev 16 UI'ı**~~ — Karar: Görev 16'da pencereye bırakma + köşe bildirimleri geldi; eklenen PDF'lerin listede görünmesi Görev 19'da.
8. ~~**Görev 22 klasör ve .bib**~~ — Karar: Aşama 1'de basit yanıt; klasördeki PDF'ler doğrudan Gelen kutusuna (tek özet bildirim), .bib/.ris içe aktarma diyaloğunda, kütüphane klasörü için yalnız bildirim (ADR 0017).
9. ~~**`pnpm setup`**~~ — Karar: `pnpm bootstrap`; CLAUDE.md güncellendi (ADR 0002).
10. ~~**Koyu tema tokenları**~~ — Karar (2026-11-14): bugünkü koyu tema tokenları olduğu gibi onaylandı. Açık temadaki mor çakışması 18. soruya ayrıldı.
11. ~~**Kısayol çakışması**~~ — Karar (2026-11-14): "Atla" `→` tuşu ve karar çubuğunda tıklanabilir "Atla" düğmesi. Space elemede kullanılmaz; `J`/`K` karar vermeden önceki/sonraki kayıt. Tasarım 5.2 taslağındaki `Space` etiketi eskidi.
12. Plan "24 adım" diyor, liste 25 (S1 + 1–23 + 6b) — plan metninde düzeltilecek.
13. ~~**İki değerlendiricili eleme ve Cohen kappa**~~ — Karar: Aşama 2 sonunda. Önce tek kişilik eleme biter; sonra kararlar kütüphaneler arasında aktarılarak iki hakem, "Çakışmalar" sekmesi ve kappa (ADR 0019).
14. ~~**Yeni API sağlayıcılarının sırası**~~ — Karar: (1) PubMed + Europe PMC, (2) DOAJ + ERIC + CORE, (3) DergiPark (öne alınabilir). Her biri ayrı onay + ADR; CLAUDE.md 1. kuraldaki liste ancak kaynak eklendiğinde güncellenir (ADR 0019).
15. ~~**TR Dizin ve YÖK Tez kullanım koşulları**~~ — Karar: kurumlara sorulmayacak; ikisi de yalnız dosya yolundan. TR Dizin BibTeX ile; YÖK Tez yalnız sitesi dışa aktarım sunuyorsa (ADR 0019).
16. ~~**`citeproc-py` lisansı**~~ — Karar: BSD-2-Clause-Views (izin verici, MIT ile uyumlu); CSL kaynakçası arka uçta bununla. `citeproc-js` (AGPL/CPAL) kullanılmaz.
17. ~~**Varsayılan review yöntemi**~~ — Karar: PRISMA 2020; Kitchenham SLR seçenek (ADR 0019).
18. ~~**Açık temada iki mor**~~ — Karar (2026-11-14): açık temada "tekrar bakılacak" fuşya `#c026d3` (eskisi `#9333ea`, YZ moru `#7c3aed` ile karışıyordu); koyu temadaki mor/fuşya ayrımıyla aynı. Tasarım taslakları eski rengi gösteriyor; `tokens.json` geçerli.
19. **Ön ayar örnek dosyaları (Görev 26):** her veritabanı için gerçek, küçük bir dışa aktarım dosyası gerekiyor (Web of Science, Scopus, JSTOR, EBSCO, ProQuest, PsycINFO, IEEE Xplore, ACM DL, Google Scholar, TR Dizin). Hangilerine kurum erişimi var? Varsayılan: erişilenlerle başla; dosyası olmayanın ön ayarı gizli kalır.
20. **Kalite değerlendirmesinin aşaması:** taslakta Aşama 2'de (Görev 38), tam metin elemesinden sonra. Varsayılan: Aşama 2.
