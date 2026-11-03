---
description: Aşama planındaki bir görevi standart iş akışıyla uygula
argument-hint: <görev no, ör. 6b>
---

Görev: $ARGUMENTS

1. `docs/plan.md` içinde "$ARGUMENTS ·" ile başlayan görevi bul. Tanımını ve **Kabul** kriterini aynen alıntıla.
2. `docs/progress.md`'yi oku. Bu görevin bağlı olduğu görevler bitmemişse dur ve hangilerinin eksik olduğunu söyle.
3. Planın ilgili bölümlerini (mimari, veri modeli, klasör yapısı, terminal entegrasyonu) oku. UI işiyse `docs/design/screens/` içindeki ilgili ekranları ve `docs/design/tokens.*` dosyasını incele.
4. Kod yazmadan önce bir uygulama planı sun:
   - değişecek / oluşturulacak dosyalar
   - yaklaşım ve önemli tasarım kararları
   - kabul kriterini doğrulayacak testler
   - riskler ve açık sorular
   Sonra onayımı bekle.
5. Onaydan sonra `task/$ARGUMENTS-<kısa-ad>` branch'ini aç. Önce testleri, sonra kodu yaz. `pnpm check` yeşil olana kadar devam et.
6. Bitince:
   - kabul kriterinin karşılandığını komut + çıktı ile göster
   - `docs/progress.md`'yi güncelle (durum, notlar, "Sonraya" maddeleri)
   - plandan sapma olduysa ADR yaz
   - Conventional Commit at ve PR açıklaması taslağı ver (ne, neden, nasıl test edildi, yeni bağımlılıkların lisansları)
