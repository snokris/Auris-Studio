# Auris Studio

Helyben futó, **egynarrátoros hangoskönyv-olvasó és -készítő** magyar szövegekhez. EPUB-, PDF- és TXT-könyvet importál, a fejezeteket szerkeszthetővé teszi, felolvassa őket, majd WAV/MP3 hangot és SRT feliratot exportál. A cél a természetes magyar kiejtés és hanglejtés, valamint a gyors generálás Apple Silicon Macen.

A projekt a [mp3pintyo/Auris](https://github.com/mp3pintyo/Auris) forkja. A jelenlegi Auris Studio **Higgs TTS 3 — 4B** modellt használ; Apple Siliconon az MLX a fő útvonal. Nem tartalmazza az upstream összes, főleg Windowsra és többszereplős hangjátékra épülő funkcióját. A korábban kipróbált OmniVoice és VibeVoice nincs az alkalmazásban.

## Gyors kezdés Apple Silicon Macen

Előfeltétel: Homebrew, Python 3.12, Git és ffmpeg. Az alábbi telepítéshez és a Higgs-modell első letöltéséhez **internetkapcsolat kell**; a már telepített alkalmazás és letöltött modell ezután helyben fut, API-kulcs nélkül.

```bash
brew install python@3.12 ffmpeg git
git clone --branch dev https://github.com/snokris/Auris-Studio.git
cd Auris-Studio
python3.12 -m venv reader/.venv
bash reader/setup.sh
bash reader/run.sh
```

Nyisd meg a <http://127.0.0.1:7860> címet. Az indító terminálban a `Ctrl+C` leállítja a szervert. A modell első betöltése hosszabb lehet. A telepítő Apple Siliconon külön `reader/.mlx_runtime` környezetet is létrehoz; a **Settings → Higgs backend → Auto** itt az MLX-et választja. Más platformokon a Transformers-kompatibilitási útvonal érhető el, de a projekt elsődleges célplatformja az Apple Silicon.

> A `dev` a jelenleg fejlesztett, tesztelt ág; a `main` a kiadott állapot. Ha a legfrissebb itt leírt funkciókat szeretnéd, a `dev` ágat használd.

## Első könyv felolvasása

1. A **Library** oldalon importálj EPUB-, PDF- vagy TXT-fájlt. A felismert fejezetek utólag szerkeszthetők.
2. A **Settings → Narrator voice library** részben készíts és ments egy hangot. Szintetikus hangnál magyar próbaszövegből több jelöltet hallgathatsz meg; referenciahangnál tiszta, egybeszélős WAV és a felvétel **pontos átirata** kell. A próbaként felolvastatott szöveg külön mező, nem azonos a WAV átiratával.
3. Nyisd meg a könyv **Voice Studio** oldalát, válassz egy **mentett** hangot, próbáld ki saját szöveggel, majd mentsd a könyvhöz. Mentett hang kiválasztása nélkül a könyv hangja nem generálható.
4. A **Reader** bal alsó Play gombjával indul a felolvasás. Bekezdésre kattintva onnan folytatható; a fejezet hangja előre is generálható.
5. Az **Export → Scope** részen külön választható az aktuális fejezet (**This chapter**), a teljes könyv (**All chapters**) vagy néhány fejezet (**Selected chapters**, például `2-6` vagy `1,3,7-10`). Több fejezetnél az összefűzés kapcsolójával 1–4 WAV/MP3 fájl és hozzájuk illeszkedő SRT felirat kérhető; kikapcsolva fejezetenkénti fájlok készülnek. MP3-hoz ffmpeg kell, M4B-export jelenleg nincs.

A részletes, képernyőn követhető útmutató a futó alkalmazás **Docs** menüjében vagy a `/docs` címen található.

## Hangok, magyar szöveg és sebesség

- A négy hangjellemző — nem, korjelleg, hangfekvés, akcentus — **címke és szűrő**. Nem a Higgs hanggenerálását vezérli. A szintetikus jelöltek tényleges hangját meg kell hallgatni, és a megfelelőt névvel elmenteni. A mentett szintetikus és referenciahangok külön listában szerepelnek; szerkeszthetők, törölhetők, valamint `.aurisvoice` fájlba exportálhatók és onnan importálhatók.
- A magyar számnormalizálás a felolvasás előtt kezeli többek között a dátumokat, évszámokat, sorszámokat, időpontokat és pénzösszegeket. Ez szöveg-előkészítés, nem garancia a modell minden kiejtésére. A fejezetfelismerés és a hosszú mondatok tagolása szintén a magyar felolvasást segíti.
- Az MLX hibrid út a kijelentő szegmenseket kötegben készíti (alapérték: 5), a kérdéseket külön referenciaággal. A kérdés utáni „– kérdezte” jellegű közbevetés külön szegmensre kerül. A korábbi ötmondatos **helyi** mérésben ez az út közel hatszor gyorsabb volt a soros Higgs/MPS útnál; ez nem általános sebességgarancia. A kérdő hanglejtés sem tökéletes minden mondatnál.
- Az opcionális stúdiómasztering, a beszédszünetek és az MP3-kódolás a Settingsben állítható. A lejátszás és az export ugyanazt a könyvhöz mentett narrátorhangot használja.

### ER Sno kérdésreferenciái: csak ezen a gépen

A mostani kódban egy mentett hang mellé kérdésminták kapcsolhatók. Az ER Sno helyi hangtárában az alap-WAV mellett a jóváhagyott **„Megmondhatom nekik…”** és **„Fogjak felmosót?”** WAV szerepel; az MLX a kérdő mondatokat ezekkel együtt generálja. Kijelentéseknél és más hangoknál a korábbi útvonal marad. A részletes mérés és a bekötés a [kérdőmondat-naplóban](docs/question-prosody-2026-10-07.md) olvasható.

**Fontos:** a mentett hangtár, az ER Sno két extra WAV-ja és a hozzájuk tartozó `.questions.json` fájl helyi adat, nincs a Git-repóban. Egy új klónban a funkció kódja megvan, de az ER Sno-profil nem jelenik meg automatikusan. A `.aurisvoice` export jelenleg csak az alap-WAV-ot és átiratát viszi át; az extra kérdésfájlokat külön kell másolni. A saját hangfelvételeket csak megfelelő jogosultsággal használd.

## Fejlesztés és dokumentáció

A `main` a kiadott, a `dev` a tesztelt, összefésült fejlesztési ág; új feladat saját `feature/<téma>` ágon készül. Tesztek a projekt virtuális környezetével:

```bash
cd reader
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

További technikai leírás: [Higgs/MLX Apple Silicon](docs/higgs-mlx-apple-silicon.md), [magyar kérdő hanglejtés](docs/hungarian-question-intonation.md), [kérdőmondat-kísérletek](docs/question-prosody-2026-10-07.md). Az alkalmazás beállításaihoz kapcsolódó környezeti változók `AURIS_STUDIO_` előtagot használnak.

## Köszönet és licenc

Az eredeti Auris projektért **nikhilprasanth**-nak, a forkért és a korábbi magyar támogatásért **mp3pintyo**-nak, a Higgs beszédmodellért pedig a [Boson AI](https://huggingface.co/bosonai) csapatának köszönet. A projekt licence a [LICENSE](LICENSE) fájlban, a Higgs modell felhasználási feltételei a [hivatalos modellkártyán](https://huggingface.co/bosonai/higgs-tts-3-4b) találhatók; terjesztés előtt mindkettőt és a használt hangminták jogait ellenőrizni kell.
