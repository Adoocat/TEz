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
| API | Açık, belgeli API'si olan ve kullanım koşulları uygun kaynak | Var: OpenAlex, Semantic Scholar, arXiv, Crossref. Aday: PubMed, Europe PMC, DOAJ, ERIC, CORE, DergiPark (OAI-PMH) | Sağlayıcı adaptörü (ADR 0008); her biri için onay, güncel belge kontrolü, ADR ve CLAUDE.md 1. kuraldaki ağ listesinin güncellenmesi |
| Dosya | API'si olmayan, ücretli veya otomasyonu yasaklayan kaynak | Google Scholar, JSTOR, Scopus, Web of Science, ScienceDirect, EBSCO, ProQuest, PsycINFO, HeinOnline, IEEE Xplore, ACM DL, TR Dizin, YÖK Ulusal Tez Merkezi | Dışa aktarılan dosya arama kaydı olarak içe alınır (Görev 15); veritabanı adı, tarih ve sorgu kaydedilir, PRISMA'da kendi kutusuyla sayılır |

Dosya yolu yedek değil, birinci sınıf yoldur. Kazıma (scraping) yok: kullanım koşulları otomasyonu yasaklayan veya bot kontrolü yapan siteye (Google Scholar, JSTOR) bağlanılmaz, CAPTCHA aşılmaz. Koşulları belirsiz kaynak, koşullar netleşene kadar eklenmez.

### Aşamalara dağılım

| Ne | Aşama | Ön koşul |
| --- | --- | --- |
| Yeni review'larda varsayılan yöntem PRISMA 2020 (Kitchenham SLR seçenek olarak kalır); review formundaki varsayılan değişir | 2, başı | — |
| Veritabanı ön ayarlı içe aktarma: kullanıcı "JSTOR", "Web of Science", "Google Scholar"… seçer; her birinin dışa aktarma biçimi (WoS düz metni, Scopus CSV, tek tek BibTeX) ve tuhaflıkları TEz'de çözülür | 2, başı | Her veritabanından gerçek, küçük, kendi ürettiğimiz örnek dosya |
| "Bu veritabanından nasıl dışa aktarılır" kısa rehberi (arama ekranında) | 2, başı | Ön ayarlarla birlikte |
| PRISMA diyagramında "diğer yöntemler" dalı: kartopu ile birlikte gri literatür (tez, rapor, kayıt) | 2 | PRISMA görevi |
| Yeni API sağlayıcıları, bu sırayla: (1) PubMed + Europe PMC, (2) DOAJ + ERIC + CORE, (3) DergiPark (koşulları açık olduğu için öne alınabilir) | 2'den başlayarak | Her biri ayrı onay + güncel belge kontrolü + ADR + CLAUDE.md 1. kural güncellemesi |
| TR Dizin: yalnız dosya yolu; arayüzünden alınan BibTeX, ön ayarlı içe aktarmada "TR Dizin" olarak | 2, başı (deneme hemen) | Gerçek bir TR Dizin dışa aktarımıyla deneme |
| İki değerlendiricili eleme: kararların bir kütüphaneden diğerine aktarılması, "Çakışmalar" sekmesi, Cohen kappa | 2, sonu | Tek kişilik eleme bitmiş olmalı; şema hazır (`reviewer`) |
| Biçimlendirilmiş kaynakça (CSL): en az APA 7, MLA, Chicago, Vancouver, IEEE; Türkçe ve İngilizce; kapsam seçili / koleksiyon / review'da dahil edilenler; panoya ve dosyaya. Dışa aktarma ekranıyla (tasarım 5.10) birlikte | 2, sonu | Eleme kararları. Arka uçta `citeproc-py` (BSD-2-Clause-Views, uygun); `citeproc-js` AGPL/CPAL olduğu için kullanılmaz |
| Enstitü tez yazım kılavuzlarına göre özel CSL stilleri | CSL'den sonra, ihtiyaç doğdukça | — |
| Kalite değerlendirmesi alandan bağımsız: kullanıcının kendi soruları ve ölçeği veya hazır kontrol listesi (Kitchenham, JBI, RoB 2 gibi yanlılık riski araçları) | Kalite değerlendirme görevi geldiğinde | Şema hazır (`quality_question`, `quality_assessment`) |
| Yayın türlerinde kitap, kitap bölümü ve tez: filtreler ve dışa aktarma | Arama filtreleri ve dışa aktarma ekranıyla | — |
| YÖK Ulusal Tez Merkezi: yalnız dosya yolu; sitenin arama sonuçlarını dosyaya aktarma imkânı varsa ön ayarlı içe aktarmaya eklenir, yoksa kaynak olarak eklenmez. Tezler yine her dosya kaynağından ve PRISMA'nın gri literatür dalından gelebilir | 2, ön ayarlarla | YÖK Tez'in dışa aktarımı olup olmadığı kontrol edilir |
| Kayıtlı harici arama (dosya yolundaki her veritabanı için): sorgu ve veritabanı review'da saklanır; "Siteyi aç" siteyi kullanıcının tarayıcısında açar ve sorguyu panoya kopyalar. Aynı arama yeniden içe aktarılınca "son içe aktarmadan beri N yeni kayıt" farkı gösterilir, eleme kuyruğuna yalnız yeniler girer; her içe aktarma yine ayrı `search_run` | 2, ön ayarlarla | `search_query`'ye harici veritabanı bilgisi (migration) |
| Harici aramalar için yenileme hatırlatması ("YÖK Tez'de son arama 32 gün önce, yenilensin mi?"); ağa çıkmaz, yalnız son içe aktarma tarihine bakar | 4, kayıtlı sorgu uyarılarıyla | Kayıtlı harici arama |
| Tezler API'li kaynaklardan: OpenAlex'in tez (`dissertation`) türü ve CORE'un topladığı üniversite açık arşivleri; Aşama 4 uyarıları tezler için de otomatik çalışır. YÖK Tez'in yerini tutmaz, boşluğu kısmen kapatır | OpenAlex: 2 (yayın türü filtresiyle); CORE: kendi sağlayıcı sırasında | Örnek sorgularla Türk tezleri kapsamının ölçülmesi |
| Word içinde yazarken atıf eklentisi | Kapsam dışı | Zotero'ya aktarım (Aşama 6) bu yolu karşılar |

