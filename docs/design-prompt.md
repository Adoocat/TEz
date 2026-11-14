# TEz — Arayüz Design Prompt

Nov 2, 2026 · @Demirkan

## 1. Rol ve bağlam

Sen, araştırma ve veri yoğun masaüstü araçlarında deneyimli bir ürün tasarımcısısın. Görevin **TEz** adlı masaüstü uygulamasının arayüzünü tasarlamak: tasarım dili, bileşen seti ve aşağıda öncelik sırasıyla verilen ekranların yüksek doğruluklu (high-fidelity) maketleri.

**Ürün:** TEz, lisansüstü öğrencilerin tezleri için sistematik literatür taraması yapmasını sağlayan, yerel öncelikli (local-first) bir masaüstü uygulaması. Arama, eleme, okuma, not alma, içerik çıkarma ve tez yazımına hazırlığı tek bir iş akışında birleştirir. Tüm veri kullanıcının bilgisayarında durur; internet yalnızca akademik arama, meta veri ve PDF indirme için kullanılır.

**Kullanıcı:** Her daldan lisansüstü öğrenci ve araştırmacı: beşerî bilimler, hukuk, eğitim, sağlık, psikoloji, mühendislik… Hiçbir alan esas alınmaz (ADR 0019). İlk kullanıcı bir bilgisayar mühendisliği yüksek lisans öğrencisi, sonra lab arkadaşları ve başka alanlardan araştırmacılar. Teknik okuryazarlığı yüksek, klavyeyi seven, günde saatlerce aynı araçta çalışır. Kütüphanesinde 200 ile 2000+ kayıt olur (makale, kitap, kitap bölümü, tez). Örnek veri için tez konusu: LLM destekli kod inceleme (yalnızca maketler için).

**Giriş kapıları:** Uygulama yalnızca penceresinden kullanılmaz. Kurulumdan sonra kullanıcı terminalden (`tez .`, `tez makale.pdf`, `tez search …` — PowerShell, cmd, bash, zsh) ve dosya yöneticisinin sağ tık menüsündeki **"Open with TEz"** seçeneğinden de çalışır; tıpkı VS Code'daki `code .` ve "Open with Code" gibi. Arayüz, dışarıdan gelen bu içeriği akışı bölmeden karşılamalı (bkz. 4.6).

**Kullanıcının ana iş akışı (tasarım bu sırayı desteklemeli):**

1. Bir tarama projesi (review) açar: araştırma soruları, dahil etme / hariç tutma kriterleri.
2. Birden fazla akademik kaynakta tek sorguyla arar; sonuçlar tekilleştirilir, her arama kayda geçer.
3. Başlık-özet aşamasında hızla eler (Dahil / Hariç / Belki + gerekçe), sonra tam metin eler.
4. Dahil edilen makaleleri okur, vurgular, not alır; tabloları ve şekilleri çıkarır.
5. Literatür matrisini doldurur (satır = makale, sütun = yöntem, veri seti, metrik vb.); her hücre PDF'teki kaynak cümleye bağlıdır.
6. Yapay zekâdan öneri alır ama her öneriyi kaynağıyla görüp kendisi onaylar.
7. PRISMA diyagramını, kaynakçayı (BibTeX/RIS veya APA, MLA gibi biçimlendirilmiş) ve tez taslağını dışa aktarır.

**Üründe aklında tutman gereken üç vaat:** her bilgi kaynağına kadar izlenebilir; yapılan her eleme kararı gerekçesiyle kayıtlı; yapay zekâ önerir, kullanıcı karar verir.

## 2. Tasarım ilkeleri ve görsel dil

Hedef his: **sakin bir akademik çalışma masası** — yoğun ama ferah, saatlerce yorulmadan kullanılan bir araç. Pazarlama sitesi ya da genel bir SaaS paneli gibi görünmemeli; Linear, Zotero 7, Obsidian ve iyi bir IDE arasında bir yerde dur.

### İlkeler

1. **İçerik önce:** Ekranın çoğu makale metnine, listelere ve tablolara ayrılır; krom (kenarlıklar, başlıklar, gölgeler) en aza iner.
2. **Kaynak her zaman bir tık ötede:** Bir bilgi PDF'ten geliyorsa yanında küçük bir kaynak çipi (`Yazar 2024 · s.4`) bulunur; tıklanınca PDF o konumda açılır ve cümle kısa süre vurgulanır.
3. **Yapay zekâ içeriği ayrı görünür:** Onaylanmamış YZ önerisi hiçbir zaman kullanıcı verisi gibi görünmez; kendine ait renk, kesikli çerçeve ve "YZ önerisi" etiketi taşır.
4. **Klavye birinci sınıf:** Her ana eylemin kısayolu var ve arayüzde (düğme ipuçlarında, menülerde) görünür.
5. **Yoğunluk ayarlanabilir:** Varsayılan "kompakt"; ayarlardan "rahat" seçilebilir.
6. **Durum asla yalnız renkle anlatılmaz:** Renk + ikon + kısa etiket birlikte kullanılır.

### Tipografi

- **Arayüz:** Türkçe karakterleri (ğ, ı, İ, ş, ç, ö, ü) iyi destekleyen bir sans-serif (öneri: Inter veya IBM Plex Sans). Temel boyut 13 px, ikincil 12 px, başlıklar 15/18/22 px.
- **Okuma içeriği:** Özetler, notlar ve YZ cevapları için bir serif (öneri: Source Serif 4 veya IBM Plex Serif), 15 px, satır yüksekliği 1.6.
- **Teknik değerler:** DOI, atıf anahtarı, sorgu metni için monospace (öneri: JetBrains Mono veya IBM Plex Mono), 12 px.

