# TEz — Claude Code proje rehberi

TEz, lisansüstü öğrencilerin sistematik literatür taraması yapması için yerel öncelikli (local-first) bir masaüstü uygulamasıdır: arama → eleme → okuma → not/matris → tez yazımına köprü. Sahibi Demirkan (bilgisayar mühendisliği yüksek lisans). Önce kişisel kullanım, sonra lab arkadaşları. Bu bir portföy projesi; kod kalitesi, testler ve dokümantasyon birinci sınıf gereksinimdir.

## Kaynak belgeler (hepsini her oturumda okuma; görev gerektirdiğinde ilgili bölümü oku)

- `docs/plan.md` — mimari, veri modeli, klasör yapısı, Aşama 1 görevleri (S1, 1–23, 6b), riskler, varsayılan kararlar. **Tek doğru kaynak.**
- `docs/design-prompt.md` — arayüz gereksinimleri, ekran tanımları, kısayollar, durumlar.
- `docs/design/` — tasarım ekranları (`screens/`) ve tasarım tokenları (`tokens.*`). UI işine başlamadan önce ilgili ekranı incele.
- `docs/adr/` — mimari karar kayıtları. Plandan her sapma burada belgelenir.
- `docs/progress.md` — görev durumu. Her görevin sonunda güncellenir.

## Mimari özeti

```text
[Tauri v2 kabuğu (Rust)] --başlatır--> [tez-backend serve : FastAPI, 127.0.0.1:<rastgele port>, token]
        |                                     |  alt süreç olarak başlatır ve izler
        |                                     v
        |                              [tez-backend worker : processing_job kuyruğu (lease)]
[React UI (webview veya tarayıcı)] --HTTP + SSE + token--> API

[tez (konsol programı)] --pencere komutları--> TEz uygulamasını argümanlarla çalıştırır (single-instance iletir)
                        --başsız komutlar--> açık örneğin API'si (.tez/instance.json) veya kilitle doğrudan DB

Kütüphane klasörü: library.sqlite (WAL, FTS5) · files/ · derived/ · snapshots/ · backups/ · .tez/
Ağ yalnızca: OpenAlex, Semantic Scholar, arXiv, Crossref, DBLP, Unpaywall; sonra isteğe bağlı GROBID ve LLM
```

Arka uç tek bir ikilidir (`tez-backend`), üç modu vardır: `serve`, `worker`, `cli`. Web modunda `tez serve`, token içeren yerel bir adres yazdırır. `tez` ayrı bir konsol programıdır çünkü Windows'ta pencereli (GUI) programlar terminale çıktı yazamaz.

## Değişmez kurallar

1. **Yerel öncelik:** Kullanıcı verisi kütüphane klasöründen çıkmaz. Ağ yalnızca yukarıdaki servislere.
2. **Doğrulanabilirlik:** PDF'ten gelen her bilgi bir `anchor`a bağlanır. YZ çıktısı kullanıcı onaylamadan kalıcı tabloya yazılmaz.
3. **Sistematiklik:** `search_run`, `search_result` ve `screening_decision` yalnızca eklenir (append-only); düzeltme yeni satırdır.
4. **PRISMA sayıları türetilir**, hiçbir yerde saklanmaz.
5. **Bozuk girdi çökertmez:** PDF, ağ ve ayrıştırma hataları yakalanır, kayda geçer, ilgili öğe işaretlenir.
6. **Lisans MIT:** AGPL/GPL bağımlılık yok (PyMuPDF ve Marker yasak; yerine pypdfium2 ve Docling). Yeni bağımlılığın lisansını kontrol et ve PR açıklamasına yaz.
7. **Sırlar:** API anahtarları işletim sistemi anahtar zincirinde (Python `keyring`). Veritabanına, loglara, test fixture'larına asla.
8. **Plandan sapma:** Önce bana sor; onaylanırsa `docs/adr/NNNN-<konu>.md` yaz (bağlam, karar, sonuçlar).

## Teknoloji