### TR Dizin ve YÖK Tez: yalnız dosya yolu

İkisinin de otomatik erişim için yayımlanmış koşulu yok (YÖK Tez'in API'si hiç yok). Kurumlara sorulmayacak; ilerlenebilir yol seçildi: ikisi de yalnız dosya yolundan gelir. Resmi, belgeli bir API yayımlanırsa API yoluna alınması yeniden değerlendirilir (onay + ADR).

## Aşama 2 görevleri

Nov 14, 2026 · Onaylandı. Kapsam: "Aşama 1 sonrası kararlar" tablosunda 2. aşamaya konan her şey ve taramanın kritik yolunun ikinci halkası (eleme ve PRISMA). Kartopu, Riskler tablosundaki karara göre Aşama 4'ten buraya alındı.

Numaralar Aşama 1'den devam eder (branch adları çakışmasın diye). Her adım yine tek PR'dır. Sıra kritik yolu izler: önce review ve kaynaklar, sonra eleme, sonra PRISMA ve diğer yöntemler, en sonda çıktılar ve iki değerlendirici.

**Bu aşama için alınan arayüz kararları (Nov 14, 2026):** Koyu tema bugünkü tokenlarla (`docs/design/tokens.json`) olduğu gibi kalır. Elemede "Atla" `→` tuşudur ve karar çubuğunda tıklanabilir bir "Atla" düğmesi de vardır. Space elemede kullanılmaz; `J`/`K` kayıtlar arasında karar vermeden gezinir.

### A. Review temeli

- [ ] **24 · Review oluşturma ve paneli:** varsayılan yöntem PRISMA 2020 (Kitchenham SLR seçenek); oluşturma sihirbazı (tasarım 4.1: başlık, yöntem, araştırma soruları, protokol notu); review paneli (tasarım 5.1: aşama ilerlemesi, her aşamada bekleyen sayı ve "devam et", son aramalar, küçük PRISMA özeti için yer). *Kabul:* yeni review'un yöntemi PRISMA 2020; eski review'lar değişmez; panel sayıları türetilir (servis testi + E2E).
- [ ] **25 · Eleme kriterleri:** dahil etme / hariç tutma kriterleri; kod (`I1`, `E1`), aşama (başlık-özet, tam metin, ikisi), sıra (ilk dokuzu `1`–`9` kısayolu). Kullanılmış kriter silinmez, arşivlenir. *Kabul:* kullanılmış kriteri silmek `screening.criterion_in_use` döner; sıra değişince kısayol numaraları da değişir.

