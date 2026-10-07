# Auris Studio — lokális hangoskönyvkészítő

Teljesen **lokális, ingyenes hangoskönyvkészítő**: EPUB-, PDF- vagy TXT-könyvből felolvasott hangoskönyvet készít (MP3/WAV + felirat), internetkapcsolat és API-kulcsok nélkül. A cél a **minél élethűbb, emberibb magyar felolvasás egyetlen narrátorhanggal** — automatikus nyelvfelismerés, magyar fejezetdetektálás, magyar számnévolvasás és hangklónozás magyar referenciahangból.

Ez a repó a [mp3pintyo/Auris](https://github.com/mp3pintyo/Auris) forkja, amely maga is az eredeti [nikhilprasanth/Auris](https://github.com/nikhilprasanth/Auris) projektre épül. Az Auris Studio a Higgs TTS 3 motort Apple Silicon-támogatással, magyar szövegkezeléssel és teljes exportfolyamattal egészíti ki. Windows- és Linux-telepítéshez a mp3pintyo-repó útmutatója az irányadó.

## Képernyőképek

Apple Silicon backend: [Higgs TTS 3 + MLX hibrid integráció és mérések](docs/higgs-mlx-apple-silicon.md).

### Library
![Library](assets/library.png)

### Reader
![Reader](assets/reader.png)

### Voice Studio
![Voice Studio](assets/voice_studio.png)

### Settings
![Settings](assets/settings.png)

## Telepítés macOS-en (Apple Silicon)

Előfeltétel a [Homebrew](https://brew.sh), utána:

```bash
brew install python@3.12 ffmpeg git
git clone https://github.com/snokris/Auris-Studio.git
cd Auris-Studio
python3.12 -m venv reader/.venv
bash reader/setup.sh
```

Indítás:

```bash
bash reader/run.sh
```

Ezután a böngészőben: **http://127.0.0.1:7860**

Az installer Apple Siliconon külön `.mlx_runtime` környezetet készít. Első
Higgs-indításkor az MLX modell és a codec a Hugging Face cache-be töltődik;
helyi snapshot is választható a Settingsben. A Backend maradhat **Auto**
értéken: M-szérián MLX-et, más platformon a Transformers útvonalat választja.

## Használat röviden

1. **Library** — EPUB/PDF/TXT importálása; a magyar nyelvet és a fejezethatárokat magától felismeri, a felismert fejezetek pedig import után szerkeszthetők.
2. **Reader** — lejátszás bármely mondattól; a fejezet hangja előre is legenerálható.
3. **Settings → Narrator voice library** — magyar próbamondatból több szintetikus hangjelölt generálható és a meghallgatott jelölt saját néven menthető. Referencia-WAV (3–10 másodperc, egy beszélő) és pontos átirat is menthető. A referenciahangnál külön mezőbe kerül a WAV-ban elhangzó pontos szöveg és a próbaként felolvastatni kívánt szöveg; a hang mentés előtt előnézetben kipróbálható. A két hangtípus külön listában és külön `reader/data/voices/synthetic/`, illetve `reader/data/voices/reference/` mappában él. A négy régi jellemző (nem, korjelleg, hangfekvés, akcentus) a meghallgatott hangok szerkeszthető címkéje és a mentett listák működő szűrője; a Higgsnek nem adnak nem létező, garantált hangtervezési parancsot. A hangok átnevezhetők, átiratuk és WAV-juk/jelöltjük cserélhető, törölhetők, valamint `.aurisvoice` fájlba exportálhatók és visszatölthetők.
4. **Könyv → Voice Studio** — a könyvhöz kizárólag a Settingsben mentett szintetikus vagy referenciahang választható. Az előnézeti szöveg itt szerkeszthető, alaphelyzetbe állítható és a könyvhöz menthető; a Preview gomb lejátszás közben Stopra vált. A felolvasás és az export ugyanazt a rögzített hangprofilt használja; mentett hang nélkül új hang nem generálódik.
5. **Export** — a felső sávból nyíló panelen (`E` billentyű) az aktuális vagy kiválasztott fejezetek WAV/MP3 hanggal és SRT felirattal, `all`, `2-6` vagy `1,3,7-10` formában. MP3-hoz ffmpeg szükséges; M4B-export jelenleg nincs.

A böngészős **Docs** menü részletes, lépésről lépésre követhető útmutatót ad a hangtárhoz, a könyvenkénti hangválasztáshoz, a magyar felolvasáshoz, az Apple Silicon/MLX backendhez, a lejátszáshoz, az exporthoz és a hibaelhárításhoz. A Docs a futó alkalmazásban a `/docs` címen érhető el; a felület szövege a [reader/templates/docs.html](reader/templates/docs.html) fájlban él.

## Miben más az Auris Studio?

### Apple Silicon (MPS)

A Higgs natív MLX backenden használja a Metal GPU-t. A Transformers kompatibilitási útvonal MPS-en a Higgs natív bfloat16 formátumát használja; hiba esetére az `AURIS_STUDIO_HIGGS_MPS_DTYPE=fp32` kapcsolóval kényszeríthető float32-re.

### Egy narrátorhang, élethűen

Az Auris Studio teljes egészében **egynarrátoros felolvasásra** van hangolva: egyetlen, minél emberibb narrátorhang olvassa a teljes könyvet. Szintetikus hangot a Higgs referencia nélkül hoz létre; a kiválasztott rövid WAV és pontos szövege utána referenciahangként rögzül, így a könyv további mondataiban ugyanazt a hangkaraktert használja. Nem külön betanított modell keletkezik. A többszereplős narráció (karakterfelismerés, szereplőnkénti hangok) kódja megmaradt, de ki van kapcsolva; a kapcsoló az `app.py` `MULTI_VOICE_NARRATION` konstansa.

### Hangminőség

Az MLX hibrid útvonal a kijelentéseket kötegben generálja, a kérdéseket pedig külön referenciaággal készíti. A magyar kérdő hanglejtés minősége továbbra is fejlesztési feladat: az ER Sno hanggal több kérdésreferenciás, felhasználó által kedvezőnek ítélt **helyi próba** készült, de ez még nincs bekötve az alkalmazásba. A nyelvi célokat és a tesztpárokat a [kérdő hanglejtés követelménye](docs/hungarian-question-intonation.md), a kiválasztott próbamintát a [kísérleti napló](docs/question-prosody-2026-10-07.md) rögzíti.

### Természetes felolvasás

A valódi bekezdésvégeken a narrátor nagyobbat lélegzik: külön, hosszabb szünet szól (alap 0,85 mp, a Settingsben állítható), a lejátszásban, az exportban és a feliratban egyformán. Import közben a szöveg megtisztul a láthatatlan szeméttől (BOM, zero-width és vezérlőkarakterek, hibás Unicode), ami kiejtési hibákat és generálási bicsaklásokat okozna; az 500 karakternél hosszabb szövegegységek pedig tagmondathatáron feldarabolódnak, így a nagyon hosszú mondatok sem instabilak. Opcionálisan bekapcsolható a stúdiómasztering: finom EQ + kompresszor és kétmenetes EBU R128 hangosságillesztés (−19 LUFS) fejezetenként — hangoskönyv-szabvány, egyenletes hangerő.

### Magyar szövegkezelés

Magyar szövegnél a saját számnévolvasó fut le legelőször, még a motorok saját normalizálói előtt — azok ugyanis csak angolul, kínaiul és japánul tudnak, a `num2words` magyar tábláiban pedig a sorszámnevek száz fölött hibásak. A modul (`reader/core/hungarian_numbers.py`) kezeli a tő- és sorszámneveket, a dátumokat, a kötőjeles ragokat, az órákat, a százalékot, a hőfokot és a római számokat, és tudja, hogy csak az utolsó összetételi tag kapja a sorszámragot: a „932. esztendejében” így „kilencszázharminckettedik esztendejében”, nem pedig „kilencszázharminckettő”.

A fejezetfelismerés a kiírt sorszámneveket („Harmadik fejezet”) és a nevesített szakaszokat (Előszó, Epilógus) is fejezethatárnak veszi. A Higgs raw prompt módja szintén átmegy a normalizáláson, így ott sem maradnak számjegyek a felolvasásban.

### Fejezetszerkesztő és címnegyed

Import után a fejezetek átnevezhetők, kihagyhatók, törölhetők és összevonhatók. A címoldal és az impresszum alapból kimarad a felolvasásból, a mottó és a bevezető viszont bent marad, és az első fejezet előtti bevezető próza sem vész el.

### Exportfolyamat

Egyszerre egy export fut, Szünet / Folytatás / Leállítás vezérléssel; a szerver újraindítása után szüneteltetett állapotban tér vissza. Két folyamatjelző, mentett beállítások, könyvtárjelvény és élő állapotpont mutatja, hol tart. A fejezetek egyenként, elkészültükkor íródnak ki, így egy megszakadt export munkája nem vész el. Export közben a motorváltás, az újratöltés és a hangelőnézetek le vannak tiltva.

A kimenet lapos `exports/Szerző_-_Cím/` mappába kerül, és a fájlnevek is tartalmazzák a szerzőt — így a fájlok a mappájukból kiemelve is azonosíthatók:

```
exports/Dan_Brown_-_A_titkok_titka/
  Dan_Brown_-_A_titkok_titka_01_PROLÓGUS.mp3
  Dan_Brown_-_A_titkok_titka_01_PROLÓGUS.srt
```

Kérhető 1–4 összefűzött MP3 is a hozzájuk illeszkedő, újraidőzített felirattal. Az MP3-kódolás (VBR minőség vagy fix bitráta) és a beszédszünetek — mondatok, párbeszédfordulók, kihagyások, bekezdésvégek és fejezetek között — a Settingsben állíthatók. Minden MP3 ID3-címkéket kap: fejezetcím, szerző, könyvcím (album) és sorszám (track), így a fájlok a lejátszókban rendezetten jelennek meg.

### Hangcache és Voice Studio

A Beállítások hangcache-kártyája mutatja a cache méretét, kitakarítja az árva szegmenseket, és könyv törlésekor automatikusan söpör. A régi hangpresetek és a könyvekhez már feltöltött referenciahangok az első indításkor az új hangtárba másolódnak; az eredeti fájlok megmaradnak. Mentett hang módosításakor az azt használó könyvek szegmensei újragenerálódnak. Hang törlésekor az érintett könyveknél új narrátort kell választani.

## TTS-motor

Az Auris Studio kizárólag a **Higgs TTS 3 — 4B** modellt használja. A magyar támogatás, a zero-shot hangklónozás és az expresszív vezérlés miatt ez adta a legjobb egynarrátoros eredményt.

Apple Siliconon a Higgs natív MLX hibrid backendje az alapértelmezett. A
kijelentéseket legfeljebb ötös batchben készíti, a kérdéseket pedig külön, a
narrátor eredeti WAV-jából származtatott, belső hosszú szünetében rövidített
referenciával. A korábbi ötmondatos helyi mérésben a hibrid út közel hatszor
gyorsabb volt a Higgs/MPS soros útvonalánál. A kérdés utáni párbeszédjelölő
közbevetés („– kérdezte”, „he asked”) külön szegmensre kerül, hogy a kérdés
megőrizze kérdőjeles végét.

A kérdőmondatok hibájának diagnózisa, a magyar és angol akusztikai
összehasonlítás, valamint a helyi meghallgatható A/B minták:
[Kérdő mondatok — 2026-10-07](docs/question-prosody-2026-10-07.md).

\* A Higgs licence hangoskönyveknél jól látható „Boson AI Higgs Audio” forrásmegjelölést kér, a hangklónozáshoz pedig a beszélő hozzájárulása szükséges. Részletek a [hivatalos modellkártyán](https://huggingface.co/bosonai/higgs-tts-3-4b).

## Hasznos beállítások (Settings)

- `Audio format` → **MP3** (az exporthoz ffmpeg szükséges)
- `Higgs backend` → **Auto** (Apple Siliconon MLX hybrid)
- `MLX narration batch size` → **5**
- `Hybrid question reference` → **bekapcsolva**
- `MP3 mode` → VBR (a szegmensek közti csend így szinte semmibe nem kerül)
- `Spoken Pauses` → a mondat-, párbeszéd-, kihagyás-, bekezdés- és fejezetszünet füllel hangolható
- `Studio mastering` → kapcsold be, ha egyenletes, hangoskönyv-szabvány hangerőt szeretnél; hasonlítsd össze füllel

## Fejlesztés

A `main` ág a kiadott állapot, a `dev` a mindig működő, összefésült állapot; minden téma saját `feature/<téma>` ágon készül, és tesztelés után olvad vissza a `dev`-be.

Tesztek futtatása:

```bash
cd reader
.venv/bin/python -m unittest discover -s tests
```

A környezeti változók az `AURIS_STUDIO_` előtagot használják (`AURIS_STUDIO_HIGGS_MPS_DTYPE`, `AURIS_STUDIO_OFFLINE`, `AURIS_STUDIO_USE_LOCAL_WHEELS`, `AURIS_STUDIO_WHEELS_DIR`).

## Köszönet

Az eredeti Auris projektért köszönet **nikhilprasanth**-nak, a Higgs-integrációért és a magyar nyelvi támogatásért **mp3pintyo**-nak, a beszédmodellért pedig a [Boson AI](https://huggingface.co/bosonai) csapatának. Az Auris Studio licence az eredeti projektét követi (lásd `LICENSE`).
