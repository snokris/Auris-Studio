# Magyar Higgs mérés Apple Siliconon

Első upstream-átvételi kör, 2026-10-03. A kiejtési szabályokat ez a kör nem módosítja.

## Mi változott?

- Higgs: a narrátor referenciájának kódjai a worker memóriájában maradnak, legfeljebb 16 fájlváltozathoz. Modell-/worker-újraindításkor kiürülnek. A modell belső API-ját ellenőrizzük; ha nincs támogatás, a korábbi nyers hangos út marad.
- A rövid referencia egyszer elkészített ismétlése újrahasználható az `audio_cache/higgs_refs/` könyvtárból. A származtatott WAV ugyanolyan privát, mint az eredeti; a Git kizárja. Ezek a lemezfájlok a közös hangcache részei, automatikus lemezes takarítás még nincs.
- Mindkét motor új generálási cache-kulcsa megkülönbözteti az eszközt, számformátumot, normalizálóverziót és referenciafájl-változatot (abszolút út, méret, mtime és ctime). Ez fájlmetaadat-alapú azonosság, nem tartalmi hash. Higgsnél a beállított modellforrás is szerepel.
- Megmarad a Higgs MPS/bfloat16 és az OmniVoice MPS/float32 alapértéke, valamint a megszakítás utáni Higgs-helyreállítás.
- A DB-ben már késznek jelölt könyvrészleteket nem invalidáljuk: azok továbbra is a korábbi hangot játsszák le. Az új motorcache nem teljes DB-migráció. Új változat vizsgálatához újragenerálás vagy az alábbi mérőeszköz kell.

## Biztonságos A/B próba

Előbb várd meg az aktív könyvgenerálás végét, majd állítsd le az Auris szervert. A mérőprogram külön modellt tölt be; ne versenyezzen a futó appal a memóriáért. A `--confirm-idle` a te megerősítésed, nem automatikus GPU-ellenőrzés.

A repo gyökeréből, a referenciaút és átirat behelyettesítésével:

```bash
reader/.venv/bin/python reader/scripts/benchmark_higgs.py --reference "/abszolut/privat/referencia.wav" --reference-text "A referenciahang pontos átirata." --reference-cache off --output reader/audio_cache/benchmarks/higgs-off-01 --confirm-idle
reader/.venv/bin/python reader/scripts/benchmark_higgs.py --reference "/abszolut/privat/referencia.wav" --reference-text "A referenciahang pontos átirata." --reference-cache on --output reader/audio_cache/benchmarks/higgs-on-01 --confirm-idle
```

Meglévő könyvnél biztonságosabb a könyvazonosító: így a privát útvonal és átirat nem jelenik meg a parancssorban. Például a Siló jelenlegi azonosítója `1`:

```bash
reader/.venv/bin/python reader/scripts/benchmark_higgs.py --book-id 1 --reference-cache off --output reader/audio_cache/benchmarks/higgs-off-01 --confirm-idle
reader/.venv/bin/python reader/scripts/benchmark_higgs.py --book-id 1 --reference-cache on --output reader/audio_cache/benchmarks/higgs-on-01 --confirm-idle
```

Mindkét futás ugyanazt az öt saját magyar mondatot generálja kétszer, azonos 123-as maggal, magyar normalizálással, az aktuális Higgs-beállításokkal. A kész beszédhang cache-ét mindkét esetben megkerüli. Az `off` csak a referenciakód-cache-t kapcsolja ki; az előkészített referenciafájl újrahasznosítása mindkét futásban működik. A kapcsoló csak a mérőfolyamatra és gyermekére érvényes, a mentett appbeállításokat nem írja át.

A kimenet privát WAV-okat és `results.json` fájlt tartalmaz: betöltési idő, mondatonként teljes generálási idő, hanghossz, RTF, első kérés jelölése, modell/device/dtype, seed, beszélt promptok, corpus- és Git-verzió, referencia és átirat SHA-256. Meglévő kimeneti mappát nem ír felül. A fix seed nem garantál bitazonos MPS-eredményt; ismételj fordított futási sorrenddel is, új kimeneti nevekkel.