### B. Kaynaklar: dosya yolu ve yeni API'ler

- [ ] **26 · Ön ayarlı içe aktarma ve dışa aktarma rehberi:** kullanıcı veritabanını seçer: Web of Science düz metin, Scopus CSV, JSTOR / EBSCO / ProQuest / PsycINFO / IEEE Xplore / ACM DL (RIS veya BibTeX), Google Scholar (tek tek BibTeX), TR Dizin (BibTeX), YÖK Tez (yalnız sitesi dışa aktarıyorsa). Her biçimin tuhaflıkları TEz'de çözülür; `search_run.source` veritabanının adıdır. Arama ekranında veritabanı başına kısa "nasıl dışa aktarılır" rehberi (tr/en). *Kabul:* her ön ayar için gerçek, küçük, kendi ürettiğimiz örnek dosyayla test (alanlar, Türkçe karakterler, uyarılar); örnek dosyası olmayan veritabanının ön ayarı, dosya gelene dek gizli.
- [ ] **27 · Kayıtlı harici arama:** `search_query`'ye harici veritabanı (migration). "Siteyi aç" siteyi kullanıcının tarayıcısında açar ve sorguyu panoya kopyalar. Aynı aramanın yeni içe aktarımı "son içe aktarmadan beri N yeni kayıt" gösterir, eleme kuyruğuna yalnız yeniler girer; her içe aktarma yine ayrı `search_run`. *Kabul:* aynı dosyayı iki kez içe aktarmak 0 yeni verir; bir kayıt eklenmiş dosya 1 yeni verir; PRISMA iki `search_run`'ı da görür.
- [ ] **28 · Yayın türleri ve tezler:** kitap, kitap bölümü, tez (yüksek lisans / doktora); tez türü saklanır (migration); arama ve kütüphanede yayın türü filtresi; OpenAlex'te `dissertation` filtresi; BibTeX'te `@mastersthesis` / `@phdthesis`, RIS'te `THES`. *Kabul:* tür eşleme tablosu testleri (dört sağlayıcı + içe aktarma); yazıcı–içe aktarıcı gidiş-dönüşünde tez türü korunur.
- [ ] **29 · PubMed ve Europe PMC sağlayıcıları** (iki PR): her biri için önce onay, güncel API belgesi kontrolü, ADR ve CLAUDE.md 1. kuraldaki ağ listesinin güncellenmesi; sorgu çevirisi (MeSH alanları dahil), hız sınırları, `ok` / `partial` / `error`. *Kabul:* kaydedilmiş gerçek yanıtlarla (cassette) eşleme testleri, ağ olmadan; tekilleştirme PMID ve PMCID'yi tanır.

### C. Eleme

