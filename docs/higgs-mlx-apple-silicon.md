# Higgs TTS 3 + MLX — Apple Silicon hibrid integráció

Dátum: 2026-10-05. Ág: `feature/omnivoice-hungarian-prosody`.

## Döntés röviden

Az OmniVoice maradhat gyors vázlatmotor, de a természetes magyar egynarrátoros
felolvasás elsődleges motorja a Higgs TTS 3 natív MLX futtatással. Ez ugyanazt
a Higgs-modellcsaládot használja, amely hallásra eddig jobb volt, miközben az
Apple Silicon GPU-t közvetlenül használja.

Az elfogadott hibrid változat az alkalmazás normál lejátszási, előnézeti,
fejezetgenerálási és exportútvonalán is működik. Az Auto backend Apple
Siliconon MLX-et, más platformon Transformerst választ.

## Miért nem további OmniVoice-hangolás?

- Az OmniVoice klónozási utasításai a hivatalos felületen életkorra, nemre,
  hangmagasságra, suttogásra, valamint angol/kínai akcentusokra korlátozódnak.
  Nincs általános magyar fonéma- vagy mondathanglejtés-vezérlés.
- A hivatalos útmutató 3–10 másodperces, azonos nyelvű, pontosan átírt
  referenciahangot ajánl; a hosszabb minta ronthatja a klónozást.
- A mondatonkénti, kontextus nélküli generálás ismert prozódiai korlát. A
  korábbi 16/24/32 lépéses próbák sebességet változtattak, de a hallható
  magyar hangsúlyozási problémát nem oldották meg.
- A Higgs hivatalos modellkártyája a magyart a 85 kiemelten ellenőrzött nyelv
  között sorolja fel. A modell saját összehasonlításában kérdéseknél és
  összetett mondatoknál is megelőzi az OmniVoice-ot.

