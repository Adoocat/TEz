# Claude Code — ilk oturum prompt'u

Aşağıdaki metni Claude Code'daki ilk oturumda olduğu gibi yapıştır.

---

Merhaba. Bu repo TEz projesi; proje kuralları `CLAUDE.md`'de. Bu oturumun amacı, Aşama 1'e başlamadan önce durumu netleştirmek ve risk denemesi S1'i yapmak. **Bu oturumda henüz uygulama kodu yazma.**

## Adım 1 — Okuma ve rapor (dosya değiştirme yok)

1. `docs/plan.md` ve `docs/design-prompt.md`'yi baştan sona oku. `docs/design/` klasörünün içeriğini listele ve ekran görüntülerini incele.
2. Bu makinede kurulu araçları ve sürümlerini komutla kontrol et: git, Python, uv, Node.js, pnpm, Rust (rustc, cargo), Tauri ön koşulları (Windows'ta WebView2 ve MSVC Build Tools). Eksik olanlar için Windows'ta kurulum komutlarını ver (winget tercih).
3. Bana kısa bir rapor ver:
   - (a) plan ile tasarım ekranları arasındaki çelişkiler veya eksikler
   - (b) Aşama 1 görev sırasındaki bağımlılık sorunları
   - (c) eksik araçlar ve kurulum komutları
   - (d) plandaki kütüphane/eklenti bilgilerinden güncel belgelerle çelişen var mı (özellikle Tauri v2 sidecar, single-instance ve deep-link eklentileri)
   - (e) bana sormak istediğin sorular

Raporu verdikten sonra dur ve yanıtımı bekle.

## Adım 2 — İlerleme dosyası (onayımdan sonra)

`docs/progress.md`'yi oluştur:
- tablo: `Görev | Durum | Branch/PR | Not`
- sırayla tüm Aşama 1 görevleri: S1, 1, 2, 3, 4, 5, 6, 6b, 7, 8, 9 … 23 — hepsi "bekliyor"
- altında "Sonraya" ve "Açık sorular" bölümleri

Repo'yu başlat (git init, `.gitignore`, `.gitattributes`, MIT `LICENSE`, kısa bir İngilizce `README.md`) ve ilk commit'i at.

## Adım 3 — Risk denemesi S1 (plan modunda başla)

S1'in tanımı ve kabul kriteri `docs/plan.md` → "0. Risk denemesi" bölümünde. Ek kurallar:

- Deneme kodu ana kod tabanına girmez: `spikes/s1-tauri-sidecar/` altında, atılabilir kod olarak.
- Şunları ölç ve kaydet: Python sidecar'ın PyInstaller onedir boyutu, kurulum paketinin boyutu, uygulamanın açılış süresi, sidecar'ın ilk `/health` yanıtına kadar geçen süre.
- Şunları doğrula:
  1. Tauri, sidecar'ı rastgele port + token ile başlatıyor; uygulama kapanınca süreç ölüyor (Görev Yöneticisi'nde yetim süreç kalmıyor).
  2. İkinci bir başlatma (`TEz.exe makale.pdf`) yeni pencere açmadan çalışan pencereye iletiliyor.
  3. Ayrı bir konsol programı (`tez`) PowerShell'de çıktı yazabiliyor ve pencere komutlarını masaüstü uygulamasına iletebiliyor.
  4. pdf.js, Tauri webview'inde (WebView2) 300 sayfalık bir PDF'i kabul edilebilir bellek ve kaydırmayla gösterebiliyor.
- Sonuçları `docs/adr/0001-desktop-shell-and-sidecar.md` olarak yaz (İngilizce): ne denendi, ölçümler, karar, açık riskler.
- Bir doğrulama başarısız olursa alternatifleri (ör. sidecar yerine farklı başlatma, `tez` için farklı kabuk) ADR'de karşılaştır ve bana karar için sun; kendi başına mimariyi değiştirme.

## Sonrası

S1 onaylandıktan sonra görevleri sırayla `/task <no>` komutuyla ilerleteceğiz: `/task 1`, `/task 2`, `/task 3` … Her görev ayrı branch ve ayrı PR.