- [ ] **30 · Kısayol altyapısı:** `tinykeys`; bağlam başına tek kısayol haritası (genel, eleme, okuyucu, liste); `?` katmanı ve düğmelerdeki `kbd` ipuçları aynı haritadan üretilir; yazı alanındayken kısayollar susar. *Kabul:* aynı bağlamda çift atama testte kırılır; `?` katmanı tr/en.
- [ ] **31 · Eleme servisi ve API:** kararlar yalnız eklenir (düzeltme ve geri alma yeni satır, `superseded_by`); hariçte gerekçe zorunlu; başlık-özette dahil / belki olanlar tam metin kuyruğuna geçer; kuyruk sırası kararlı; filtreler (kararsız, belki, dahil, hariç); kaydın güncel durumu türetilir. *Kabul:* zor vakalar tablosu (geri al, düzelt, aşama atlama denemesi, gerekçesiz hariç); 2000 kayıtlık review'da sonraki kayıt sunucuda < 50 ms.
- [ ] **32 · Başlık-özet eleme ekranı:** tasarım 5.2 odak modu: büyük başlık ve özet, kriter paneli, karar çubuğu `I` · `E` + `1`–`9` · `M` · Atla `→` (tıklanabilir düğmesi de var) · Geri al `U` · Not `N`; `J`/`K` ile gezinme; özette anahtar kelimeler vurgulu (dahil yeşil, hariç kırmızı alt çizgi, Türkçe katlamayla); ilerleme, oturum sayacı, filtre; liste modu (satırda tek tuşla karar). *Kabul:* E2E: 20 kayıt yalnız klavyeyle, aynı 20 kayıt yalnız fareyle (Atla düğmesi dahil) elenir; karardan sonra sonraki kayıt < 100 ms.
- [ ] **33 · Tam metin eleme:** solda okuyucu (Görev 20); kriter paneli ve karar çubuğu aynı; PDF yoksa "PDF'leri bul" (Görev 17) ve "Tam metne erişilemedi" (PRISMA'da ayrı sayılır). *Kabul:* E2E: PDF'li ve PDF'siz kayıt; "erişilemedi" PRISMA'da kendi kutusunda.

### D. PRISMA ve diğer yöntemler

- [ ] **34 · PRISMA sayıları:** PRISMA 2020 akışının her kutusu `search_run`, `search_result`, `review_record` ve `screening_decision`'dan türetilir (kaynak başına bulunan, tekrar, elenen, erişilemeyen, gerekçe başına hariç, dahil); "diğer yöntemler" dalı (kartopu, web siteleri, kuruluşlar, kayıtlar, tezler); hiçbir sayı saklanmaz. *Kabul:* elle hesaplanmış örnek review'lar tablosu; kutular arası değişmezler (bulunan = tekrar + elenen + …) testi; karar düzeltilince sayılar doğru değişir.
- [ ] **35 · PRISMA diyagramı:** tasarım 5.7; SVG; kutu etiketleri düzenlenebilir (etiket saklanır, sayı saklanmaz); tr/en; siyah-beyaz baskı teması; SVG ve PNG dışa aktarma; review panelindeki küçük özet aynı veriden. *Kabul:* diyagramdaki her sayı Görev 34'le aynı; dışa aktarılan SVG geçerli ve kendi başına açılır.
- [ ] **36 · Kartopu:** seçili dahil edilenlerden geri (kaynakça) ve ileri (atıf yapanlar) kartopu, OpenAlex ve Semantic Scholar üzerinden, işçide iş olarak; sonuçlar tekilleştirilir; `review_record.origin` = `citation_backward` / `citation_forward`, kaynak makale `origin_ref`'te; turlar (Wohlin) numaralanır; yeni kayıtlar eleme kuyruğuna girer. *Kabul:* cassette'lerle; review'da zaten olan kayıt yeniden eklenmez; PRISMA'da "diğer yöntemler" dalında tur başına sayılır.
- [ ] **37 · Gri literatür:** elle kayıt ekleme (tez, rapor, kayıt, web sayfası) ve bir içe aktarmayı "diğer yöntemler" (web sitesi, kuruluş) olarak işaretleme; ikisi de tekilleştirmeden geçer. *Kabul:* elle eklenen tez PRISMA'nın diğer yöntemler dalında doğru kutuda; aynı kaydın veritabanından da gelmesi tekrar sayılır.

### E. Kalite değerlendirmesi

- [ ] **38 · Kalite değerlendirmesi:** `quality_question` ve `quality_assessment` (migration); kullanıcının kendi soruları ve ölçeği veya hazır kontrol listesi şablonu (Kitchenham, JBI, RoB 2 gibi; her şablonun lisansı eklenmeden önce kontrol edilir); alandan bağımsız, isteğe bağlı aşama; tam metinde dahil edilenler için. *Kabul:* özel ölçekli bir soru seti ve bir şablonla uçtan uca test; aşama kapalıyken review paneli onu göstermez.

### F. Çıktılar

- [ ] **39 · Biçimlendirilmiş kaynakça (CSL):** arka uçta `citeproc-py` (BSD-2-Clause-Views); en az APA 7, MLA, Chicago, Vancouver, IEEE; Türkçe ve İngilizce yerel ayar; stiller ve yerel ayarlar pakette, CC BY-SA atfı `docs/licenses.md`'de; kapsam: seçili makaleler, koleksiyon veya review'da dahil edilenler. *Kabul:* her stil için kitap, bölüm, makale, bildiri ve tez örneklerinde beklenen çıktı testleri (tr ve en).
- [ ] **40 · Dışa aktarma ekranı:** tasarım 5.10; kapsam seçimi; BibTeX / RIS (Görev 23), biçimlendirilmiş kaynakça (panoya ve dosyaya), atıf anahtarı biçimi önizlemesi; yöntem bölümü için arama stratejisi tablosu (kaynak, tarih, birebir sorgu, sonuç sayısı; Markdown ve CSV); "Terminal komutunu kopyala". *Kabul:* E2E: dahil edilenlerin APA 7 kaynakçası panoya alınır; strateji tablosu her `search_run`'ı içerir.

### G. İki değerlendirici

- [ ] **41 · Kararların kütüphaneler arası aktarımı:** herkes kendi kütüphanesinde eler; kararlar `reviewer` adıyla bir dosyaya (JSON, sürümlü şema) dışa aktarılır ve diğer kütüphaneye alınır; kayıtlar tanımlayıcılarla eşlenir, eşlenemeyenler raporlanır; alınan kararlar da yalnız eklenir. *Kabul:* iki geçici kütüphaneyle gidiş-dönüş testi; aynı dosyayı iki kez almak tekrar oluşturmaz.
- [ ] **42 · Çakışmalar ve Cohen kappa:** "Çakışmalar" sekmesi (iki karar yan yana; uzlaşma kararı yeni satır); aşama başına Cohen kappa ve uyum yüzdesi; PRISMA uzlaşılmış kararlarla sayılır. *Kabul:* kappa elle hesaplanmış örneklerle aynı; uzlaşmadan sonra çakışma listesi boşalır.

Aşama 2'ye bilerek alınmayanlar: DOAJ, ERIC, CORE ve DergiPark sağlayıcıları (PubMed ve Europe PMC'den sonra, sırayla, her biri ayrı onayla); harici aramalar için yenileme hatırlatması ve kayıtlı sorgu uyarıları (Aşama 4); PDF tam metin indeksleme, notlar ve literatür matrisi (Aşama 3); tarayıcı bağlayıcısı (Aşama 6 sonrası, onay + ADR).

