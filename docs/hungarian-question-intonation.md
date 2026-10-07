# Magyar kérdő hanglejtés — követelmény és tesztterv

Állapot: 2026-10-07. Kutatási jegyzet, nem beépített prozódiavezérlés.
A korábbi audit mintái nem mentek át a felhasználói meghallgatáson. Az ER Sno
hang későbbi, több kérdésreferenciás helyi próbájából a „Fogjak felmosót?”-ös
változatot választotta a felhasználó; ez az ER Sno helyi hangtárában már aktív.
A részletek a [kísérleti naplóban](question-prosody-2026-10-07.md) vannak.

## A nyelvi cél

A semleges, jelöletlen eldöntendő kérdés alapdallama emelkedő–eső.
Elegendően hosszú dallamhordozó szakasznál a csúcs jellemzően az utolsó
előtti szótag körül van, utána hallható esés következik. Előtte emelkedés
vagy plató is lehet. A korábbra kerülő csúcs sem szükségképpen hibás,
de a vizsgált hallgatók az utolsó előtti helyzetet ítélték a
legtermészetesebbnek. A „vajon” önmagában nem alakítja ezt kérdőszavas,
ereszkedő kérdéssé; az „-e” viszont alapesetben eső dallammal jár.
Az „ugye” helye és a beszélő szándéka is számít.
[Baditzné Pálvölgyi, 2021, 460–477.](https://real.mtak.hu/148871/)

Nem elég megszámolni a mondat összes szótagját: az utolsó főhangsúlytól
induló dallamhordozó szakasz hossza a lényeges. Egy szótagon a végső esés
gyakran elmarad; két szótagon az emelkedés és esés főként a másodikra
zsúfolódhat, és az esés gyenge vagy hiányzó lehet. A hang időtartama és
zöngéssége is korlátozza a megvalósulást. Ezért az „utolsó előtti szótagot
mindig megemeljük” nem általános szabály.
[Varga, 2002, különösen 307–310.](https://real.mtak.hu/54843/1/aling.49.2002.3-4.4.pdf)

A semleges kérdőszavas kérdésben általában a kérdőszó hangsúlya és az
ereszkedő folytatás adja a kérdő jelleget, rövid és hosszú mondatban is.
Választó kérdésnél a lehetőségek külön dallami egységek; visszakérdezésnél
és hiányos kérdésnél a helyzet más kontúrt indokolhat. A dallamcsúcs nem
azonos a magyar szó első szótagján levő szóhangsúllyal. A prozódiához
a hangmagasság mellett időzítés, intenzitás és tagolás is tartozik.
[Olaszy, 2002, Questions szakasz](https://www.magyarbeszed.hu/download/Acta_Linguistica_Hungarica_prosody_OG.pdf)

Következmény a tesztelésre: a felolvasási szándékot is rögzíteni kell.
Ugyanaz az írott mondat lehet semleges érdeklődés vagy hitetlenkedő
visszakérdezés. A kérdőjel ezt nem dönti el.

## Mi korlátozza jelenleg az Aurist?

A Higgs TTS 3 hivatalos leírása a `pitch_*`, `expressive_*` és `speed_*`
jeleket mondatszintűnek nevezi. Helyhez kötött jel a szünet és a hangeffektus.
Nincs dokumentált, szótaghoz rendelt F0-görbe vagy magyar kérdéstípus-parancs.
A `pitch_high` tehát nem azt jelenti, hogy a kérdő dallam megfelelő helyen
tetőzzön. Tetszőlegesen kitalált vezérlőszöveget sem szabad beadni.
[Higgs PROMPTING.md](https://huggingface.co/bosonai/higgs-tts-3-4b/blob/main/PROMPTING.md)

Helyi kódellenőrzés:

- A `reader/core/higgs_mlx_engine.py` kérdőjel alapján választ külön
  generálási útvonalat; kérdéstípust vagy főhangsúlyt nem határoz meg.
- A `reader/core/higgs_mlx_worker.py` szöveget, referencia-hangkódot,
  átiratot és mintavételezési paramétereket ad át.
- A telepített `mlx_audio/tts/models/higgs_audio_v3/prompt.py` a referencia
  és célszöveg sorrendjét állítja össze. Nincs külön szótagos dallamterv.
  A v3 `generate()` a `voice` és extra `kwargs` értékeket eldobja;
  egy új Python-paraméter önmagában nem teremtene új modellképességet.

A korábbi szünetrövidítés és seed-választás nem valósít meg nyelvi
dallamszabályt. A negyedenkénti F0-átlag és a hangfájl végétől mért
csúcstávolság sem helyettesíti a szótagok tényleges időbeli azonosítását.

## Célzott tesztkészlet

Az alábbiak saját tesztmondatok. A megadott szándék mellett kell őket
értékelni; nem minden lehetséges felolvasásukra vonatkozó előírások.
A szótagjelölést csak elemzéshez használjuk, nem adjuk át a TTS-nek.

| Eset | Szöveg | Ellenőrzés |
|---|---|---|
| Semleges eldöntendő, rövid | Eljönnek vasárnap? | A `va-sár-nap` zárásnál a `sár` körüli csúcs után esés. |
| Ugyanez hosszabban | Ha végeznek a költözéssel, eljönnek vasárnap? | Ugyanaz a záró kérdő egység; a hosszabb bevezetés ne tolja a csúcsot a `nap`-ra. |
| Korábbi hibás példa | Megérkezik a vonat este hét óra harminckor? | Semleges olvasatban a `har-minc-kor` zárásnál ne a `kor` legyen a végső emelkedés. |
| Egy szótag | Jó? | Természetes rövid kérdés, kötelező mesterséges visszaesés nélkül. |
| Két szótag | Elég? | Ne az első szótagra erőltessük a hosszabb kérdés sablonját. |
| Hosszú mondat, rövid végső fókusz | Amit tegnap elküldtem neked javításra, az így már JÓ? | A nagybetű csak a vizsgálati fókuszt jelzi; TTS-bemenetben `jó`. |
| Semleges kérdőszavas, rövid | Mikor érkeznek? | Kérdőszói hangsúly, természetes ereszkedés. |
| Ugyanez hosszabban | Mikor érkeznek meg a tegnap megrendelt könyvek? | A hosszúság ne váltson ki automatikus végemelést. |
| Kérdő partikula | Megérkezett-e a csomag? | Az eső lezárás önmagában nem hiba. |
| Választó kérdés | Reggel indulunk vagy este? | Két lehetőség elkülönítése; ne egyetlen általános kérdésgörbe. |
| Visszakérdezés | Mikor? | Kontextus: a választ nem hallottuk; ne a semleges kérdőszavas sablon döntsön. |
| Elbeszélő közbevetés | – Eljönnek vasárnap? – kérdezte halkan. | A kérdés és a közbevetés külön szegmens maradjon. |
| Kijelentő kontroll | Eljönnek vasárnap. | Ne kapjon kérdő dallamot, a narrátor hangja maradjon azonos. |

## Referenciakísérlet és elfogadási feltételek

Elsőként egy jogszerűen használható beszélő természetes kijelentő és
kérdő felvételével érdemes kontrollált referenciatesztet végezni.
A kérdésreferencia átvitelének működése **hipotézis**, nem meglévő funkció
vagy garantált megoldás. A referenciában ne ugyanaz a mondat legyen, mint
az értékelésben: az általánosítást is vizsgálni kell.

Ehhez elkészült a
[`reader/scripts/compare_higgs_question_references.py`](../reader/scripts/compare_higgs_question_references.py)
helyi próbaeszköz. A telepített MLX-Audio Higgs v3 már fogad több hangot
(`ref_audio_codes_list`) és hozzájuk tartozó több átiratot (`ref_texts`),
ezért az első összehasonlításhoz nem kell módosítani a csomagot. Az Auris
könyvfelolvasása továbbra is egy referenciát használ; a próba nem kapcsol
be új viselkedést az alkalmazásban. Az eszköz egy alap WAV-ot és egy vagy
több kérdés-WAV-ot vár, mindegyikhez külön pontos leirattal. Azonos bemenő
mondatot egyszer az alap, egyszer az alap és a természetes kérdések
együttes referenciájával állít elő.
A leiratok és bemeneti fájlnevek nem kerülnek a jelentésbe, csak a hashük;
a kimenet kizárólag a Git által kizárt `reader/audio_cache` alatt lehet.
Például a projekt gyökeréből, a Metal GPU-nak elegendő szabad memória mellett:

```sh
reader/.mlx_runtime/bin/python reader/scripts/compare_higgs_question_references.py \
  --base-audio /helyi/alap.wav \
  --base-text-file /helyi/alap.txt \
  --question-audio /helyi/kerdes-1.wav \
  --question-text-file /helyi/kerdes-1.txt \
  --question-audio /helyi/kerdes-2.wav \
  --question-text-file /helyi/kerdes-2.txt \
  --output reader/audio_cache/benchmarks/kerdes-tobb-referencia-01 \
  --limit 2
```

Az ER Sno hanggal a kontrollált több-referenciás próba lefutott. A mentett
alaphang és két ugyanazon hangú kérdésminta (a hosszabb „Megmondhatom nekik…”
és a „Fogjak felmosót?”) kombinációját választotta a felhasználó. Az
alkalmazásban az ER Sno hang kérdései már ezt a háromreferenciás útvonalat
használják; a helyi hangfájlok Gitből ki vannak zárva. A két kérdés-WAV
átiratát a fájlnév és a felhasználói meghallgatás alapján rögzítettük.

Azonos modell, seed és célszöveg mellett csak a referencia változzon;
azonos beszélő, összevethető felvételi minőség és pontos átirat szükséges.
Először a rövid/hosszú semleges pár, majd a rövid végső fókusz és a
kérdőszavas kontroll következzen. Ezután további szövegeken és több
rögzített seeddel kell ellenőrizni a megbízhatóságot, nem csak a legjobban
sikerült felvételt megtartani.

Az akusztikai ellenőrzés a szótagmagok tényleges, kézzel ellenőrzött
hangbeli helyét használja. Zöngétlen hangon és csendben nincs értékelhető
F0; oktávhibás becslés nem minősíthető dallamcsúcsnak. A relatív görbét,
az esés helyét, időzítést és hangminőséget együtt kell vizsgálni.
Az elfogadás feltétele a természetes magyar kérdés, változatlan
szövegtartalom és hangkarakter, robotos toldás nélkül, felhasználói
meghallgatással jóváhagyva. A generálási időt is rögzíteni kell.

Ha a kontrollált referencia sem hoz következetes javulást, ez a módszer
nem kerülhet alapértelmezésbe. Akkor a következő kutatási irány a valóban
vezérelhető prozódia vagy magyar kérdéseken történő modellillesztés
megvalósíthatósága, nem újabb véletlen seedek beépítése. Ebben a
felülvizsgálatban az alkalmazás hangjai és modellbeállításai nem változtak;
új hanggenerálás csak a Gitből kizárt kísérleti mappákban történt.