- **Arka uç:** Python 3.12+, uv, FastAPI, Pydantic v2, SQLAlchemy 2 (senkron oturum), Alembic (`render_as_batch=True`), Typer, httpx (async) + hishel + tenacity, rapidfuzz, bibtexparser v2, rispy, pypdfium2, keyring. Test: pytest, pytest-recording (vcrpy). Kalite: ruff, pyright (`src/tez` için strict).
- **Ön yüz:** pnpm, Vite, React, TypeScript (strict), react-router, TanStack Query/Table/Virtual, Zustand, react-i18next, Tailwind CSS + shadcn/ui (Radix), pdfjs-dist, openapi-typescript + openapi-fetch. Test: Vitest + Testing Library, Playwright (web modunda E2E).
- **Masaüstü:** Tauri v2 + eklentiler: single-instance, deep-link, shell (sidecar), dialog. Python ikilisi PyInstaller onedir modunda.
- **Sürüm politikası:** Yeni bağımlılıkta güncel kararlı sürüm; lock dosyaları commit edilir. Plandaki bir kütüphane/API bilgisi güncel belgelerle çelişirse belgeye uy ve bana bildir.

## Kod kuralları

**Arka uç**
- Modül deseni: `modules/<ad>/{router,service,repository,schemas,models}.py`. Router iş mantığı içermez. Modüller birbirinin repository'sine değil, service'ine erişir.
- Hatalar: `TezError(code, params)`; API yanıtı `{"error": {"code": ..., "params": {...}}}`. Kullanıcı metni ön yüzde i18n ile üretilir.
- ID'ler UUIDv7 (TEXT); zamanlar UTC, ISO 8601.
- Dış servisler bir `Protocol` adaptörü arkasında. Testler ağa çıkmaz: sahte adaptör veya kaydedilmiş cassette.
- Türkçe metin normalizasyonu tek yerde: `shared/text.py` (İ/ı doğru katlanır); `title_norm` gibi kolonlar buradan üretilir.
- `except Exception: pass` yok; yakalanan her hata loglanır veya işaretlenir.

**Ön yüz**
- `features/<ad>/` dikey dilim. Sunucu durumu yalnızca TanStack Query'de; API çağrıları yalnızca üretilmiş istemciyle (`src/api/`, elle düzenlenmez).
- Tüm kullanıcı metinleri i18n anahtarı; `tr` ve `en` birlikte eklenir.
- Sabit renk/ölçü yok: tasarım tokenları CSS değişkenleri olarak kullanılır.
- Platforma özgü her şey `lib/platform/` (`tauri.ts` / `browser.ts`) üzerinden.
- Uzun listeler sanallaştırılır (hedef: 2000+ satır akıcı).

**Genel**
- Kod, yorumlar, commit mesajları, README ve ADR'ler **İngilizce**. Benimle **Türkçe** yazış.
- Conventional Commits. Bir görev = bir branch (`task/<no>-<kısa-ad>`) = bir PR.
- Geliştirme makinesi Windows: yollar `pathlib` / `node:path` ile; bash'e özgü betik yazma (betikler Python veya Node); `.gitattributes` ile satır sonları sabit.

## Komutlar (kök `package.json` betikleri — Görev 1 bunları kurar, hep çalışır tut)

- `pnpm setup` — bağımlılıkları kurar (uv sync + pnpm install)
- `pnpm dev` — arka uç + web arayüzü (tarayıcı modu)
- `pnpm dev:desktop` — Tauri ile masaüstü
- `pnpm check` — iki tarafta lint + tip kontrolü + test (CI ile aynı)
- `pnpm gen:api` — OpenAPI'den TS istemcisini üretir
- `pnpm e2e` — Playwright testleri

## Her görevde iş akışı

1. `docs/progress.md`'ye bak; bağımlı görev bitmediyse dur ve söyle.
2. `docs/plan.md`'den görevi ve **Kabul** kriterini oku; UI işiyse `docs/design/` içindeki ilgili ekranı incele.
3. Önce plan sun (değişecek dosyalar, yaklaşım, testler, riskler, açık sorular) ve onayımı bekle. Belirsizlikte varsayım yapma, sor.
4. Onaydan sonra: önce kabul kriterini kodlayan testler, sonra kod.
5. `pnpm check` yeşil olmadan görev bitmiş sayılmaz. Testi geçirmek için testi zayıflatma.
6. Bitince: kabul kriterinin karşılandığını komut + çıktı ile göster, `docs/progress.md`'yi güncelle, commit at, PR açıklaması taslağı yaz (ne, neden, nasıl test edildi, yeni bağımlılık lisansları).
7. Görev kapsamını aşma. Fark ettiğin ek işleri `docs/progress.md` → "Sonraya" bölümüne yaz.

## Yapma

- Ağa çıkan test, gerçek API anahtarı, büyük ikili dosya commit'i (test PDF'leri küçük ve kendin üretilmiş olsun).
- Migration'sız şema değişikliği.
- Plan dışı büyük refactor veya yeni mimari bileşen (önce sor).