## Aşama 3 görevleri

Nov 25, 2026 · Onaylandı. Kapsam: kritik yolun son halkası (okuma → not → matris). 2. aşamadaki gibi her adım tek PR'dır ve numaralar devam eder.

**Alınan kararlar (Nov 25, 2026):** Docling ile otomatik tablo çıkarma ve OCR bu aşamada yok (paket boyutu); tablolar ve şekiller elle seçilen alandan gelir, taranmış PDF'te bilgi şeridi çıkar. GROBID yalnız `localhost` adresinde (1. kural). Not düzenleyici CodeMirror 6 + önizleme; WYSIWYG yok. YZ öğeleri Aşama 5'e kadar gizli.

### 0. Risk denemesi

- [x] **S2 · Metin konumu:** pypdfium2'nin çıkardığı metin, pdf.js'te seçilen metinle aynı yere düşüyor mu? İki sütun, tire bölünmesi, bitişik harf (ligatür), Türkçe karakter ve döndürülmüş sayfa denenir. *Kabul:* örnek PDF'lerde seçimlerin ≥ %95'i doğru yere oturur; sonuç ADR'de.

### A. Tam metin

- [x] **43 · Metin çıkarma:** PDF'ler işçide sayfa sayfa okunur (`text_chunk`); eski PDF'ler de işlenir. *Kabul:* bozuk, şifreli ve taranmış PDF çökertmez, işaretlenir; aynı iş iki kez çalışınca tekrar oluşmaz.
- [x] **44 · Tam metin arama:** `chunk_fts`, Türkçe katlamayla; sonuçta makale, sayfa ve alıntı. *Kabul:* İ/ı testleri geçer; 2000 makalede < 200 ms; sonuç doğru sayfayı açar.
- [x] **45 · Okuyucu geliştirmeleri:** belge içi arama, ana hat ve küçük resimler, farklı sayfa boyutları, eksik yazı tipi ayarları, belge sekmeleri, odak modu (tasarım 4.5). *Kabul:* 300 sayfada akıcı; E2E.

### B. Konum ve vurgular

- [x] **46 · Anchor servisi:** PDF konumu (alıntı + önek/sonek + koordinat), doğrulama, yeniden konumlama, konuma atlama. *Kabul:* değişen PDF'te alıntı yeniden bulunur; bulunamazsa "kayıp" işaretlenir, yanlış yere gitmez.
- [x] **47 · Vurgular:** seçim kutusu, renkler, yorum, alan seçimi, vurgu listesi, `H`. *Kabul:* vurgu her yakınlaştırmada yerinde; E2E.