### Renk

Nötr, hafif sıcak gri tonlar + tek bir ana vurgu rengi (öneri: derin mürekkep mavisi veya koyu camgöbeği). Gradyan, neon ve parlak gölge yok. Açık ve koyu tema eşit özenle tasarlanmalı; koyu tema saf siyah değil, koyu gri olmalı. Tüm renkler token olarak tanımlanmalı (`--color-bg`, `--color-surface`, `--color-text-muted`, `--color-accent` vb.).

**Semantik renkler** (her biri açık ve koyu temada):

| Anlam | Kullanıldığı yer | Renk yönü | İkon/etiket |
| --- | --- | --- | --- |
| Dahil | Eleme kararı | Yeşil | ✓ Dahil |
| Hariç | Eleme kararı | Kırmızı | ✕ Hariç + gerekçe kodu (E2) |
| Belki | Eleme kararı | Amber | ? Belki |
| Okunacak / Okunuyor / Okundu / Tekrar bakılacak | Okuma durumu | Gri / mavi / yeşil / mor | Küçük daire ikonları |
| YZ önerisi (onaysız) | Matris hücresi, özet, cevap | Mor/menekşe tonu, kesikli çerçeve | ✦ YZ önerisi |
| Doğrulanmış kaynak | Kaynak çipi | Vurgu rengi | Sayfa numaralı çip |
| Doğrulanamayan iddia | YZ cevabı | Turuncu dalgalı alt çizgi | ⚠ Kaynakta bulunamadı |
| Geri çekilmiş makale | Liste, detay, okuyucu | Koyu kırmızı şerit | Retracted rozeti |
| İşleniyor / hatalı | PDF durumu | Mavi animasyonlu / kırmızı | Dönen ikon / ünlem |

Vurgulama (highlight) renkleri: sarı, yeşil, mavi, pembe, mor — PDF üzerinde %35–40 opaklıkla okunabilir kalmalı.

### Ölçüler ve detay