Az RTF a generálási idő / hanghossz: kisebb érték gyorsabb. Az első kérés codec-betöltést és bemelegítést is tartalmazhat; külön kezeld a későbbi soroktól. A worker WAV-kiírása és a szülőbe visszaolvasás benne van az időben, a benchmark saját WAV-másolata nincs. Ez nem streaming elsőhang-késleltetés.

Hallgatáskor figyeld: mondatkezdetek, hosszú magánhangzók, számok/dátumok, rövidítések, mondatvégek és a narrátor azonossága. Az ismert normalizálási hibákat ez a kör még nem javítja. Gyorsulást és hangminőség-változatlanságot csak valódi Mac-es A/B után állíthatunk.

Ugyanez a corpus OmniVoice-szal is elkészíthető, ugyanabból a könyvhivatkozásból, a végső hangcache megkerülésével:

```bash
reader/.venv/bin/python reader/scripts/benchmark_omnivoice.py --book-id 1 --output reader/audio_cache/benchmarks/omnivoice-01 --confirm-idle
```

2026-10-05-én a corpus v2 a Siló narrátorával OmniVoice-on is elkészült. A motor MPS/float32 módban futott, 16 lépéssel. Modellbetöltés: 8,49 s; az öt kérés átlaga 7,23 s, az első hangprofil-előkészítése utáni négy kérés átlaga 6,18 s. Ezek az adatok egyetlen futásból származnak, ezért nem tekintendők végleges teljesítményértékelésnek. A privát eredmény a Gitből kizárt `reader/audio_cache/benchmarks/omnivoice-20261005-02/` mappában található. A corpus v2 ötödik eleme már az önálló kérdés; az első négy szöveg változatlan a Higgs v1 méréshez képest.

## Ellenőrzés

### Első M5 Pro mérés — 2026-10-05

A Siló mentett narrátorhangjával, MPS/bfloat16 módban lefutott a cache ki/be próba és egy fordított sorrendű kontroll. Az első teljes körben a cache nélküli átlag 11,39 s (RTF 1,549), a cache-es 12,25 s (RTF 1,644) volt; ezt erősen torzította az eltérő betöltési/bemelegedési állapot. Az azonos ötmondatos első ismétlés 13,42 s, illetve 12,47 s átlagot adott. A fordított kontrollban a cache-es átlag 12,96 s (RTF 1,751), a cache nélküli 12,72 s (RTF 1,718) lett. Mind a 15 összehasonlítható WAV-pár bájtszinten azonos volt.

A meghallgatás három problémát tárt fel. Az `1932.` normalizált bemenete helyes volt (`ezerkilencszázharminckettő`), de a Higgs hibásan artikulálta a hosszú összetett számnevet. A jelenlegi normalizáló a `Ft` rövidítést és a ponttal írt `7.30-kor` időpontot nem oldotta fel, így a worker `Ft`, illetve `hét.harminckor` szöveget kapott. Ezek a következő magyar normalizáló-port kötelező regressziós esetei. A corpus v1 kérdésmintája három mondatot küldött egy kérésben, miközben a valódi egynarrátoros szegmentáló a kérdést önállóan adja át; a corpus v2 ezért a kérdést a kérés végén tartja. A v1 kérdéshanglejtése nem használható az alkalmazás viselkedésének megítélésére.

Következtetés: a cache ebben a mintában nem változtatja meg a hangot, de az M5 Pro teljes generálási idejében nem mutatott megismételhető gyorsulást. A referencia kódolása nem a fő szűk keresztmetszet; a következő sebességkört a token-generálás/MPS útvonalán kell keresni. A funkció biztonságos gyorsítótárként megmarad, de erre a mérésre nem alapozunk gyorsulási ígéretet. A nyers eredmény és a privát WAV-ok a Git által kizárt `reader/audio_cache/benchmarks/higgs-*-20261005-*` mappákban vannak.

```bash
cd reader
.venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

A célzott tesztek a cache-találatot, fájlváltozást, LRU-korlátot, modellszeparációt, hibakezelést, API-visszaesést, stabil előkészített referenciát, a szülő–worker kérést és a mérőciklust vizsgálják, valódi modellbetöltés nélkül. Valódi MPS-sebesség- és hallgatási próba még hátravan.
