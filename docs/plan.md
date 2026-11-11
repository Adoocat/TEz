# TEz — Mimari ve Aşama 1 Planı

Nov 2, 2026 · @Demirkan

## Özet

Yığının özü (FastAPI + React/TS + Tauri + SQLite/FTS5 + pdf.js) doğru; aşağıdaki yedi noktada değişiklik öneriyorum. Aşama 1'in gerçekçi süresi tek kişiyle 3–4 hafta.

| Konu | Planda | Önerim | Neden |
| --- | --- | --- | --- |
| Arka uç yapısı | Belirtilmemiş | Modüler monolit: bir API süreci + ayrı işçi (worker) süreci | Bozuk PDF bir C kütüphanesini çökertirse yalnızca işçi düşer, arayüz ayakta kalır |
| ORM ve migration | Migration sistemi | SQLAlchemy 2 + Alembic (`batch` modu) | SQLite'ın `ALTER TABLE` sınırlarını Alembic batch modu çözer |
| Vektör indeksi | sqlite-vec veya FAISS | sqlite-vec | Tek veritabanı dosyası: yedekleme ve tutarlılık kolay; 2000 makale ölçeğinde yeterli |
| Düzen/tablo çıkarma | Docling veya Marker | Docling | Marker GPL-3.0 ve modelleri kısıtlı lisanslı; Docling MIT |
| PDF metin/görsel | PyMuPDF | pypdfium2 (karar); PyMuPDF kullanılmaz | PyMuPDF AGPL-3.0; pypdfium2 Apache/BSD — proje MIT lisanslı kalabilir |
| GROBID | Gömülü bileşen | İsteğe bağlı harici servis (yerel Docker veya lab sunucusu) | Java + birkaç GB bellek; masaüstü paketini ağırlaştırır |
| API sözleşmesi | — | FastAPI OpenAPI şemasından üretilen TS istemcisi | Arka uç ile ön yüz arasında derleme zamanında tip güvenliği |

