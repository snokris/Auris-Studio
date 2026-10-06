# Magyar hangkarakter-próba — 2026-10-06

Ez a helyi meghallgatási kör az egynarrátoros magyar felolvasásra készült.
Nem változtatja meg az Auris Studio alapértelmezett motorját vagy beállításait.
Az alábbi WAV-fájlok az `audio_cache` alatt vannak, ezért az Obsidianban ezen
a gépen lejátszhatók, de a Git-repóval **nem** kerülnek át másik gépre.

## Próbaszöveg, rögzített sorrendben

1. „A reggeli fény lassan végigkúszott a szoba falán. Odakint csendesen esett az eső.”
2. „Ősszel a sűrű fűben tűnődve ült a fiú, miközben Győr fölött hűvös szél fújt.”
3. „1932. március 5-én 12 ember érkezett a faluba. A 932. oldalon találták meg a választ.”
4. „A jegy 3500 Ft volt, a vonat 7.30-kor indult. A következő járat 7:45-kor érkezik.”
5. „Vajon visszatér még?”
6. „Megérkezik a vonat este 7:30-kor?”
7. „Végre megérkeztél! Már azt hittem, soha többé nem látlak.”
8. „A szék üres maradt mellette. Halkan becsukta a könyvet, és sokáig nem szólt.”

Mindegyik modell ugyanazt a szöveget kapta. A 3., 4. és 6. példán az Auris
Studio meglévő magyar, TTS-barát számnormalizálását használtuk: például
„ezer kilencszáz harminckettő”, „kilencszáz harminckettedik”, „háromezer
ötszáz forint” és „hét óra harminc perckor”. A számkiejtést így is füllel
kell ellenőrizni, mert a modell a helyes szövegből is hibázhat.

## Meghallgatható felvételek

Minden összefűzött felvétel a fenti nyolc szöveget tartalmazza, 0,8 másodperc
szünettel. A hangszínen és a hangmagasságon utólag nem módosítottunk.

| Motor és hang | Összefűzött próba |
|---|---|
| Jelenlegi Higgs TTS 3 / MLX | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-higgs/all-8.wav) |
| MOSS-TTS Local 1.5 / MLX, 4 bit | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-moss/all-8.wav) |
| Supertonic 3, M1 | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-supertonic/samples/M1-all-8.wav) |
| Supertonic 3, F1 | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-supertonic/samples/F1-all-8.wav) |
| Piper, Imre | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-piper/samples/imre-all-8.wav) |
| Piper, Anna | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-piper/samples/anna-all-8.wav) |
| Piper, Berta | [8 mondat](../reader/audio_cache/benchmarks/voice-candidates-20261006-piper/samples/berta-all-8.wav) |

Az egyes mondatok külön WAV-ként is megtalálhatók ugyanitt (`01.wav`–`08.wav`,
a Supertonic és Piper esetében hangnévvel előtagolva). A Supertonic további
nyolc beépített hangjáról egy-egy rövid, első mondatos előnézet készült:
`M2`–`M5`, illetve `F2`–`F5`.

## Futási körülmények és első mérések

- Higgs: az alkalmazás jelenlegi hibrid MLX-útvonala, meglévő magyar narrátori
  referenciával, 123-as generálási seed. A nyolc hang készítése a betöltés
  után kb. **21,5 s** volt; az első modellbetöltés kb. 6,2 s.
- MOSS: `mlx-community/MOSS-TTS-Local-Transformer-v1.5-4bit` és
  `mlx-community/MOSS-Audio-Tokenizer-v2-bf16`, `language="Hungarian"`, ugyanaz
  a helyi narrátori referencia, 123-as seed. A hét, már letöltött modellel
  készült hang együtt kb. **17,6 s** alatt generálódott; az ötödik, első
  mintának az idejébe a dekóder egyszeri letöltése is beleesett.
- Supertonic: `supertonic==1.3.1`, beépített M1/F1 stílus, `lang="hu"`,
  8 lépés, 1,0 sebesség. A nyolc hang M1-gyel kb. **10,6 s**, F1-gyel kb.
  **9,5 s** alatt készült a modell letöltése/betöltése után.
- Piper: `piper-tts==1.8.0`, három hivatalos `hu_HU` közepes minőségű hang,
  CPU-futtatás. A nyolc hang hangkarakterenként kb. **0,6–0,9 s** alatt készült
  a modellbetöltés után. A macOS ARM-csomag ismert eSpeak-adatútvonalhibáját
  rövid, ideiglenes szimbolikus hivatkozással kerültük meg; az Auris kódja nem
  változott.

Ezek egyetlen helyi, nem szabványos futás idői, eltérő kimeneti hanghosszal;
nem tekinthetők végleges sebességi rangsornak. A természetes magyar kiejtés,
hangsúly, érzelem és kérdő hanglejtés minőségéről a meghallgatás dönt.

## Meghallgatási döntés

A felhasználó szerint egyik alternatíva sem közelíti meg a jelenlegi
Higgs/MLX természetes magyar felolvasását. A kipróbált MOSS Local 1.5 / 4 bites
MLX-változat különösen érthetetlen, nem hat magyar felolvasásnak. A Piper
sebessége és a Supertonic választható hangjai ezt a minőségi különbséget nem
ellensúlyozzák. **A Higgs/MLX marad az alkalmazás motorja; az alternatívákat
nem integráljuk.**

A MOSS-nál az MLX feldolgozó forrása alapján a `Hungarian` címke bekerült a
generálási prompt `Language` mezőjébe. Nem látszik egyszerűen elhagyott
nyelvi beállítás; a jelenlegi eredmény ugyanakkor csak a fenti kvantált
Local-változatra és erre a referenciahangra vonatkozik, nem bizonyítja, hogy
a MOSS minden változata alkalmatlan magyarra.

Források: [Supertonic dokumentáció](https://github.com/supertone-oss-archive/supertonic-py/blob/main/docs/index.md),
[MOSS-TTS MLX használat](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/tts/models/moss_tts/README.md),
[Piper magyar hangok](https://github.com/rhasspy/piper/blob/master/VOICES.md),
[Piper macOS útvonalhiba](https://github.com/OHF-Voice/piper1-gpl/issues/272).