### C. Notlar

- [x] **48 · Not servisi:** `note`, `note_link`, not araması, geri bağlantılar. *Kabul:* bağlantılar kayıtta güncellenir; hedef silinirse kırık diye işaretlenir.
- [x] **49 · Notlar ekranı:** not ağacı, Markdown düzenleyici, `[[` önerisi, geri bağlantı paneli, otomatik kayıt (tasarım 5.3). *Kabul:* E2E; kapanınca yazı kaybolmaz.
- [x] **50 · Okuyucudan nota:** "Nota alıntıla", "Kopyala (atıflı)", kaynak çipi, `⇧N`. *Kabul:* çip okuyucuyu o cümlede açar.

### D. Literatür matrisi

- [x] **51 · Matris servisi:** matris, sütun türleri (metin, sayı, seçenek, çoklu seçenek, evet/hayır), satırlar dahil edilenlerden türetilir. *Kabul:* tür değişince veri sessizce kaybolmaz; hariç tutulanın hücreleri saklanır.
- [ ] **52 · Matris ızgarası:** sabit başlıklar, klavyeyle düzenleme, filtre, gruplama, geri alma (tasarım 5.4). *Kabul:* 100 × 15 akıcı; E2E.
- [ ] **53 · Hücre kanıtı:** "Matris hücresine bağla", kanıt paneli, okuyucuda Matris sekmesi, kanıt kapsamı yüzdesi. *Kabul:* hücre → PDF cümlesi → hücre gidiş-dönüşü; E2E.
- [ ] **54 · Matris çıktısı:** CSV, Excel, Markdown (kanıt ve sayfayla), kalite puanı sütunu, review panelinde "Veri çıkarma" aşaması. *Kabul:* Türkçe karakterler Excel'de doğru.

### E. Belge yapısı

- [ ] **55 · Şekil ve tablo galerisi:** okuyucuda seçilen alan kaynağıyla kaydedilir; galeri, yan yana karşılaştırma, dışa aktarma (tasarım 5.5). *Kabul:* öğeden PDF'teki yere dönülür.
- [ ] **56 · GROBID (isteğe bağlı):** bölümler ve kaynakça; kapalıyken arayüzde görünmez. *Kabul:* testler kayıtlı yanıtla; GROBID yokken hiçbir şey bozulmaz.

### F. Kapanış

- [ ] **57 · Kapanış:** uçtan uca deneme (Aşama 2'de denenmeyen akışlar dahil), demo verisi, README. *Kabul:* arama → eleme → okuma → matris tek oturumda tamamlanır.

## Riskler, eksikler ve alternatifler

En büyük risk teknik değil: aracın kendisi tez taramasını geciktirebilir. Bu yüzden önce taramanın kritik yolunu (arama → eleme → okuma → matris) uçtan uca çalışır hale getirmeyi, gerisini ihtiyaç doğdukça eklemeyi öneriyorum.

### Riskler

| Risk | Etkisi | Önlem |
| --- | --- | --- |
| Kapsam | 6 aşama tek kişiye çok; tez takvimini zorlar | Kritik yol önce; kartopu Aşama 4'ten 2'ye (her alanda kullanılan tamamlayıcı yöntem, API ile ucuz); grafik ve uyarılar sonra |
| Paket boyutu | Docling/torch ve OCR modelleri paketi GB'lara çıkarır | Çekirdek uygulama hafif; ağır işleme isteğe bağlı indirilen paket veya harici servis |
| Veri kaynağı kapsamı | Her alanın jürisi kendi veritabanlarını bekler (Scopus, Web of Science, JSTOR, PubMed, PsycINFO, TR Dizin, Google Scholar…); çoğunun açık API'si yok | İki yol (ADR 0019): açık API'si olan kaynak sağlayıcı olur; diğerlerinin dışa aktarımı ön ayarlı içe aktarmayla arama kaydı olur (görev 15) |
| Kaynak kullanım koşulları | Google Scholar ve JSTOR otomasyonu yasaklar veya engeller; TR Dizin ve YÖK Tez'in otomatik erişim koşulu yok | Kazıma yok; koşulları belirsiz kaynak yalnız dosya yolundan gelir |
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