Veri modeline iki taşıyıcı kavram ekliyorum: **Review** (bir sistematik tarama projesi; arama, kriter, eleme ve PRISMA bunun altında) ve **Anchor** (PDF'te bir konum; vurgulama, matris kanıtı, çıkarılan öğe ve yapay zekâ alıntısı hepsi bunu kullanır). "Doğrulanabilir yapay zekâ" ilkesini teknik olarak garanti eden şey Anchor.

**Ek gereksinim:** Kurulumdan sonra TEz terminalden (`tez` komutu) ve dosya yöneticisinin "Open with TEz" menüsünden de kullanılır. Terminal ayrı bir ürün değil, aynı servis katmanına açılan ikinci bir kapıdır; ayrıntısı "Terminal ve sistem entegrasyonu" bölümünde.

## Mimari

Uygulama üç yerel katmandan oluşur: Tauri kabuğu, React ön yüz ve iki süreçli Python sidecar. İnternete yalnızca sidecar çıkar; tüm veri kullanıcının kütüphane klasöründe kalır.

&#91;embedded content: bileşenler ve iletişim · 3 yerel katman, 3 dış servis\]

- **Başlatma:** Tauri boş bir port seçer, rastgele bir token üretir, sidecar'ı bu bilgilerle başlatır ve ön yüze iletir. Sidecar yalnızca 127.0.0.1'i dinler; tokensız istek reddedilir.
- **Ön yüz ↔ API:** REST (JSON) + uzun işlerin ilerlemesi için Server-Sent Events. İstemci ve tipler OpenAPI şemasından üretilir.
- **API ↔ işçi:** Doğrudan çağrı yok. API `processing_job` tablosuna iş yazar, işçi kiralama (lease) ile alır ve sonucu veritabanına yazar. İşçi çökerse kira dolar, iş yeniden denenir; üç başarısızlıkta dosya "hatalı" işaretlenip atlanır.
- **Web modu:** Aynı API `tez serve` ile Tauri olmadan başlar, ön yüz tarayıcıda açılır. Platforma özgü işler (dosya seçici, klasör açma) `lib/platform` adaptöründedir.
- **LLM ve GROBID:** İkisi de bir arayüz arkasında. Kapalıyken ilgili özellikler arayüzden gizlenir; uygulamanın geri kalanı etkilenmez.

**Süreç yönetimi:** Arka uç tek bir ikili (`tez-backend`) olarak paketlenir ve üç modda çalışır: `serve` (API), `worker` (işçi), `cli` (başsız komutlar). API, işçiyi alt süreç olarak başlatır, izler ve çökerse yeniden başlatır. Web modunda `tez serve`, Jupyter'deki gibi token içeren yerel bir adres yazdırır. PDF'ler ön yüze arka uçtan HTTP Range destekli bir uç noktayla akıtılır.

## Terminal ve sistem entegrasyonu

Kurulumdan sonra TEz üç kapıdan kullanılır: pencere, terminal (`tez` komutu; PowerShell, cmd, bash, zsh fark etmez) ve dosya yöneticisinin "Open with TEz" menüsü — VS Code'daki `code .` ve "Open with Code" gibi. Üçü de aynı servis katmanını kullanır; iş mantığı kopyalanmaz.

### Komut seti

| Komut | Ne yapar | Pencere |
| --- | --- | --- |
| `tez` | Uygulamayı açar veya öne getirir | açar |
| `tez .` · `tez <klasör>` | Klasör bir TEz kütüphanesiyse onu açar; değilse içindeki PDF'ler için içe aktarma önizlemesi gösterir | açar |
| `tez <dosya.pdf>` | PDF'i "Gelen kutusu"na ekler (sha256 ile tekrar kontrolü), okuyucuda açar | açar |
| `tez <dosya.bib>` · `tez <dosya.ris>` | İçe aktarma sihirbazını açar | açar |
| `tez open <atıf-anahtarı> --page 4` | Makaleyi okuyucuda o sayfada açar | açar |
| `tez search "<sorgu>" --sources openalex,s2 --review <ad>` | Federe arama yapar, arama kaydı oluşturur | gerekmez |
| `tez import <dosya> --source "IEEE Xplore" --searched-at 2026-11-01` | Dışa aktarılmış sonuçları arama kaydı olarak içe alır | gerekmez |
| `tez add <pdf…> --collection <ad>` | Toplu PDF ekler | gerekmez |
| `tez export --format bibtex --review <ad> -o refs.bib` | Kaynakçayı dışa aktarır | gerekmez |
| `tez list` · `tez jobs` · `tez backup` · `tez prisma -o prisma.svg` | Sorgulama ve bakım | gerekmez |

Ortak bayraklar: `--library <yol>`, `--json` (betikler için kararlı çıktı), `--lang tr|en`, `--quiet`. Çıkış kodları: `0` başarı, `1` hata, `2` kısmi başarı (örneğin bir arama kaynağı başarısız).

### Nasıl çalışır

- **Tek başlatıcı:** `tez`, arka uç ikilisinin konsol modudur (tez-backend cli'ye giden ince bir konsol kabuğu). Windows'ta pencereli (GUI) programlar terminale çıktı yazamadığı için tez ayrı bir konsol programı olmak zorunda; VS Code da bu yüzden code.cmd kullanır. Pencere gerektiren komutlarda tez, masaüstü uygulamasını argümanlarla çalıştırır; Tauri'nin tek örnek (single-instance) mekanizması bunu çalışan pencereye iletir, pencere yoksa açılır.
- **Başsız komutlar:** Python arka ucunun `cli` giriş noktasına (Typer) gider ve aynı servisleri çağırır.
- **Eşzamanlılık kuralı:** Kütüphane açık bir pencerede kullanılıyorsa CLI, `.tez/instance.json`'daki port ve token ile o örneğin yerel API'sine bağlanır; değilse kütüphane kilidini alıp veritabanına doğrudan yazar. Aynı anda iki yazar olmaz ve terminalden başlatılan iş arayüzde canlı görünür.
- **Kayıt:** Terminalden yapılan aramalar `search_run.initiated_via = cli` ile loglanır.
- **Tekrarlanabilirlik:** Arama ekranındaki "Terminal komutunu kopyala" düğmesi o aramanın birebir `tez search` karşılığını verir; yöntem bölümüne eklenebilir.

### İşletim sistemine göre kurulum

| Özellik | Windows | macOS | Linux |
| --- | --- | --- | --- |
| `tez` komutu PATH'te | Kurulumda "PATH'e ekle" onay kutusu | Uygulama menüsünde "tez komutunu PATH'e kur" (`/usr/local/bin` bağlantısı, yönetici izni) | Paket `/usr/bin/tez` bağlantısı kurar |
| Open with TEz — dosya | Kayıt defteri: `.pdf`, `.bib`, `.ris` bağlam menüsü | Info.plist belge türleri → Finder "Birlikte Aç" | `.desktop` dosyasında `MimeType` |
| Open with TEz — klasör | Klasör ve klasör arka planı bağlam menüsü | Finder Quick Action (isteğe bağlı) | Nautilus/Dolphin eylemi (isteğe bağlı) |
| `tez://` bağlantıları | Kayıt defteri URL protokolü | `CFBundleURLTypes` | `x-scheme-handler/tez` |
| Varsayılan PDF uygulaması olma | Hayır, yalnızca "Birlikte aç" listesinde | Hayır | Hayır |

Her entegrasyon kurulumda onay kutusuyla seçilir (VS Code kurulumundaki gibi), sonradan Ayarlar › Sistem entegrasyonu'ndan açılıp kapatılır ve kaldırmada temizlenir.

### Güvenlik

- `instance.json` yalnızca kullanıcıya okunabilir (Unix'te 0600, Windows'ta kullanıcı ACL'i); token her açılışta yenilenir.
- `tez://` bağlantıları yalnızca gezinir (makale, sayfa, not açma). İçe aktarma veya silme gibi eylemler bir bağlantıyla tetiklenmez.

### Riskler

- **Windows 11 sağ tık menüsü:** Klasik kayıt defteri girdileri "Daha fazla seçenek göster" altında kalır. Üst menüde görünmek için `IExplorerCommand` + paket kimliği (sparse package) gerekir; ilk sürümde klasik menü, sonra değerlendirme.
- **Kod imzalama:** İmzasız uygulamada SmartScreen ve Gatekeeper uyarı verir; macOS'ta dosya ilişkilendirme imzasız uygulamada güvenilmez olabilir. Maliyeti erken netleşmeli.
- **CLI başlatma süresi:** PyInstaller tek dosya modu her çağrıda açılma gecikmesi ekler. Tek klasör (onedir) modu + tembel import; hedef ilk çıktı < 1 sn.
- **Aşama etkisi:** Başlatıcı, tek örnek ve başsız çekirdek komutlar Aşama 1'e eklendi (görev 22–23); PATH, sağ tık menüsü ve dosya ilişkilendirme kurulum paketiyle Aşama 6'da.

### Bu bölüm için sorular

- "Open with TEz" hangi türlere kaydedilsin: PDF, `.bib`, `.ris`, klasör — hepsi mi?
- Aşama 1'deki başsız komutlar `search`, `import`, `add`, `export` olarak yeterli mi?
- CLI çıktı dili: önerim insan okunur çıktı sistem dilinde, `--json` alan adları her zaman İngilizce.

## Veri modeli

Model 5 gruptan \~35 tablodan oluşuyor; Aşama 1 yalnızca ilk iki grubun çekirdeğini kurar. Tüm tablolarda `id` UUIDv7 (TEXT, zamana göre sıralanabilir; ileride kütüphaneler arası birleştirmede çakışmaz), `created_at`, `updated_at` var. Alan adları İngilizce, kod ile aynı.

### 1. Kütüphane çekirdeği (Aşama 1)

| Tablo | Önemli alanlar | Not |
| --- | --- | --- |
| `paper` | title, title\_norm, abstract, year, venue, venue\_type, volume/issue/pages, language, url, oa\_url, citation\_count, reading\_status, citekey, retraction\_status, deleted\_at | citekey UNIQUE; silme yumuşak (çöp kutusu) |
| `paper_identifier` | paper\_id, scheme (doi/arxiv/s2/openalex/dblp/isbn/zotero), value | UNIQUE(scheme, value); tekilleştirmenin temeli |
| `paper_relation` | from\_paper\_id, to\_paper\_id, kind (version\_of/erratum\_of/retraction\_of) | arXiv ön baskısı ile yayımlanmış sürümü bağlar |
| `author`, `paper_author` | display\_name, family, given, orcid · position, affiliation\_raw | N:N, sıra korunur |
| `attachment` | paper\_id, kind (pdf/supplement), rel\_path, sha256, page\_count, source, text\_status (pending/ok/needs\_ocr/failed), error | sha256 UNIQUE: aynı PDF iki kez saklanmaz |
| `collection`, `collection_paper` | parent\_id, name, sort\_order, is\_system | ağaç; bir makale birden fazla koleksiyonda; is\_system = "Gelen kutusu" gibi sistem koleksiyonları |
| `tag`, `paper_tag` | name, color | N:N |
| `smart_collection` | name, filter\_json | sürümlü filtre DSL'i, sorguya derlenir |

### 2. Arama ve sistematik tarama

| Tablo | Önemli alanlar | Not |
| --- | --- | --- |
| `review` | title, research\_questions\_md, protocol\_md, method (prisma2020/kitchenham\_slr), status | bir tez = bir veya birkaç review |
| `search_query` | review\_id, name, query\_text, filters\_json, alert\_enabled, alert\_last\_run\_at | kayıtlı sorgu ve uyarılar |
| `search_run` | review\_id, query\_id (içe aktarmada boş), source, translated\_query, executed\_at, initiated\_via (gui/cli), total\_reported, retrieved\_count, status, error, snapshot\_path | her kaynak için ayrı satır; ham API yanıtı sıkıştırılmış dosyada |
| `search_result` | run\_id, rank, paper\_id, match\_method (doi/id/title\_fuzzy/new), match\_score | "bulunan" ve "tekrar" sayıları buradan türetilir |
| `review_record` | review\_id, paper\_id, origin (database/citation\_backward/citation\_forward/manual), origin\_ref | UNIQUE(review\_id, paper\_id); kartopu kaynağı da burada |
| `screening_criterion` | review\_id, kind (inclusion/exclusion), code ("E1"), text, stage | hariç tutma gerekçeleri listesi |
| `screening_decision` | review\_id, paper\_id, stage (title\_abstract/full\_text), decision (include/exclude/maybe), criterion\_id, note, reviewer, superseded\_by | yalnızca ekleme; düzeltme yeni satırdır |
| `quality_question`, `quality_assessment` | text, scale · paper\_id, question\_id, score, note | SLR yöntemlerinde zorunlu kalite değerlendirmesi |

### 3. Okuma, not ve matris

| Tablo | Önemli alanlar | Not |
| --- | --- | --- |
| `anchor` | attachment\_id, page\_index, rects\_json, quote\_exact, quote\_prefix, quote\_suffix, char\_start, char\_end | koordinatlar PDF birimi (piksel değil); alıntı metni PDF değişirse yeniden konumlamayı sağlar |
| `annotation` | paper\_id, anchor\_id, kind (highlight/underline/area), color, comment\_md |  |
| `note` | title, body\_md, paper\_id?, review\_id? | serbest not veya makaleye bağlı |
| `note_link` | source\_note\_id, target\_type (note/paper/anchor), target\_id | kayıtta markdown'dan çıkarılır; backlink = ters sorgu |
| `matrix`, `matrix_column` | review\_id, name · name, instruction, data\_type (text/number/enum/multi\_enum/bool), options\_json, sort\_order | `instruction` hem kullanıcıya açıklama hem YZ'ye talimat |
| `matrix_row`, `matrix_cell` | paper\_id, sort\_order · column\_id, value\_text, value\_json, origin (manual/ai\_accepted) | UNIQUE(matrix\_id, paper\_id, column\_id) |
| `cell_evidence` | cell\_id, anchor\_id | bir hücreye birden fazla kaynak cümle |

### 4. Çıkarma, atıf ve işler

| Tablo | Önemli alanlar | Not |
| --- | --- | --- |
| `text_chunk` | attachment\_id, page\_index, section\_id?, ord, text, char\_start, char\_end | FTS5 `chunk_fts` bunun üzerinde; Aşama 5'te sqlite-vec `chunk_vec` |
| `document_section` | attachment\_id, type (abstract/intro/method/results/discussion/other), heading, page\_start, page\_end |  |
| `extracted_asset` | attachment\_id, kind (table/figure), label, caption, page\_index, bbox\_json, anchor\_id, file\_rel\_path, data\_json, extractor, extractor\_version | çıkarıcı sürümü saklanır: yeniden işleme kararı için |
| `reference_entry` | attachment\_id, ord, raw\_text, parsed\_json, matched\_paper\_id?, match\_score | kaynakçanın tek tek girdileri |
| `citation_edge` | citing\_paper\_id, cited\_paper\_id, source (grobid/s2/openalex) | PK iki makale; yalnız kütüphane içi atıflar |
| `processing_job` | type, payload\_json, dedupe\_key, status, priority, attempts, max\_attempts, lease\_until, progress, error | dedupe\_key UNIQUE: aynı iş iki kez kuyruğa girmez |

### 5. Yapay zekâ ve sistem

| Tablo | Önemli alanlar | Not |
| --- | --- | --- |
| `ai_suggestion` | target\_type (matrix\_cell/summary/gap/answer), target\_ref, content\_json, provider, model, prompt\_version, status (pending/accepted/edited/rejected) | onaylanmadan hiçbir hedef tabloya yazılmaz |
| `ai_suggestion_evidence` | suggestion\_id, anchor\_id, verified | `verified` = alıntı kaynak metinde birebir bulundu |
| `paper_fts`, `note_fts` | title\_norm, abstract, authors · body | FTS5 sanal tablolar |
| `setting` | key, value\_json | API anahtarları burada değil, işletim sistemi anahtar zincirinde (Python keyring; CLI de pencere olmadan erişir) |

**Üç tasarım kararı:**

- PRISMA sayıları saklanmaz, `search_result`, `review_record` ve `screening_decision`'dan türetilir; diyagram ile veri tutarsız olamaz.
- Eleme kararları değiştirilemez kayıttır. Yöntem bölümü için tam iz verir; ileride iki değerlendiricili eleme ve Cohen kappa hesabı şema değişmeden eklenir.
- Türkçe büyük/küçük harf (İ/ı) FTS5'in `unicode61` tokenizer'ında doğru katlanmaz; `title_norm` gibi normalize kolonlar uygulama tarafında üretilip indekslenir.

## Klasör yapısı

Tek bir monorepo; ön yüz hem tarayıcıda hem Tauri içinde aynı kodla çalışır, arka uç modülleri dikey dilimlerdir.

```text
tez/
├─ apps/
│  ├─ web/                      # React + TS (Vite) — tarayıcıda ve Tauri içinde aynı kod
│  │  ├─ src/
│  │  │  ├─ app/                # router, sağlayıcılar, düzen (kenar çubuğu · ana alan · denetçi)
│  │  │  ├─ api/                # OpenAPI'den üretilen istemci (elle düzenlenmez)
│  │  │  ├─ features/           # search, library, reader, screening, notes, matrix, ai, settings
│  │  │  │  └─ library/         # components/, hooks/, routes.tsx, *.test.tsx
│  │  │  ├─ components/ui/      # paylaşılan bileşenler (Radix tabanlı)
│  │  │  ├─ lib/platform/       # tauri.ts / browser.ts: dosya seçici, klasör açma, sidecar adresi
│  │  │  └─ i18n/               # react-i18next kurulumu
│  │  ├─ locales/{tr,en}/       # çeviri JSON dosyaları
│  │  └─ e2e/                   # Playwright testleri (web modunda)
│  └─ desktop/
│     └─ src-tauri/             # Tauri v2: sidecar başlatma, port/token aktarımı, güncelleme
├─ backend/
│  ├─ pyproject.toml            # uv ile yönetilir
│  ├─ alembic/                  # migration'lar
│  ├─ src/tez/
│  │  ├─ main.py                # uygulama fabrikası
│  │  ├─ worker.py              # iş kuyruğu işçisi (ayrı süreç)
│  │  ├─ cli/                   # tez komutu (Typer): search, import, add, export, open
│  │  ├─ core/                  # config, db (pragmalar, oturum), auth (token), errors, logging
│  │  ├─ shared/                # http (hız sınırı, önbellek, yeniden deneme), ids, text (normalize)
│  │  ├─ jobs/                  # queue.py, registry.py, handlers/
│  │  └─ modules/
│  │     ├─ library/            # papers, collections, tags, smart collections
│  │     ├─ search/
│  │     │  ├─ providers/       # openalex.py, semantic_scholar.py, arxiv.py, crossref.py, dblp.py
│  │     │  ├─ dedup.py
│  │     │  ├─ service.py · repository.py · router.py · schemas.py
│  │     ├─ files/              # PDF depolama, Unpaywall
│  │     ├─ importers/          # bibtex, ris, (Aşama 6) zotero
│  │     ├─ screening/ · notes/ · matrix/ · extraction/ · citations/ · ai/ · export/
│  │     └─ reviews/
│  └─ tests/
│     ├─ unit/ · integration/
│     └─ fixtures/              # örnek PDF'ler, kaydedilmiş API yanıtları (cassette)
├─ packaging/                   # windows/ (kayıt defteri, NSIS), macos/ (Info.plist, Quick Action), linux/ (.desktop, MIME)
├─ docs/
│  ├─ architecture.md
│  └─ adr/                      # mimari karar kayıtları (0001-sqlite-vec.md …)
├─ scripts/                     # gen-api-client, build-sidecar, seed-demo-library
└─ .github/workflows/           # ci.yml (lint + test), release.yml (Aşama 6)
```

**Modül iç deseni:** `router` (HTTP) → `service` (iş kuralı) → `repository` (SQL). Modüller birbirinin tablolarına değil servislerine erişir; harici sistemler (`providers/`, LLM, GROBID) birer adaptör arkasındadır. Bu, her modülü sahte (fake) bağımlılıkla tek başına test etmeyi sağlar.

**Kullanıcı kütüphane klasörü** (koddan ayrı):

```text
TEz Library/
├─ library.sqlite          # WAL modunda
├─ files/<ilk 2 hex>/<sha256>.pdf
├─ derived/<attachment_id>/ # çıkarılan görseller, tablolar, GROBID TEI
├─ snapshots/              # arama ham yanıtları (.json.gz)
├─ backups/
└─ .tez/instance.json      # çalışan örnek: port + token (yalnız kullanıcıya açık)
```

## Aşama 1 görevleri

Aşama 1, 24 küçük adımdan oluşur; her adım tek bir PR'dır ve yanındaki kabul kriteri sağlanınca biter. İlk adım bilinçli olarak bir risk denemesidir (spike): paketleme çalışmazsa mimari daha bir satır kod yazılmadan değişir.

### 0. Risk denemesi (1–2 gün)

- [ ] **S1 · Tauri + Python sidecar:** PyInstaller ile paketlenmiş "hello" FastAPI, Tauri v2 tarafından başlatılır, rastgele port + tek kullanımlık token ile bağlanır, uygulama kapanınca süreç ölür; ikinci bir "tez makale.pdf" çağrısı yeni pencere açmadan çalışan pencereye iletilir. *Kabul:* hedef işletim sisteminde kurulup çalışan paket; boyutu kaydedildi.

### A. İskelet ve altyapı

- [ ] **1 · Monorepo ve araçlar:** uv, ruff, pyright, pytest; pnpm, Vite, ESLint, Vitest; pre-commit. *Kabul:* `pnpm check` kök package.json betiğiyle her iki tarafta lint + tip + test çalıştırır (Windows'ta make gerekmez).
- [ ] **2 · CI:** GitHub Actions'ta lint, tip kontrolü, test (Ubuntu). *Kabul:* PR'da yeşil rozet.
- [ ] **3 · Arka uç çekirdeği:** config, yapılandırılmış log, hata modeli (hata kodları, metin değil), token doğrulama, `/health`. *Kabul:* tokensız istek 401 döner.
- [ ] **4 · Veritabanı:** SQLAlchemy 2, SQLite pragmaları (WAL, foreign\_keys, busy\_timeout), Alembic. *Kabul:* boş veritabanından `upgrade head` → `downgrade base` testi geçer.
- [ ] **5 · Kütüphane klasörü:** oluştur/aç, kilit dosyası + örnek keşif dosyası (aynı kütüphaneyi iki pencere açamaz; CLI çalışan örneğe bağlanır). *Kabul:* ikinci açılış anlaşılır hata verir.
- [ ] **6 · Aşama 1 tabloları:** 1. ve 2. gruptaki tablolar (kalite değerlendirmesi hariç) + `processing_job` + `setting`. *Kabul:* repository birim testleri, kısıt ihlali testleri.
- [ ] **6b · İş kuyruğu ve işçi süreci:** `processing_job` üzerinde kiralama (lease) tabanlı kuyruk, `tez-backend worker`, API'nin işçiyi başlatıp izlemesi, ilerleme için SSE uç noktası. *Kabul:* işçi süreci öldürülünce iş, kira dolunca yeniden denenir; ilerleme arayüzde görünür.
- [ ] **7 · API istemci üretimi:** OpenAPI → `openapi-typescript` + `openapi-fetch`. *Kabul:* CI, üretilmiş istemci güncel değilse kırılır.
- [ ] **8 · Ön yüz kabuğu:** yönlendirme, üç panelli düzen, TanStack Query, tr/en, açık/koyu tema, platform adaptörü; Tailwind CSS + shadcn/ui, tasarım tokenları docs/design/ klasöründen CSS değişkeni olarak; temel Ayarlar ekranı (dil, tema, kaynak e-postası ve API anahtarları). *Kabul:* dil ve tema değişimi kalıcı; tarayıcıda ve Tauri'de açılır.

### B. Çoklu kaynakta arama

- [ ] **9 · HTTP katmanı:** paylaşılan `httpx` istemcisi, kaynak başına hız sınırlayıcı, üstel geri çekilmeli yeniden deneme, yanıt önbelleği. *Kabul:* 429 ve zaman aşımı senaryoları sahte sunucuyla test edildi.
- [ ] **10 · Ortak kayıt şeması:** `NormalizedRecord` (başlık, yazarlar, yıl, tanımlayıcılar, özet, OA bağlantısı). *Kabul:* şema testleri.
- [ ] **11 · Sağlayıcılar:** OpenAlex, Semantic Scholar, arXiv, Crossref (her biri ayrı PR). *Kabul:* kaydedilmiş gerçek yanıtlarla (cassette) eşleme testleri; ağ olmadan çalışır.
- [ ] **12 · Tekilleştirme:** DOI/arXiv normalize (önek, sürüm eki, büyük/küçük harf), bulanık başlık eşleşmesi (rapidfuzz) + yıl ± 1 + ilk yazar. *Kabul:* zor vakalar tablosu (ön baskı/yayın, noktalama farkı, Türkçe karakter) geçer.
- [ ] **13 · Federe arama servisi:** kaynaklar paralel, kısmi hata tolere edilir, `search_run`/`search_result` ve ham anlık görüntü yazılır. *Kabul:* bir kaynak çökünce diğer sonuçlar yine gelir ve hata kayda geçer.
- [ ] **14 · Arama arayüzü:** sorgu formu, kaynak başına durum, tekilleştirilmiş sanallaştırılmış liste, "review'a/kütüphaneye ekle", arama geçmişi. *Kabul:* 1000 sonuçta akıcı kaydırma.

### C. İçe aktarma ve dosyalar

- [ ] **15 · BibTeX/RIS içe aktarma:** aynı `NormalizedRecord` → tekilleştirme yolundan geçer ve `search_run` olarak loglanır (IEEE/Scopus dışa aktarımları için). *Kabul:* örnek dosyalar, hatalı girdi raporu.
- [ ] **16 · PDF ekleme:** sürükle-bırak, sha256, kütüphane klasörüne kopyalama, sayfa sayısı (pypdfium2). *Kabul:* aynı PDF ikinci kez eklenmez; bozuk PDF işaretlenir, uygulama çökmez.
- [ ] **17 · Açık erişim PDF:** Unpaywall + arXiv'den bulma ve indirme, `processing_job` olarak. *Kabul:* indirme arka planda; ilerleme arayüzde görünür.

### D. Explorer ve okuyucu

- [ ] **18 · Koleksiyon ve etiketler:** ağaç CRUD, sürükle-bırak, çoklu koleksiyon, etiketler, okuma durumu. *Kabul:* entegrasyon testleri + E2E akışı.
- [ ] **19 · Kütüphane listesi:** sanallaştırılmış tablo, sıralama/filtre, detay paneli, meta veri FTS araması. *Kabul:* 2000 makalelik demo kütüphanede arama < 100 ms.
- [ ] **20 · PDF görüntüleyici:** pdfjs-dist, PDF arka uçtan HTTP Range ile akıtılır, sanallaştırılmış sayfalar, yakınlaştırma, metin katmanı, `?page=` ile derin bağlantı. *Kabul:* 300 sayfalık PDF'te bellek ve kaydırma kabul edilebilir.
- [ ] **21 · Kapanış:** yedekleme (SQLite backup API + zip), README, mimari belgesi, ilk ADR'ler, Playwright duman testi. *Kabul:* yedekten geri yükleme testi geçer.

### E. Terminal ve tek örnek

- [ ] **22 · Tek örnek ve argüman iletimi:** Tauri single-instance ve deep-link eklentileri; `tez`, `tez <pdf>`, `tez <klasör>` ve `tez://` çağrıları çalışan pencereye iletilir; `.tez/instance.json` keşif dosyası. *Kabul:* uygulama açıkken ve kapalıyken aynı komut aynı sonucu verir, ikinci pencere açılmaz.
- [ ] **23 · Başsız CLI çekirdeği:** Typer ile `tez search`, `tez import`, `tez add`, `tez export`; `--json`, `--library`, çıkış kodları. Çalışan örnek varsa onun API'sine, yoksa kilidi alıp doğrudan veritabanına. *Kabul:* uçtan uca testler iki modda da geçer; `--help` Türkçe ve İngilizce.

Aşama 1'e bilerek alınmayanlar: PDF tam metin indeksleme (Aşama 3), kayıtlı sorgu uyarıları ve kartopu (Aşama 4), Zotero, PATH kurulumu, sağ tık menüsü ve dosya ilişkilendirme (Aşama 6, kurulum paketiyle).

## Aşama 1 sonrası kararlar: her alana açık TEz

Nov 11, 2026 · Ayrıntı ve gerekçe: ADR 0019

Aşama 1 bittikten sonra bir akademisyenin (psikolog) geri bildirimiyle kapsam netleşti: **TEz her daldan araştırma ve tez içindir** (beşerî bilimler, hukuk, eğitim, sağlık, mühendislik…). Hiçbir alan grubu esas alınmaz. Plandaki bilgisayar bilimine yaslanan varsayılanlar (Kitchenham, DBLP, IEEE/ACM vurgusu, örnek matris sütunları) bu yüzden ürünün kapsamı değil, sahibinin tezinden gelen başlangıç ayarlarıdır.

### Veritabanları için iki yol

| Yol | Ne zaman | Örnekler | Nasıl |
| --- | --- | --- | --- |
| API | Açık, belgeli API'si olan ve kullanım koşulları uygun kaynak | Var: OpenAlex, Semantic Scholar, arXiv, Crossref. Aday: PubMed, Europe PMC, DOAJ, ERIC, CORE, DergiPark (OAI-PMH), TR Dizin | Sağlayıcı adaptörü (ADR 0008); her biri için onay, güncel belge kontrolü, ADR ve CLAUDE.md 1. kuraldaki ağ listesinin güncellenmesi |
| Dosya | API'si olmayan, ücretli veya otomasyonu yasaklayan kaynak | Google Scholar, JSTOR, Scopus, Web of Science, ScienceDirect, EBSCO, ProQuest, PsycINFO, HeinOnline, IEEE Xplore, ACM DL | Dışa aktarılan dosya arama kaydı olarak içe alınır (Görev 15); veritabanı adı, tarih ve sorgu kaydedilir, PRISMA'da kendi kutusuyla sayılır |

Dosya yolu yedek değil, birinci sınıf yoldur. Kazıma (scraping) yok: kullanım koşulları otomasyonu yasaklayan veya bot kontrolü yapan siteye (Google Scholar, JSTOR) bağlanılmaz, CAPTCHA aşılmaz. Koşulları belirsiz kaynak, koşullar netleşene kadar eklenmez.

### Aşamalara dağılım

| Ne | Aşama | Ön koşul |
| --- | --- | --- |
| Yeni review'larda varsayılan yöntem PRISMA 2020 (Kitchenham SLR seçenek olarak kalır); review formundaki varsayılan değişir | 2, başı | — |
| Veritabanı ön ayarlı içe aktarma: kullanıcı "JSTOR", "Web of Science", "Google Scholar"… seçer; her birinin dışa aktarma biçimi (WoS düz metni, Scopus CSV, tek tek BibTeX) ve tuhaflıkları TEz'de çözülür | 2, başı | Her veritabanından gerçek, küçük, kendi ürettiğimiz örnek dosya |
| "Bu veritabanından nasıl dışa aktarılır" kısa rehberi (arama ekranında) | 2, başı | Ön ayarlarla birlikte |
| PRISMA diyagramında "diğer yöntemler" dalı: kartopu ile birlikte gri literatür (tez, rapor, kayıt) | 2 | PRISMA görevi |
| Yeni API sağlayıcıları, bu sırayla: (1) PubMed + Europe PMC, (2) DOAJ + ERIC + CORE, (3) TR Dizin + DergiPark (DergiPark'ın koşulları açık olduğu için öne alınabilir) | 2'den başlayarak | Her biri ayrı onay + güncel belge kontrolü + ADR + CLAUDE.md 1. kural güncellemesi |
| TR Dizin: önce arayüzünden alınan BibTeX dosyasıyla içe aktarma denemesi; sonra doğrudan sağlayıcı | 2 (deneme hemen) | Doğrudan sağlayıcı için TR Dizin'in yazılı onayı (aşağıda "Kullanım koşulları") |
| İki değerlendiricili eleme: kararların bir kütüphaneden diğerine aktarılması, "Çakışmalar" sekmesi, Cohen kappa | 2, sonu | Tek kişilik eleme bitmiş olmalı; şema hazır (`reviewer`) |
| Biçimlendirilmiş kaynakça (CSL): en az APA 7, MLA, Chicago, Vancouver, IEEE; Türkçe ve İngilizce; kapsam seçili / koleksiyon / review'da dahil edilenler; panoya ve dosyaya. Dışa aktarma ekranıyla (tasarım 5.10) birlikte | 2, sonu | Eleme kararları. Arka uçta `citeproc-py` (BSD-2-Clause-Views, uygun); `citeproc-js` AGPL/CPAL olduğu için kullanılmaz |
| Enstitü tez yazım kılavuzlarına göre özel CSL stilleri | CSL'den sonra, ihtiyaç doğdukça | — |
| Kalite değerlendirmesi alandan bağımsız: kullanıcının kendi soruları ve ölçeği veya hazır kontrol listesi (Kitchenham, JBI, RoB 2 gibi yanlılık riski araçları) | Kalite değerlendirme görevi geldiğinde | Şema hazır (`quality_question`, `quality_assessment`) |
| Yayın türlerinde kitap, kitap bölümü ve tez: filtreler ve dışa aktarma | Arama filtreleri ve dışa aktarma ekranıyla | — |
| YÖK Ulusal Tez Merkezi: deneysel, varsayılanı kapalı kaynak; "şu an hangi tezler yapılıyor" için kayıtlı sorgu uyarılarıyla | 4 | YÖK'ün yazılı onayı; resmi API yok |
| Word içinde yazarken atıf eklentisi | Kapsam dışı | Zotero'ya aktarım (Aşama 6) bu yolu karşılar |

### Kullanım koşulları: TR Dizin ve YÖK Tez

İkisine de e-postayla sorulur: TR Dizin için `trdizin@tubitak.gov.tr` (TÜBİTAK ULAKBİM), YÖK Ulusal Tez Merkezi için `tezmerkezi@yok.gov.tr`. Sorular: resmi bir API veya veri erişim yolu var mı; kullanıcının başlattığı aramalarla bir masaüstü uygulamasının meta veri (başlık, yazar, özet, yıl, DOI) çekmesine izin veriliyor mu; hız sınırı, kayıt/anahtar ve atıf şartı.

- **Olumlu cevap:** ilgili kaynak, yukarıdaki sıraya göre sağlayıcı olarak eklenir (ADR + onay).
- **Olumsuz cevap, "böyle bir şey yok" veya cevap yok:** doğrudan sağlayıcı yazılmaz; yalnız dosya yolu. TR Dizin arayüzden alınan BibTeX ile gelir; YÖK Tez'in dışa aktarımı yoksa kaynak eklenmez.

## Riskler, eksikler ve alternatifler

En büyük risk teknik değil: aracın kendisi tez taramasını geciktirebilir. Bu yüzden önce taramanın kritik yolunu (arama → eleme → okuma → matris) uçtan uca çalışır hale getirmeyi, gerisini ihtiyaç doğdukça eklemeyi öneriyorum.

### Riskler

| Risk | Etkisi | Önlem |
| --- | --- | --- |
| Kapsam | 6 aşama tek kişiye çok; tez takvimini zorlar | Kritik yol önce; kartopu Aşama 4'ten 2'ye (her alanda kullanılan tamamlayıcı yöntem, API ile ucuz); grafik ve uyarılar sonra |
| Paket boyutu | Docling/torch ve OCR modelleri paketi GB'lara çıkarır | Çekirdek uygulama hafif; ağır işleme isteğe bağlı indirilen paket veya harici servis |
| Veri kaynağı kapsamı | Her alanın jürisi kendi veritabanlarını bekler (Scopus, Web of Science, JSTOR, PubMed, PsycINFO, TR Dizin, Google Scholar…); çoğunun açık API'si yok | İki yol (ADR 0019): açık API'si olan kaynak sağlayıcı olur; diğerlerinin dışa aktarımı ön ayarlı içe aktarmayla arama kaydı olur (görev 15) |
| Kaynak kullanım koşulları | Google Scholar ve JSTOR otomasyonu yasaklar veya engeller; TR Dizin ve YÖK Tez'in koşulları belirsiz | Kazıma yok; koşulları belirsiz kaynak netleşene kadar eklenmez, eklenirse deneysel ve varsayılanı kapalı |
| Sorgu eşdeğerliği | Tek sorgu her API'de farklı yorumlanır; raporlama standartları kaynak başına tam sorgu ister | Kaynak başına çevrilmiş sorgu saklanır, gösterilir ve düzenlenebilir |
| API koşulları | Kota, anahtar ve e-posta (polite pool) kuralları sık değişir | Sağlayıcı ayarları yapılandırılabilir; her sağlayıcı yazılmadan önce güncel belgeleri kontrol edilir |
| Konum kayması | PDF yeni sürümle değişirse vurgular ve kanıtlar kayar | Anchor'da metin alıntısı + önek/sonek ile yeniden konumlama |
| Uydurma alıntı | LLM var olmayan cümleyi kaynak gösterebilir | LLM'e numaralı metin parçaları verilir; dönen alıntı arka uçta parçada birebir aranır, bulunamayan iddia gösterilmez |
| Webview farkları | Tauri her işletim sisteminde farklı motor kullanır (WebView2, WKWebView, WebKitGTK); pdf.js performansı değişir | S1 denemesinde hedef sistemlerde pdf.js ölçülür |
| Lisans | PyMuPDF (AGPL) ve Marker (GPL) dağıtım biçimini kısıtlar | Proje lisansı Aşama 1 başında seçilir, ADR'ye yazılır |

### Planda eksik olanlar

- **Review (tarama projesi) kavramı:** arama, kriter, eleme ve PRISMA'yı kütüphaneden ayırır; aynı makale iki taramada farklı karar alabilir.
- **Kalite değerlendirmesi:** Kitchenham SLR'de zorunlu, sağlık taramalarında yanlılık riski olarak beklenir; şemaya eklendi. Araçtan bağımsız tutulur (ADR 0019).
- **PRISMA 2020 ayrıntıları:** "diğer yöntemlerle bulunanlar" dalı (kartopu ve gri literatür: tez, rapor, kayıt) ve "tam metnine erişilemeyen" kayıtlar.
- **Sürüm ilişkisi:** arXiv ön baskısı ile konferans sürümü ayrı kayıt olarak tutulup bağlanmalı.
- **Tekrarlanabilirlik:** her aramanın ham API yanıtı saklanmalı.
- **Güvenlik:** API anahtarları işletim sistemi anahtar zincirinde; sidecar yalnızca 127.0.0.1 + token.
- **Hata bildirimi:** lab arkadaşları kullanmaya başlayınca log dışa aktarma ve "tanılama paketi" gerekecek.

### Önerdiğim kütüphaneler

- **Arka uç:** iş kuyruğu için harici araç yerine SQLite'ta kiralama (lease) tabanlı basit kuyruk; HTTP için `httpx` + `hishel` (önbellek) + `tenacity`; eşleşme için `rapidfuzz`; içe aktarma için `bibtexparser` v2 ve `rispy`.
- **Ön yüz:** sunucu durumu TanStack Query, arayüz durumu Zustand; liste ve matris TanStack Table + Virtual; Markdown düzenleyici CodeMirror 6; atıf grafiği Sigma.js (Aşama 4); kısayollar `tinykeys`.
- **Test:** `pytest` + `vcrpy` (kaydedilmiş API yanıtları), Vitest + Testing Library, Playwright (web modunda E2E — iki modda çalışmanın bir kazancı).

## Açık sorular ve varsayılan kararlar

Sorular yanıtlanana kadar geliştirme bu varsayılanlarla ilerler; bir varsayılan değişirse yalnızca "Etkisi" sütunundaki kısım yeniden ele alınır.

| Soru | Varsayılan karar | Etkisi |
| --- | --- | --- |
| Kapsam | Her daldan araştırma ve tez; hiçbir alan esas alınmaz (ADR 0019) | Varsayılanlar, sağlayıcılar, örnek veri |
| Tez alanı (sahibinin) | LLM destekli kod inceleme; yalnızca demo kütüphanesini ve ilk denemeleri belirler, ürünün kapsamını değil | Örnek veri |
| Tarama yöntemi | Varsayılan PRISMA 2020; Kitchenham SLR seçenek; kartopu (Wohlin) her yöntemle (ADR 0019) | Eleme aşamaları ve review formu (Aşama 2) |
| Çalışma biçimi | Tek kullanıcı: masaüstü + yerel web modu (`tez serve`); çok kullanıcılı sunucu yok | Kimlik doğrulama yok, yalnız token |
| İşletim sistemi | Geliştirme Windows'ta, CI Ubuntu'da; paketler Aşama 6'da Windows → macOS → Linux | S1 denemesi Windows'ta |
| Lisans | MIT; PyMuPDF ve Marker yok, yerine pypdfium2 ve Docling | Bağımlılık seçimi |
| LLM | Aşama 5'e kadar karar gerekmez; arayüz sağlayıcıdan bağımsız | Aşama 5 |
| GROBID | İsteğe bağlı harici servis, Aşama 3'te Docker ile | Aşama 3 |
| Lab işbirliği | Herkesin ayrı kütüphanesi; şemada `reviewer` alanı hazır | Yok |
| Zaman | Aşamalar takvimle değil görev sırasıyla ilerler | Planlama |
| Open with TEz türleri | PDF, `.bib`, `.ris`, klasör | Aşama 6 |
| CLI dili | İnsan okunur çıktı sistem dilinde, `--json` alan adları İngilizce | Görev 23 |
