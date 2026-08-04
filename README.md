# YDS Calisma Uygulamasi

Kisisel kullanim icin YDS calisma araci. Sunucu/derleme gerektirmez; saf
HTML + CSS + JS (ES modules). iPhone'da Safari'den ana ekrana eklenince
tam ekran, native hissi veren bir PWA olarak calisir ve tamamen cevrimdisi
kullanilabilir.

## Icindekiler
1. [Mevcut veri durumu](#mevcut-veri-durumu)
2. [Kurulum sirasi (scriptler)](#kurulum-sirasi-scriptler)
3. [Yeni PDF ekleme](#yeni-pdf-ekleme)
4. [Yerel olarak calistirma](#yerel-olarak-calistirma)
5. [GitHub Pages'e yukleme](#github-pagese-yukleme)
6. [iPhone'da ana ekrana ekleme](#iphoneda-ana-ekrana-ekleme)
7. [Veri yedekleme](#veri-yedekleme)
8. [Proje yapisi](#proje-yapisi)
9. [Bilinen sinirlamalar](#bilinen-sinirlamalar)

---

## Mevcut veri durumu

`tools/parse.py`, `kaynak/` klasorundeki 17 gercek YDS kitapcigini (2013
sonbahar - 2021 sonbahar) isleyip `data/questions/` altina JSON olarak
cikardi:

```
17 oturum x 80 soru = 1360 soru
  - 1360/1360 sorunun 5 sikki eksiksiz
  - 1360/1360 sorunun cevabi cevap anahtariyla eslesti
  - 0 supheli kayit (data/review-needed.json bos)
```

Tip dagilimi (gercek YDS yapisiyla birebir ortusuyor):

| Tip | Soru sayisi |
|---|---|
| reading (okuma) | 340 |
| vocabulary (sozcuk/ifade tamamlama) | 272 |
| cloze (parca - bosluk doldurma) | 170 |
| sentence_completion (cumle tamamlama) | 170 |
| dialogue (diyalog tamamlama) | 85 |
| irrelevant_sentence (akisi bozan cumle) | 85 |
| restatement (anlamca en yakin cumle) | 68 |
| paragraph_completion (parca tamamlama) | 68 |
| translation_en_tr | 51 |
| translation_tr_en | 51 |

Not: Saglanan 23 PDF'den 6 tanesi ("ingilizce09042023.pdf",
"ingilizce_tsk_*.pdf" vb.) gercek sinav kitapcigi degil, her soru
grubundan sadece 1 ornek gosterip cevabini da acikca yazan bir
tanitim/ornek soru dokumaniydi (cevap anahtari sayfasi da yoktu). Bu
dosyalar `kaynak/` klasorune alinmadi; ayristirici zaten cevap anahtari
bulamadigi herhangi bir dosyayi otomatik atlar ve sebebini raporda yazar.

`explanation` (soru aciklamalari) ve `data/dictionary.json` (kelime
sozlugu) henuz doldurulmadi -- bunlar Anthropic API anahtari gerektirir
ve tek seferlik, sizin calistirmaniz gereken adimlardir (asagida).

---

## Kurulum sirasi (scriptler)

Python 3.10+ gerekir. Sadece hazirlik asamasinda calisir; uygulamanin
kendisi Python'a ihtiyac duymaz.

```powershell
# 1) Bagimliliklar
pip install pdfplumber

# 2) PDF'leri JSON'a cikar (kaynak/ klasorundeki tum PDF'ler icin)
python tools/parse.py
# Tek bir dosyayi test etmek icin: python tools/parse.py 2019-1

# 3) Kelime frekans analizi (API gerekmez, tum sorulari tarar)
python tools/vocab.py

# 4) (Opsiyonel ama onerilir) Aciklama ve sozluk uretimi -- API anahtari gerekir
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python tools/explain.py          # her sorunun aciklama+celdirici analizini uretir
python tools/vocab.py --dictionary   # kelimelerin Turkce karsiligini/ornegini uretir
```

- `explain.py` ve `vocab.py --dictionary` **kaldigi yerden devam eder**:
  zaten dolu olan `explanation` / sozluk kayitlarini atlar. Kesintiye
  ugrarsa tekrar calistirmaniz yeterli.
- Ikisi de sonucu ilgili JSON dosyasina gomer; uygulama calisirken bir
  daha API'ye ihtiyac duymaz, tamamen cevrimdisi calisir.
- `explain.py` sadece bir dosyayi islemek icin: `python tools/explain.py 2019-1`
- Test amacli az sayida soru islemek icin: `python tools/explain.py --limit 20`

`parse.py` her calistirildiginda son adimda `data/questions/index.json`
ve `data/questions/by-type/*.json` dosyalarini da yeniden uretir (uygulamanin
tip bazinda tembel yukleme yapabilmesi icin). `vocab.py`/`explain.py`
calistirdiktan sonra bu index'i yenilemek isterseniz `parse.py`'i tekrar
calistirmaniz yeterli (var olan JSON'lari bozmaz, sadece index/by-type'i
yeniden derler).

---

## Yeni PDF ekleme

1. ÖSYM'nin "Çıkmış Sorular" bolumunden YDS/YÖKDİL soru kitapciklarini indirin.
   Cevap anahtari PDF icinde gomulu geliyorsa (2013-2021 kitapciklarinin
   cogunda oyle) ayrica cevap anahtari PDF'i gerekmez.
2. Dosyayi `kaynak/YIL-DONEM.pdf` kalibinda adlandirin, ornekler:
   - `kaynak/2022-ilkbahar.pdf`
   - `kaynak/2022-1.pdf` (yil icinde birden fazla oturum varsa 1/2/3)
3. Eger cevap anahtari ayri bir PDF ise `kaynak/YIL-DONEM-soru.pdf` ve
   `kaynak/YIL-DONEM-cevap.pdf` seklinde iki dosya olarak da koyabilirsiniz;
   parse.py her ikisini de dener (once ayni PDF icinde arar, yoksa
   `-cevap.pdf` esiyle eslesen dosyaya bakar).
4. `python tools/parse.py` calistirin, terminal ciktisindaki raporu okuyun:
   - Cikarilan soru sayisi 80'in altindaysa veya "Suphe" satiri 0 degilse
     `data/review-needed.json` dosyasini acip hangi sorularin elle
     kontrol edilmesi gerektigine bakin.
   - Rapor asla sessizce gecmez: eksik/supheli her sey ya konsola ya da
     review-needed.json'a yazilir.

---

## Yerel olarak calistirma

Derleme adimi yok; herhangi bir statik dosya sunucusuyla calisir.
Service worker'in dogru calismasi icin `file://` degil, bir HTTP sunucusu
uzerinden acmaniz gerekir:

```powershell
# Python ile (herhangi bir klasorden yds-app icinde calistirin)
python -m http.server 8000
# Tarayicida: http://localhost:8000/
```

veya VS Code'daki "Live Server" eklentisi gibi herhangi bir statik sunucu.

---

## GitHub Pages'e yukleme

```powershell
cd yds-app
git init
git add .
git commit -m "YDS calisma uygulamasi"
git branch -M main
git remote add origin https://github.com/<kullanici-adi>/<repo-adi>.git
git push -u origin main
```

Sonra GitHub reponuzda: **Settings > Pages > Source: Deploy from a branch
> Branch: main / (root)** secip kaydedin. Birkac dakika icinde
`https://<kullanici-adi>.github.io/<repo-adi>/` adresinde yayinda olur.

> Not: `kaynak/*.pdf` dosyalari `.gitignore` ile haric tutulur (telif
> nedeniyle repo'ya girmez). Sadece uretilen `data/` JSON'lari yuklenir.

---

## iPhone'da ana ekrana ekleme

1. Yayinlanan adresi (GitHub Pages linki ya da yerel agdaki adresi)
   **Safari**'de acin (Chrome/baska tarayicida PWA ozellikleri calismaz).
2. Alt paylas menusunden **"Ana Ekrana Ekle"** secenegini kullanin.
3. Ana ekrandaki simgeden acinca adres cubugu olmadan, tam ekran, native
   bir uygulama gibi calisir.
4. Ilk acilista tum veri (sorular, sozluk, uygulama dosyalari) service
   worker tarafindan cihaza indirilir; sonrasinda ucak modunda da calisir.

---

## Veri yedekleme

Tum ilerleme (cozulen sorular, SRS zamanlamasi, kaydedilen kelimeler,
istatistikler) sadece bu cihazin tarayicisinda (`localStorage`) tutulur.
iOS zaman zaman site verisini temizleyebildigi icin **Ayarlar** sekmesinden
duzenli olarak:

- **"Ilerlemeyi disa aktar (JSON)"** ile bir yedek dosyasi indirin.
- Veri kaybi durumunda **"Ilerlemeyi ice aktar (JSON)"** ile geri yukleyin.

---

## Proje yapisi

```
yds-app/
  kaynak/                 PDF'ler (git'e girmez)
  tools/
    parse.py              PDF -> JSON ayristirici
    explain.py            Anthropic API ile aciklama uretimi
    vocab.py               Kelime frekansi + (API ile) sozluk
    common_words.py       En sik ~700 Ingilizce kelime (gurultu filtresi)
    make_icons.py          PWA ikonlarini uretir
  index.html
  css/styles.css
  js/
    app.js                Ana orkestrator (yonlendirme, ekranlar)
    quiz.js               Test motoru (soru render, cevap, geri bildirim)
    dictionary.js         Kelimeye dokunma + bottom sheet
    storage.js            localStorage katmani, export/import
    srs.js                SM-2 turevi aralikli tekrar
    stats.js              Analiz/istatistik hesaplamalari
  data/
    questions/
      {yil-donem}.json    Her oturumun ham cikisi (deneme modu icin)
      index.json          Oturum/tip ozet indeksi
      by-type/{tip}.json  Tum yillar birlesik, tip bazinda (tembel yukleme)
    dictionary.json       Kelime -> {translation, partOfSpeech, example}
    vocab-frequency.json  Kelime frekans siralamasi
    review-needed.json    parse.py'in supheli buldugu kayitlar
  manifest.webmanifest
  sw.js
  icons/
```

---

## Bilinen sinirlamalar

- `explanation` ve `data/dictionary.json` API anahtari olmadan bos gelir;
  uygulama bu durumda "Bu soru icin henuz aciklama uretilmedi" / "Sozluk
  kaydi yok" gibi mesajlar gosterir, hata vermez. `tools/explain.py` ve
  `tools/vocab.py --dictionary` calistirilinca dolar.
- "Tek tip calisma" ve "Zayif yonum" modlari varsayilan olarak 20-30
  soruluk bir oturum baslatir (tum havuzu tek seferde degil); istenirse
  `js/app.js` icindeki `startTypeStudy(type, count)` cagrisindaki sayi
  degistirilebilir.
- Kelime lemmatizasyonu (hem `tools/vocab.py` hem `js/dictionary.js`)
  kural tabanli basit bir yaklasimdir, ağır bir NLP kutuphanesi
  kullanilmaz; nadir duzensiz fiillerde kucuk sapmalar olabilir.