Források: [OmniVoice](https://github.com/k2-fsa/OmniVoice),
[OmniVoice tippek](https://github.com/k2-fsa/OmniVoice/blob/master/docs/tips.md),
[mondatkontextus-probléma](https://github.com/k2-fsa/OmniVoice/issues/241),
[Higgs TTS 3 modellkártya](https://huggingface.co/bosonai/higgs-tts-3-4b),
[MLX-Audio Higgs dokumentáció](https://github.com/Blaizzy/mlx-audio/blob/main/docs/models/tts/higgs_audio_v3.md).

## Helyi M5 Pro mérés

Azonos öt magyar tesztmondat, azonos referencia és fix seed mellett:

| Útvonal | Modellbetöltés | 5 generálás | Kimeneti hang | Összesített RTF | Régi Higgshez képest |
|---|---:|---:|---:|---:|---:|
| jelenlegi Higgs/MPS | 14,16 s | 64,78 s | 37,0 s körül | 1,75 | 1,00× |
| Higgs/MLX, soros | 2,83 s | 29,10 s | 33,52 s | 0,87 | 2,23× |
| Higgs/MLX, soros, rövidített referencia | 2,83 s körül | 24,82 s | 31,44 s | 0,79 | 2,61× |
| Higgs/MLX, ötös batch | 2,83 s | 9,25 s | 32,68 s | 0,28 | 7,00× |

Az MLX csúcsmemória 11,3–11,5 GB volt. A batch adat áteresztőképesség: öt
független mondat egyszerre készül el, ezért nem azonos az egyetlen mondat
válaszidejével. A batch hanghossza és mintavétele eltérhet a soros futástól,
tehát külön hallgatási ellenőrzést igényel.

A próba parancsa a `reader/scripts/benchmark_higgs_mlx.py`. A külön MLX
környezet és a helyi modellnézet Gitből ki van zárva; a riport nem tárolja a
privát referencia elérési útját vagy szövegét, csak ellenőrző hash-eket.

## Referenciahang

A helyi referencia tiszta, nem klippel és zajszűrést nem igényel. Viszont
nyugodt, lassú kijelentő beszédet tartalmaz, így önmagában nem tanít erős
kérdő hanglejtést vagy nagy érzelmi tartományt.

Az eredeti fájl változatlan maradt. Készült egy kizárólag helyi, 24 kHz-es
mono próba, amelyből csak a leghosszabb belső csend 660 milliszekunduma került
ki; nincs rajta denoise, EQ, kompresszió, hangmagasság- vagy tempóváltoztatás.
Ennek hasznosságáról csak az A/B meghallgatás dönthet.

A természetes kérdések javításához a legjobb következő referencia egy külön,
ugyanazzal a beszélővel készült 5–10 másodperces magyar felvétel, benne egy
természetesen elmondott kijelentéssel és kérdéssel, szó szerinti átirattal.
Mesterségesen felhúzott mondatvég kevésbé megbízható, mint a valódi előadás.

## Alternatívák, ha az MLX-Higgs sem elég

1. **MOSS-TTS Local Transformer v1.5 MLX** — hivatalos magyar támogatás,
   hangklónozás, IPA és írásjel-alapú prozódia; Apple Siliconon ez a legerősebb
   következő jelölt. Nagyobb helyi modell és külön integráció szükséges.
2. **F5-TTS Hungarian** — kicsi közösségi magyar modell, de kevés független
   minőségi bizonyíték és korlátozott érzelemvezérlés.
3. **ZONOS2/Metal** — kísérleti magyar klónozás és érzelemvezérlés; jelenleg
   nagyobb integrációs és stabilitási kockázat.

Az MLX-Higgs az alkalmazás elsődleges Apple Silicon backendje. A MOSS-TTS csak
akkor indokolt külön A/B ágként, ha egy későbbi meghallgatás új minőségi hibát
mutat.

## Második meghallgatási kör: hibrid út

A felhasználói A/B döntés szerint a rövidített referencia adta a legjobb
kérdő hanglejtést, míg a batch futás minden más mondattípusnál volt a
legtermészetesebb. A kettő technikailag keverhető, mert nem két külön modell,
hanem ugyanannak a Higgs–MLX motornak két generálási útja:

- a kijelentések az eredeti referenciával, batchben készülnek;
- a kérdőjellel végződő mondatok külön, a rövidített referenciával készülnek;
- a kimenetek az eredeti mondatsorrendben kerülnek vissza.

Az ötmondatos helyi hibrid próba kijelentés-batche 9,48 másodperc, a külön
kérdés 1,44 másodperc volt. A 10,92 másodperces generálási összidő csak
1,90 másodperccel lassabb a teljes C batchnél, és közel hatszor gyorsabb a
jelenlegi Higgs/MPS soros útjánál.

Ugyanebben a körben javult a Higgs magyar számkiejtési bemenete:

- a hosszú évszámok és sorszámok beszédbarát egységekre tagolódnak;
- a ponttal írt, ragos időpont is „óra–perc” alakra bővül;
- az `Ft` és `HUF` rövidítés kimondott „forint” alakra bővül;
- a normalizálási cache verziója nőtt, ezért régi hibás hang nem maradhat
  észrevétlenül a gyorsítótárban.

A normál magyar szöveg-normalizálás helyesírási alakjai nem változtak; a
tagolás csak a Higgs akusztikai promptjában él.

## Alkalmazás-integráció

- A `core/higgs_mlx_engine.py` tartja a cache-t, az ötös narration batch-eket,
  a kérdésfelismerést és a referencia biztonságos, származtatott változatát.
- A `core/higgs_mlx_worker.py` külön `.mlx_runtime` Python-folyamatban fut,
  ezért az MLX újabb függőségei nem ütköznek az OmniVoice környezetével.
- A referencia eredeti fájlja soha nem módosul. A származtatott 24 kHz-es mono
  WAV az `audio_cache/higgs_mlx_refs/` könyvtárban, tartalomazonosító alatt él.
- A narration batch mérete 1–8 között állítható; a bevizsgált alapérték 5.
- A 123-as seed reprodukálja az elfogadott A/B mintát.
- A teljes alkalmazáspróbában a modell 4,27 másodperc alatt betöltött, a normál
  preview és egy valós kérdés generálása is sikeres volt.
- A végleges teljes tesztkészlet 328/328 zöld.