- 4 px ızgara; ana boşluklar 8/12/16/24.
- Liste ve tablo satırı kompaktta 28 px, rahatta 36 px.
- Köşe yarıçapı 6 px (çipler 4 px, diyaloglar 10 px).
- İkonlar 16 px çizgi ikonlar, tutarlı tek aile (Lucide benzeri).
- Hareket: 120–180 ms, yalnızca yön ve bağlam için (panel açılışı, PDF'te konuma atlama vurgusu). Dekoratif animasyon yok.

## 3. Uygulama kabuğu ve gezinme

Tüm ekranlar aynı kabuğu paylaşır: solda dar bir gezinme şeridi, bağlama göre değişen bir kenar çubuğu, ana alan, isteğe bağlı sağ denetçi paneli ve altta durum çubuğu. Hedef pencere boyutu 1440×900; en küçük 1280×800'de de bozulmamalı.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ ● ● ●  [Review: LLM Kod İnceleme SLR ▾]     ⌘K  Ara veya komut…   ◐  ⚙ │  başlık çubuğu
├────┬───────────────┬──────────────────────────────────┬──────────────────┤
│ ⌕  │ KOLEKSİYONLAR │                                  │  DENETÇİ         │
│ ▤  │ ▾ Tez         │          ANA ALAN                │  (seçili makale) │
│ ☑  │   ▸ Yöntem    │   (liste / okuyucu / matris …)   │  meta veri       │
│ 📖 │ ETİKETLER     │                                  │  koleksiyonlar   │
│ ✎  │ AKILLI        │                                  │  notlar          │
│ ▦  │  koleksiyonlar│                                  │  atıflar         │
│ ✦  │               │                                  │                  │
│ ⚙  │               │                                  │                  │
├────┴───────────────┴──────────────────────────────────┴──────────────────┤
│ ⟳ 3 iş çalışıyor · 1 hatalı   │  1.284 makale   │  Ağ: bağlı             │  durum çubuğu
└──────────────────────────────────────────────────────────────────────────┘
```

### Bileşenler

- **Başlık çubuğu:** Özel (custom) pencere başlığı. Solda aktif review seçici (birden fazla tarama projesi olabilir; "Tüm kütüphane" seçeneği de var). Ortada komut paleti tetikleyicisi. Sağda tema ve ayarlar.
- **Gezinme şeridi (56 px):** İkon + üzerine gelince etiket. Sırasıyla: Arama, Kütüphane, Eleme, Okuyucu, Notlar, Matris, YZ Asistanı; en altta İşler ve Ayarlar. Eleme ikonunda bekleyen karar sayısı rozeti.
- **Bağlam kenar çubuğu (240 px, daraltılabilir):** Kütüphanede en üstte Gelen kutusu (dışarıdan açılan PDF'ler, sayı rozetli), koleksiyon ağacı (sürükle-bırak), etiketler (renkli nokta), akıllı koleksiyonlar (filtre ikonu). Aramada kayıtlı sorgular ve arama geçmişi. Notlarda not ağacı.
- **Ana alan:** Sekmeli olabilir (birden fazla PDF veya not aynı anda açık; tarayıcı sekmesi gibi).
- **Denetçi paneli (320–400 px, yeniden boyutlanabilir, kapatılabilir):** Seçili öğenin detayları. İçeriği bölüm 4'te.
- **Durum çubuğu:** Arka plan işleri (tıklanınca İşler paneli açılır), kütüphane sayısı, ağ durumu, son yedekleme zamanı.
- **Komut paleti (⌘K / Ctrl+K):** Makale arama (başlık, yazar, DOI), ekranlara gitme, eylemler ("Yeni not", "BibTeX dışa aktar", "Koyu temaya geç", "Eşdeğer terminal komutunu kopyala"). Sonuçlar türüne göre gruplanır, her satırda kısayol görünür.
- **Bildirimler:** Sağ altta küçük toast'lar; uzun süren işler toast yerine durum çubuğunda ilerler.

Panellerin genişlikleri ve açık/kapalı durumları kullanıcı başına hatırlanır; maketlerde panellerin daraltılmış hallerini de göster.

## 4. Öncelikli ekranlar (önce bunları tasarla)

Bu ekranlar ilk geliştirme aşamasında kodlanacak; en yüksek detay bunlarda olmalı.

### 4.1 Açılış ve ilk kurulum

**Amaç:** Kütüphane klasörü seçmek ve ilk tarama projesini (review) oluşturmak.

- **Karşılama:** "Yeni kütüphane oluştur" / "Var olan kütüphaneyi aç" / son açılan kütüphaneler listesi. Verinin yerel kaldığını tek cümleyle belirt.
- **Kurulum sihirbazı (4 adım):** (1) Kütüphane klasörü ve dil, (2) arama kaynakları için e-posta / API anahtarı (hepsi isteğe bağlı, "sonra" denebilir), (3) yapay zekâ: kapalı / yerel (Ollama) / bulut — varsayılan kapalı, (4) sistem entegrasyonu: "tez komutunu terminale ekle", "Open with TEz sağ tık menüsü", "PDF, BibTeX ve RIS dosyalarını ilişkilendir" onay kutuları (VS Code kurulumundaki gibi; işletim sistemine göre etiketler değişir).
- **Yeni review formu:** Başlık, yöntem (PRISMA 2020 / Kitchenham SLR / Sistematik haritalama), araştırma soruları (RQ1, RQ2… eklenebilir liste), dahil etme ve hariç tutma kriterleri (kod + açıklama, örn. E1 "İngilizce değil"). Kriterler sonradan düzenlenebilir.

### 4.2 Sistematik arama

**Amaç:** Tek sorguyla birden fazla kaynakta aramak, sonuçları tekilleştirilmiş görmek ve her aramayı yöntem bölümü için kayda geçirmek.

**Düzen:** Üstte sorgu alanı, altında filtreler ve kaynak seçimi; ortada sonuç listesi; sağda seçili sonucun denetçisi; kenar çubuğunda kayıtlı sorgular ve geçmiş.

- **Sorgu alanı:** Çok satırlı, monospace, boolean sözdizimi renklendirmesi (`AND`, `OR`, `NOT`, tırnaklı ifadeler, parantez). Yanında "Sorguyu kaydet" ve "Yeni makale uyarısı" anahtarı; ayrıca bu aramanın birebir tez search karşılığını panoya alan "Terminal komutunu kopyala" düğmesi.
- **Filtreler:** Yıl aralığı, yayın türü (dergi, konferans, ön baskı, kitap, kitap bölümü, tez), yalnızca açık erişim, dil.
- **Kaynak çipleri:** OpenAlex, Semantic Scholar, arXiv, Crossref, DBLP — her biri açılıp kapatılabilir. Liste zamanla büyür (PubMed, Europe PMC, DOAJ, ERIC, CORE, DergiPark adayları; ADR 0019); çip alanı 10+ kaynağa sığmalı. Arama sırasında her çip kendi durumunu gösterir: bekliyor, aranıyor (ilerleme), tamamlandı (sonuç sayısı), hız sınırında (geri sayım), hata (tekrar dene). Bir kaynağın hatası diğerlerini durdurmaz.
- **Kaynak başına sorgu:** Her çipin altında açılır bir alan: o kaynağa gönderilen çevrilmiş sorgu (düzenlenebilir). Bu, yöntem raporu için önemli.
- **Özet şeridi:** "5 kaynakta 1.912 kayıt · 487 tekrar · 1.425 benzersiz · 312'si zaten kütüphanede".
- **Sonuç listesi (sanallaştırılmış):** Her satırda başlık, ilk yazar + "vd.", yıl, mekân (venue), atıf sayısı, bulunduğu kaynakların mini rozetleri (örn. OA · S2 · arXiv), açık erişim PDF ikonu, "zaten kütüphanede" işareti. Tekrar olarak birleştirilmiş kayıtlarda "3 kayıt birleştirildi" ipucu; üzerine gelince hangi kayıtların ve neye göre (DOI / başlık benzerliği %) birleştiği görünür.
- **Toplu eylemler:** Seçilenleri "Review'a ekle" (eleme kuyruğuna girer), "Kütüphaneye ekle", "PDF'leri bul ve indir".
- **Arama geçmişi (ayrı sekme):** Tablo — tarih/saat, başlatan (arayüz / terminal), sorgu, kaynak, filtreler, bildirilen sonuç, alınan sonuç, durum. "Yöntem bölümü için dışa aktar" düğmesi.
- **Dosyadan içe aktar (API'si olmayan veritabanları için birinci sınıf yol):** Kullanıcı önce veritabanını listeden seçer (Google Scholar, JSTOR, Scopus, Web of Science, ScienceDirect, EBSCO, ProQuest, PsycINFO, HeinOnline, IEEE Xplore, ACM DL, TR Dizin, YÖK Tez (dışa aktarımı varsa), "Diğer…"), sonra o veritabanından indirdiği dosyayı (RIS, BibTeX, WoS düz metni, CSV) bırakır. Seçilen veritabanı için "Buradan nasıl dışa aktarılır" adım adım kısa rehber (ekran görüntüsüz, metin). Arama tarihi ve sorgu alanları; içe aktarma geçmişte ve PRISMA'da veritabanının adıyla görünür (ör. "JSTOR · 412 kayıt").
- **Kayıtlı harici arama:** Dosya yolundaki bir veritabanı araması (veritabanı + sorgu) kaydedilebilir ve kenar çubuğunda kayıtlı sorguların yanında görünür. "Siteyi aç" düğmesi siteyi tarayıcıda açar ve sorguyu panoya kopyalar. Aynı arama yeniden içe aktarılınca önizlemede "Son içe aktarmadan (12 Eki) beri 7 yeni kayıt" yazar; eleme kuyruğuna yalnız yeniler girer. Uzun süre yenilenmeyen aramada küçük bir hatırlatma ("YÖK Tez · son arama 32 gün önce").

### 4.3 Kütüphane (Explorer)

**Amaç:** 2000+ makaleyi düzenlemek, bulmak ve durumlarını görmek.

- **Araç çubuğu:** Görünüm seçici (Liste · Kart · Zaman çizelgesi · Atıf grafiği), arama kutusu (başlık, yazar, özet, not ve PDF metninde tam metin), filtre çipleri (yıl, okuma durumu, etiket, PDF var/yok, eleme kararı), sıralama, sütun seçici, yoğunluk.
- **Liste görünümü (varsayılan):** Yoğun, sanallaştırılmış tablo. Sütunlar: seçim kutusu, okuma durumu ikonu, başlık, yazarlar, yıl, mekân, etiketler (renkli noktalar), PDF durumu (yok / var / işleniyor / hatalı), eleme kararı, eklenme tarihi, atıf anahtarı. Sütunlar sürüklenip yeniden sıralanabilir ve gizlenebilir.
- **Kart görünümü:** Başlık, yazarlar, yıl, özetin ilk 3 satırı, etiketler, ilk sayfa küçük resmi.
- **Zaman çizelgesi görünümü:** Yıllara göre gruplanmış yatay şerit; her makale bir nokta veya kart.
- **Tam metin arama sonuçları:** Eşleşmenin geçtiği cümle, sayfa numarasıyla birlikte; tıklanınca okuyucu o sayfada açılır.
- **Toplu seçim:** Seçim yapılınca üstte bir eylem çubuğu belirir: koleksiyona ekle, etiketle, okuma durumunu değiştir, dışa aktar, çöp kutusuna taşı.
- **Sürükle-bırak:** Satırlar kenar çubuğundaki koleksiyonlara sürüklenebilir; PDF dosyası pencereye bırakılınca içe aktarma başlar.
- **Kenar çubuğu:** Koleksiyon ağacı (iç içe, sayı rozetli), etiketler, akıllı koleksiyonlar (örn. "2020 sonrası · okunmamış · yöntem: anket"), Çöp kutusu.

### 4.4 Makale denetçi paneli

Seçili makalenin her ekranda aynı görünen detay paneli. Yukarıdan aşağı:

- **Uyarı şeritleri (varsa):** Geri çekilmiş makale, düzeltme yayımlanmış, ön baskının yayımlanmış sürümü var.
- **Başlık ve künye:** Başlık (serif), yazarlar (tıklanabilir), yıl, mekân, DOI ve diğer tanımlayıcılar (kopyala düğmeli, monospace), atıf anahtarı (düzenlenebilir).
- **Hızlı eylemler:** PDF'i aç, okuma durumu seçici, etiket ekle, koleksiyon, yıldız/öncelik.
- **Sekmeler:** Özet · Notlar (sayılı) · Vurgular (sayılı) · Atıflar · Eleme geçmişi · Dosyalar.
- **Atıflar sekmesi:** "Kaynakları (42)" ve "Atıf yapanlar (118)"; kütüphanede olanlar işaretli; "Tümünü tarama listesine ekle" (kartopu tarama) düğmesi.
- **Eleme geçmişi:** Zaman sıralı kararlar (aşama, karar, gerekçe kodu, not, tarih) — değiştirilemez kayıt hissi vermeli.
- **Dosyalar:** PDF, sayfa sayısı, işleme durumu (metin çıkarıldı / OCR gerekti / hatalı + sebep), "Yeniden işle".

### 4.5 PDF okuyucu

**Amaç:** Odaklanmış okuma, vurgulama ve kaynağa geri dönüş.

**Düzen:** Sol kenarda sayfa küçük resimleri / bölüm ana hattı (Özet, Giriş, Yöntem…); ortada PDF; sağda okuma paneli. Üstte belge sekmeleri.

- **Araç çubuğu:** Sayfa göstergesi (12 / 34), yakınlaştırma, sayfa genişliğine sığdır, belge içi arama, vurgulama aracı, alan seçme aracı (tablo/şekil için), odak modu (tüm paneller gizlenir).
- **Metin seçimi araç kutusu:** Seçimin hemen üstünde küçük bir kutu: vurgu renkleri, "Not ekle", "Matris hücresine bağla", "Nota alıntıla", "Kopyala (atıflı)".
- **Vurgular:** PDF üzerinde yarı saydam; üzerine gelince notu görünür. Sağ paneldeki vurgu listesinde her öğe sayfa numarasıyla; tıklanınca PDF o konuma kayar ve vurgu kısa bir nabız animasyonuyla belirir.
- **Sağ okuma paneli sekmeleri:** Notlar · Vurgular · Çıkarılanlar (tablolar ve şekiller) · Kaynakça · Matris (bu makalenin matris satırı, hücre hücre).
- **Konuma atlama:** Uygulamanın herhangi bir yerinden gelen kaynak çipi okuyucuyu ilgili sayfa ve cümlede açar; cümle 2 saniye vurgulanır.
- **Taranmış PDF:** "Bu PDF metin içermiyor — OCR uygula" şeridi.

### 4.6 Dışarıdan açma: Open with TEz, terminal ve bağlantılar

**Amaç:** Dosya yöneticisinden, terminalden veya bir `tez://` bağlantısından gelen içeriği, kullanıcının o anki işini bölmeden karşılamak. İçerik nereden gelirse gelsin arayüzdeki tepki aynıdır.

**Giriş kapıları:** Sağ tık › Open with TEz (PDF, `.bib`, `.ris`, klasör) · terminalde `tez <yol>` · `tez://` bağlantısı (ör. bir nottan veya LaTeX yorumundan) · dosyayı uygulama simgesine ya da pencereye sürükleme.

**Tek PDF geldiğinde:**

- Uygulama kapalıysa açılır, açıksa öne gelir; yeni pencere açılmaz. PDF okuyucuda yeni sekmede açılır.
- Okuyucunun üstünde satır içi bir şerit (modal değil): "makale.pdf Gelen kutusuna eklendi · DOI bulundu, meta veri getiriliyor…" + \[Koleksiyona taşı\] \[Review'a ekle\] \[Geri al\]. Meta veri gelince şerit güncellenir.
- Meta veri bulunamazsa şerit "Meta veriyi tamamla" düğmesi gösterir; küçük bir form (başlık, yazarlar, yıl, DOI) denetçi panelinde açılır.
- PDF zaten kütüphanedeyse: "Bu PDF zaten kütüphanede — mevcut kayıt açıldı (Kim vd. 2024)". Hiçbir şey kopyalanmaz.

**Birden fazla PDF veya PDF dolu bir klasör geldiğinde:** İçe aktarma önizleme diyaloğu — dosya listesi (ad, sayfa, algılanan DOI, durum), tekrar olanlar işaretli ve varsayılan olarak seçili değil, hedef koleksiyon seçici, "alt klasörleri koleksiyon olarak koru" seçeneği, alt kısımda "37 dosya · 4 tekrar · 33 içe aktarılacak" özeti.

**Klasör bir TEz kütüphanesiyse:** "Bu klasör bir TEz kütüphanesi — açılsın mı? Şu anki kütüphane kapanacak." onayı; son açılanlar listesine eklenir.

**`.bib` veya `.ris` geldiğinde — içe aktarma sihirbazı:**

1. Özet: kayıt sayısı, tekrarlar, kütüphanede zaten olanlar.
2. Alan eşleme önizlemesi: ilk 5 kayıt tablo halinde, sorunlu alanlar işaretli.
3. **"Bunu bir arama kaydı olarak logla"** (varsayılan açık): veritabanı adı (IEEE Xplore, ACM DL, Scopus, Web of Science, diğer), arama tarihi, kullanılan sorgu metni. Bu kayıt arama geçmişinde ve PRISMA'da görünür.
4. Hedef: review ve/veya koleksiyon.

**Terminalden başlatılan işler:** Arayüz açıksa, `tez search` veya `tez add` gibi komutların ilerlemesi durum çubuğunda ve İşler panelinde "Terminal" rozetiyle canlı görünür; tamamlanınca küçük bir toast ("Terminalden yapılan arama tamamlandı · 412 sonuç" + \[Göster\]).

**Kopyalanabilir komutlar:** Arama ekranında ve dışa aktarma diyaloğunda "Terminal komutunu kopyala" düğmesi o işlemin birebir `tez` karşılığını panoya alır; kopyalanınca komut kısa bir önizlemede monospace olarak görünür.

**Terminal stil örneği (tek sayfa):** Terminal çıktısı uygulamanın uzantısıdır, aynı terimleri ve semantik renkleri kullanır. Şunları içeren tek sayfalık bir örnek hazırla: `tez --help` çıktısı (komut grupları, kısa açıklamalar), `tez search` sırasında kaynak başına ilerleme satırları (bekliyor / aranıyor / tamamlandı / hız sınırı / hata), sonuç özeti tablosu, hata mesajı biçimi (ne oldu + ne yapmalı). Renkler 16 renkli terminallerde de okunur olmalı; renk kapalıyken (`NO_COLOR`) anlam kaybolmamalı. Çıktı sistem diline göre Türkçe veya İngilizce.

## 5. Sonraki ekranlar

Bu ekranlar sonraki aşamalarda kodlanacak. Eleme ve literatür matrisi ürünün kalbi; onları da yüksek detayda tasarla, diğerlerinde ana düzen ve kritik bileşenler yeterli.

### 5.1 Review paneli

Aktif tarama projesinin ana sayfası: araştırma soruları, aşama ilerlemesi (Arama → Başlık-özet eleme → Tam metin eleme → Kalite değerlendirme → Veri çıkarma), her aşamada bekleyen sayı ve "devam et" düğmesi, küçük bir PRISMA özeti, son aramalar.

### 5.2 Eleme (screening) — yüksek detay

**Amaç:** Yüzlerce kaydı hızla ve tutarlı biçimde elemek; her kararın gerekçesi kayda geçsin.

- **Odak modu (varsayılan):** Ekranda bir seferde tek kayıt. Ortada büyük ve okunaklı: başlık (serif), yazarlar, yıl, mekân, özet. Özette kullanıcının tanımladığı anahtar kelimeler vurgulu (dahil etme terimleri yeşil, hariç tutma terimleri kırmızı alt çizgi).
- **Sağda kriter paneli:** Dahil etme ve hariç tutma kriterleri, her birinin kodu ve numaralı kısayolu (1–9). Hariç seçilince gerekçe zorunlu.
- **Karar çubuğu (altta, sabit):** Dahil (`I`), Hariç (`E` + gerekçe numarası), Belki (`M`), Atla (`→`; tıklanabilir "Atla" düğmesi de var), Geri al (`U`), not ekle (`N`). Düğmelerde kısayol harfi görünür. Elemede Space kullanılmaz; `J`/`K` kayıtlar arasında karar vermeden gezinir. Karar verilince kayıt hafifçe kayarak sonrakine geçer.
- **Üst çubuk:** Aşama seçici (Başlık-özet / Tam metin), ilerleme çubuğu ("214 / 1.425 · %15"), oturum sayacı ("bu oturumda 48 karar"), filtre (yalnızca "Belki"ler, yalnızca kararsızlar).
- **Tam metin aşaması:** Sol tarafta PDF okuyucu açılır; kriter paneli ve karar çubuğu aynı kalır. PDF'i yoksa "Tam metne erişilemedi" seçeneği (PRISMA'da ayrı sayılır).
- **Liste modu (alternatif):** Tablo halinde hızlı tarama; satırda tek tuşla karar; seçilen satırın özeti altta açılır.
- **İleriye dönük (ikinci değerlendirici):** İki kişi bağımsız elediğinde çakışan kararlar için "Çakışmalar" sekmesi ve her iki kararın yan yana görünümü. Şimdilik yalnızca yerini düşün.

### 5.3 Notlar

- Sol: not ağacı ve arama. Orta: Markdown düzenleyici (canlı önizleme veya WYSIWYG benzeri). Sağ: geri bağlantılar (bu nota bağlanan notlar ve makaleler).
- `[[` yazınca not/makale önerisi açılır. Makale ve sayfa bağlantıları çip olarak görünür (`Kim vd. 2024 · s.7`); tıklanınca okuyucu o konumda açılır.
- Okuyucudan "Nota alıntıla" ile gelen alıntı, kaynak çipiyle birlikte blok alıntı olarak eklenir.

### 5.4 Literatür matrisi — yüksek detay, ürünün en önemli ekranı

**Amaç:** Dahil edilen makaleleri ortak alanlarda karşılaştırmak; her hücre kanıta bağlı.

- **Izgara:** Elektronik tablo hissi. Satır = makale (sol sütun sabit: kısa künye + okuma durumu), sütun = kullanıcı tanımlı alan (Yöntem, Veri seti, Değerlendirme metriği, Bulgular, Kısıtlar…). Yatay ve dikey kaydırmada başlıklar sabit; 100+ satır × 15+ sütunda akıcı.
- **Sütun başlığı:** Ad, veri tipi ikonu (metin, sayı, seçenek, çoklu seçenek, evet/hayır), menü (düzenle, açıklama, sırala, filtrele, "YZ ile bu sütunu doldur"). Sütun açıklaması hem kullanıcıya not hem YZ'ye talimattır.
- **Hücre durumları (her biri net ayırt edilmeli):** boş; kullanıcı girdisi; kanıtlı kullanıcı girdisi (köşede küçük kaynak işareti); **onay bekleyen YZ önerisi** (mor ton, kesikli çerçeve, ✦ işareti — kesinlikle kalıcı veri gibi görünmemeli); onaylanmış YZ önerisi (normal hücre + küçük ✦ geçmiş işareti).
- **Hücre açılır paneli:** Hücreye tıklanınca: değer düzenleyici, bağlı kaynak cümle(ler) alıntı olarak + sayfa çipi + "PDF'te aç", YZ önerisiyse "Onayla · Düzenle ve onayla · Reddet" düğmeleri ve önerinin hangi modelden geldiği.
- **Öneri kuyruğu:** "YZ ile doldur" sonrası sağ panelde onay bekleyen öneriler listesi; klavyeyle hızlı gözden geçirme (`A` onayla, `R` reddet, `↓` sonraki), her birinde kaynak cümle görünür.
- **Araç çubuğu:** Sütun ekle, satırları filtrele (koleksiyon, etiket), gruplama (ör. yönteme göre), dışa aktar (CSV, Excel, Markdown), "Boşlukları göster" (YZ'nin araştırma boşluğu önerileri; bunlar da kaynaklı ve onaya tabi).

### 5.5 Çıkarılan içerik: tablolar ve şekiller

- **Tablo görüntüleyici:** Çıkarılan tablo, orijinal PDF bölgesinin küçük resmiyle yan yana (doğruluğu kontrol için). CSV/Excel dışa aktarma, hücre düzeltme.
- **Karşılaştırma görünümü:** Farklı makalelerden seçilen tablolar yan yana, senkron kaydırma.
- **Şekil galerisi:** Izgara; her kartta görsel, şekil etiketi ("Şekil 3"), açıklama (caption), makale ve sayfa. Dışa aktarırken kaynak bilgisi otomatik eklenir.

### 5.6 YZ asistanı

- Sohbet arayüzü; üstte kapsam seçici (tüm kütüphane / bu review / bir koleksiyon / seçili makaleler).
- Cevap metni serif; her iddianın sonunda kaynak çipleri. Çipin üzerine gelince alıntılanan cümle ve sayfa önizlemesi; tıklanınca PDF açılır.
- Kaynağı doğrulanamayan cümle turuncu dalgalı alt çizgi + "Kaynakta bulunamadı" ipucu.
- Cevap altında "Nota ekle" ve "Matrise öneri olarak gönder".
- **YZ kapalıyken:** Gezinmedeki ikon soluk; ekran, nasıl açılacağını anlatan sade bir boş durum gösterir. YZ'ye bağlı tüm düğmeler gizlenir, kırık görünmez.

### 5.7 PRISMA diyagramı

PRISMA 2020 akış diyagramı otomatik: Veritabanlarından bulunan (kaynak bazında) → tekrarlar çıkarıldı → başlık-özet elemesi → elenenler → tam metne erişim → erişilemeyenler → tam metin elemesi → gerekçeli hariç tutulanlar (gerekçe başına sayı) → dahil edilenler. Yan kolda "diğer yöntemlerle bulunanlar" (kartopu). Kutulardaki sayılar canlı; etiketler düzenlenebilir; SVG/PNG dışa aktarma. Akademik yayın görünümünde, siyah-beyaz baskıya uygun bir tema da olmalı.

### 5.8 Atıf grafiği

Kütüphanedeki makaleler arası atıf ağı: düğüm boyutu = kütüphane içi atıf sayısı, renk = küme, kenar = atıf yönü. Sağda seçili düğümün denetçisi. Filtreler: yıl aralığı, koleksiyon, yalnız dahil edilenler. Merkezi makaleler etiketli, diğerleri yakınlaşınca etiketlenir.

### 5.9 İşler paneli

Arka plan işlerinin listesi: başlatan (arayüz / terminal rozeti), tür (PDF indirme, metin çıkarma, OCR, tablo çıkarma, gömme), makale, ilerleme, süre, durum. Hatalı işler kırmızı, sebebi açıklayan tek satır ve "Tekrar dene" / "Atla". Bozuk PDF uygulamayı çökertmez; burada işaretli görünür.

### 5.10 Dışa aktarma ve tez köprüsü

- Kaynakça dışa aktarma diyaloğu: biçim (BibTeX, RIS veya biçimlendirilmiş kaynakça), kapsam (seçili, koleksiyon, review'da dahil edilenler), atıf anahtarı biçimi önizlemesi.
- Biçimlendirilmiş kaynakça: stil seçici (APA 7, MLA, Chicago, Vancouver, IEEE; aranabilir liste, sık kullanılanlar üstte; ileride enstitü tez stilleri), dil (Türkçe/İngilizce), canlı önizleme (ilk birkaç girdi), "Panoya kopyala" (Word'e biçimiyle yapışır) ve dosyaya kaydet.
- Taslak oluşturucu: makale notlarını ve matris satırlarını seçip sürükleyerek bölüm taslağı oluşturma; Markdown/Word önizleme.
- Geri çekilme kontrolü sonuç ekranı: sorunlu kaynakların listesi.

### 5.11 Ayarlar

Sol kategori listesi: Genel (dil, tema, yoğunluk), Kütüphane (konum, yedekleme ve geri yükleme), Kaynaklar (API anahtarları, e-posta, hız sınırı bilgisi), Yapay zekâ (kapalı/yerel/bulut, model, gizlilik açıklaması), PDF işleme (GROBID adresi, OCR), Kısayollar (düzenlenebilir liste), Sistem entegrasyonu (terminal komutu PATH'te mi, Open with TEz menüsü, dosya ilişkilendirme, tez:// bağlantıları — her biri durum göstergesi ve aç/kapat anahtarıyla; macOS'ta "tez komutunu PATH'e kur" düğmesi), Hakkında.

## 6. Durumlar, erişilebilirlik, klavye ve çok dillilik

### Her ekran için tasarlanacak durumlar

- **Boş durum:** Yeni kütüphane, boş koleksiyon, henüz eleme yok. Kısa açıklama + tek bir birincil eylem ("İlk aramanı yap", "PDF sürükle"). İllüstrasyon gerekirse sade ve tek renkli.
- **Yükleniyor:** Listelerde iskelet (skeleton) satırlar; uzun işler için ilerleme çubuğu. Ekranı kilitleyen tam sayfa spinner yok.
- **Kısmi hata:** Bir arama kaynağı hata verdi ama diğerleri sonuç getirdi; PDF'lerden biri işlenemedi. Hata yerinde, sakin bir dille ve bir eylemle ("Tekrar dene") gösterilir.
- **Çevrimdışı:** Arama ve indirme devre dışı, nedeni tek satırla açıklanır; okuma, eleme, not ve matris tamamen çalışır.
- **Büyük veri:** 2000+ satırlık kütüphane, 300 sayfalık PDF, 100×15 matris — maketlerden en az biri bu yoğunlukta olmalı.
- **YZ kapalı:** YZ'ye bağlı öğeler gizli; arayüzde boşluk veya kırık düğme kalmaz.

### Erişilebilirlik

- WCAG 2.2 AA kontrast (açık ve koyu temada), görünür odak halkası, en az 24×24 px tıklama alanı.
- Tüm akışlar yalnız klavyeyle tamamlanabilir; odak sırası mantıklı.
- Durumlar renk + ikon + metinle anlatılır (renk körlüğü için).
- "Hareketi azalt" sistem ayarına uyulur.

### Klavye kısayolları (arayüzde görünür olmalı)

| Bağlam | Kısayol | Eylem |
| --- | --- | --- |
| Genel | ⌘K / Ctrl+K | Komut paleti |
| Genel | ⌘1 … ⌘7 | Gezinmedeki ekranlar |
| Genel | ⌘F | Bu ekranda ara |
| Genel | ? | Kısayol listesi katmanı |
| Eleme | I · E · M | Dahil · Hariç · Belki |
| Eleme | 1–9 | Hariç tutma gerekçesi |
| Eleme | U · N · → | Geri al · Not · Atla (düğmesi de var) |
| Eleme | J · K | Sonraki · önceki kayıt (karar vermeden) |
| Okuyucu | H · ⇧N | Vurgula · Not ekle |
| Okuyucu | J · K | Sonraki · önceki sayfa |
| Liste | ↑ ↓ · Space · Enter | Gezin · Önizle · Aç |
| Matris / öneri kuyruğu | A · R | Öneriyi onayla · reddet |

Mac'te ⌘, Windows/Linux'ta Ctrl gösterilir.

### Çok dillilik (Türkçe ve İngilizce)

- Maketler **Türkçe** hazırlanmalı; aynı ekranların birinin İngilizce sürümü de gösterilmeli.
- Türkçe metinler genelde daha uzun: düğme ve sütun başlıkları taşmaya dayanıklı olmalı (kısaltma yerine esneyen genişlik, gerekirse ipucu).
- Büyük harf kullanılırsa Türkçe kurallarına uy (`i → İ`, `ı → I`); bölüm başlıklarında tamamı büyük harf yerine küçük-büyük harf (sentence case) tercih et.
- Tarih ve sayı biçimleri dile göre değişir: `2 Kas 2026` / `Nov 2, 2026`; `1.425` / `1,425`; `%15` / `15%`.
- Görsellerin içine metin gömme; tüm metinler çevrilebilir kalmalı.

## 7. Örnek veri, teslimatlar ve yapılmayacaklar

### Örnek veri

Maketlerde lorem ipsum kullanma; gerçekçi ama **kurgusal** veri üret (gerçek makaleymiş gibi künye uydurma, uydurma olduğu belli olsun yeter). Konu: LLM destekli kod inceleme.

- Başlıklar kısa ve çok uzun karışık (taşma davranışı görünsün); yazar adlarında Türkçe karakterler (Şahin, Güneş, Çelik, Yıldırım, Öztürk) ve yabancı adlar.
- Yıllar 2016–2026; mekânlar konferans, dergi ve ön baskı karışık (örn. ICSE, FSE, MSR, TSE, EMSE, arXiv).
- Uç durumlar: özeti olmayan kayıt, PDF'i olmayan kayıt, işlenemeyen PDF, geri çekilmiş bir makale, aynı çalışmanın ön baskı ve yayımlanmış sürümü.
- Örnek review: "LLM Destekli Kod İnceleme — SLR"; RQ1 "Hangi LLM teknikleri kod inceleme yorumu üretmede kullanılıyor?", RQ2 "Bu araçlar nasıl değerlendiriliyor?"; kriterler I1–I3, E1–E5.
- Örnek matris sütunları: Yaklaşım, Model, Veri seti, Programlama dili, Değerlendirme metriği, İnsan değerlendirmesi (evet/hayır), Temel bulgu, Kısıtlar.

### Beklenen teslimatlar (bu sırayla)

1. **Tasarım tokenları:** Açık ve koyu tema renkleri, tipografi ölçeği, boşluklar, köşe yarıçapları, gölgeler, z-katmanları — tablo veya JSON olarak, isimlendirmesi kodda kullanılabilir.
2. **Bileşen sayfası:** Düğmeler (birincil, ikincil, sessiz, tehlike), girişler, sorgu düzenleyici, çipler (kaynak, karar, okuma durumu, YZ önerisi, kaynak/sayfa), tablo satırı durumları, ağaç, sekmeler, paneller, açılır paneller, diyaloglar, toast, ilerleme, boş durum. Her biri varsayılan, üzerine gelme, odak, devre dışı ve seçili hâlleriyle.
3. **Uygulama kabuğu:** Paneller açık ve daraltılmış hâlleriyle.
4. **Bölüm 4 ekranları:** 4.1–4.6, açık ve koyu temada.
5. **Eleme ve literatür matrisi:** 5.2 ve 5.4 yüksek detayda; kritik etkileşimler ardışık kareler olarak — karar verip sonraki kayda geçiş, hücre kanıt paneli, YZ önerisini onaylama, kaynak çipinden PDF'te konuma atlama.
6. **Diğer ekranlar:** 5.1, 5.3, 5.5–5.11 orta detayda; tek sayfalık terminal stil örneği de dahil (4.6).
7. **Kısa gerekçe:** Her ekranın yanında 2–3 cümle — hangi kararı neden verdin. Belirsiz bir nokta için yaptığın varsayımı da burada yaz.

Tasarımı geliştiricinin React + TypeScript ile, Radix tabanlı erişilebilir bileşenlerle (shadcn/ui benzeri) kodlayacağını düşün: bileşen ve token adları tutarlı olsun, her ekran tekrar kullanılan bileşenlerden kurulsun.

### Yapılmayacaklar

- Gradyan, cam efekti (glassmorphism), neon renk, büyük dekoratif gölgeler.
- İçi boş KPI kartlarıyla dolu bir "dashboard" ana sayfası.
- Maskotlu veya sohbet balonu ağırlıklı bir YZ kişiliği; YZ bir araçtır, karakter değil.
- Onaylanmamış YZ içeriğini kullanıcı verisiyle aynı stilde göstermek.
- Kritik bilgiyi (kaynak, sayfa, gerekçe) yalnızca üzerine gelince görünen ipuçlarına saklamak.
- Her küçük eylem için modal pencere; mümkünse satır içi düzenleme.
- Gerçek servislerin logolarını kullanmak; kaynakları metin çipleriyle göster.
- Arayüzde emoji.
