# Kérdő mondatok: Higgs/MLX audit — 2026-10-07

## Aktuális eredmény

A felhasználó az audit és az utána készített seed-próbák bemutatott magyar
mintáit elutasította. A későbbi, ER Sno hanggal készült, több kérdésreferenciás
helyi próbák közül a „Fogjak felmosót?”-ös változatot választotta.
**Ez még nem beépített akusztikai javítás.** A szegmentálás programhibájának
javítása önmagában nem bizonyítja a hanglejtés helyességét.
Az új, kérdéstípusokat és rövid/hosszú dallamhordozó szakaszokat megkülönböztető
[nyelvészeti követelmény és tesztterv](hungarian-question-intonation.md)
váltja fel a pusztán mondatvégi hangmagasságot vizsgáló értékelést.

## Diagnózis

A magyar kérdések néha kijelentésként hangzottak; ugyanez angolul is
előfordult. Egy igazolt szegmentálási hibát és egy lehetséges akusztikai
hibaforrást azonosítottunk:

1. A „– Visszatérsz? – kérdezte.” és a „Are you coming?” he asked.
   gyakran egyetlen, ponttal végződő TTS-szegmens volt. A kérdés útvonala
   ezért el sem indult, a közbevetés pedig kijelentő lezárást kért.
2. A korábbi hibrid út egy rögzített seeddel maga generált egy
   „Vajon visszatér még?” kérdést, majd ezt használta minden további magyar
   kérdés referenciájaként. Ez a nem ellenőrzött minta a vizsgált helyi
   hangnál maga is ereszkedő dallamú volt.

## Források és döntés

A [Higgs TTS 3 hivatalos modellkártyája](https://huggingface.co/bosonai/higgs-tts-3-4b)
kérdésekre is közöl eredményeket, de ez nem garantál jó dallamot minden
referenciával és szegmenssel. [Baditzné Pálvölgyi Kata vizsgálata](https://real.mtak.hu/148871/)
szerint a sztenderd magyar eldöntendő kérdés jellemzően emelkedő–eső,
az utolsó előtti szótag körül csúcsosodó dallamú. A
[Cambridge Grammar](https://dictionary.cambridge.org/grammar/british-grammar/intonation)
szerint angolul az eldöntendő kérdésekben gyakori az emelkedés, míg a
kérdőszavas kérdések gyakran ereszkednek. A két nyelv nem azonos dallamrajzot
használ, de mindkettőnél fontos, hogy a kérdés önálló, kérdőjellel
végződő beszédegység maradjon.

Ezért nem alkalmazunk minden kérdés végére automatikus hangmagasság-emelést:
az korábban robotos hatást okozott, és a kérdéstípusok között sem különböztet.

## Helyi A/B próba

Az alkalmazás leállított állapotában, ugyanazzal a helyi mentett hanggal,
modellel és 123-as végső seeddel három kondicionálást hasonlítottunk össze.
A WAV-ok a Git által ignorált audio_cache alatt maradnak, nem kerülnek a repóba.

| Próba | Eredeti WAV | Rövidített belső szünet | Régi generált kérdésreferencia |
|---|---|---|---|
| „Vajon visszatér még?” | [eredeti](../reader/audio_cache/benchmarks/question-audit-20261007/hu_short-original.wav) | [rövidített](../reader/audio_cache/benchmarks/question-audit-20261007/hu_short-tight.wav) | [generált](../reader/audio_cache/benchmarks/question-audit-20261007/hu_short-synth_question.wav) |
| „Megérkezik a vonat este hét óra harminckor?” | [eredeti](../reader/audio_cache/benchmarks/question-audit-20261007/hu_long-original.wav) | [rövidített](../reader/audio_cache/benchmarks/question-audit-20261007/hu_long-tight.wav) | [generált](../reader/audio_cache/benchmarks/question-audit-20261007/hu_long-synth_question.wav) |
| „Are you coming back tomorrow?” | [eredeti](../reader/audio_cache/benchmarks/question-audit-20261007/en_short-original.wav) | [rövidített](../reader/audio_cache/benchmarks/question-audit-20261007/en_short-tight.wav) | [generált](../reader/audio_cache/benchmarks/question-audit-20261007/en_short-synth_question.wav) |

A hangos keretek YIN-féle alaphangbecslésének utolsó/első negyed-medián
aránya a hosszú magyar kérdésnél eredeti/generált/rövidített sorrendben
0,74 / 0,68 / 1,02; a rövid angolnál 1,52 / 1,04 / 1,83 volt. Ez nem
minőségi pontszám, és nem bizonyítja a magyar kérdés természetességét.
Az arányok eltérő hangmagasság-eloszlást mutatnak, de önmagukban sem
a kérdő dallam meglétét, sem a referencia oksági szerepét nem igazolják.
Egy korábbi meghallgatás a közvetlenül rövidített referenciát választotta,
de a most bemutatott magyar mintákat a felhasználó nem fogadta el.

## Javítás és hatókör

- A kérdés és az utána álló magyar vagy angol közbevetés külön szegmens
  lesz. A kijelentő mondatok eddigi közbevetés-összevonása megmarad.
  A „?!” végű hangsúlyos kérdések is a kérdésútvonalra kerülnek.
- A kérdések továbbra is külön generálódnak; a kijelentések gyors,
  kötegelt útvonala változatlan.
- A kérdés közvetlenül a narrátor eredeti WAV-jának legfeljebb egy túl
  hosszú belső szünetében rövidített változatát és annak pontos átiratát
  használja. Nincs második, géppel generált referenciaminta és nincs
  utólagos hangmagasság-manipuláció.
- A hibrid cache verziója nőtt. Az első alkalmazásindításkor csak a
  kérdést tartalmazó fejezetek mentett szegmensei épülnek újra.
  A verzió ugyanakkor a kijelentések engine-cache kulcsába is bekerül:
  az érintett fejezetek kijelentéseinél a régi verziójú cache-találat
  nem garantált. Az eredeti WAV-fájlokat a migráció nem törli.

## Meghallgatási ellenőrzés

A természetességről emberi meghallgatás dönt. Rövid, hosszú, kérdőszavas
és közbevetéses magyar kérdéseket, továbbá egy angol eldöntendő kérdést
érdemes kipróbálni. Ugyanattól a beszélőtől származó, természetes kérdést
tartalmazó WAV és pontos átirata vizsgálható következő kísérleti bemenetként;
a helyes kérdő dallam átvitelét ez sem garantálja.

### Meghallgatási visszajelzés és finomabb próba

A felhasználó a fenti, rövidített referenciás hosszú magyar mintában is
**túl késői, az utolsó szótag felé csúszó emelkedést** hallott. Ez fontos
korrekció: az utolsó/első negyed f0-aránya nem mondja meg, melyik szótagra
esik a dallamcsúcs. A v5 útvonal ezért akusztikai szempontból még nem
tekinthető véglegesnek; az alkalmazás alap-seedje változatlan.

Azonos szöveggel, referenciával és generálási beállítással csak a seedet
változtatva további, helyi, Gitből kizárt minták készültek. A becsült
f0-csúcs a hosszú kérdésnél a jelenlegi 123-as seedhez képest a 42-es
és 211-es mintában korábbra került; ez sem helyettesíti a szótagpontos
fülpróbát.

| Szöveg | Jelenlegi 123 | 42-es jelölt | 211-es jelölt |
|---|---|---|---|
| Hosszú magyar kérdés | [123](../reader/audio_cache/benchmarks/question-audit-20261007/hu_long-tight.wav) | [42](../reader/audio_cache/benchmarks/question-seeds-20261007/long-seed-42.wav) | [211](../reader/audio_cache/benchmarks/question-seeds-20261007/long-seed-211.wav) |
| Rövid magyar kérdés | [123](../reader/audio_cache/benchmarks/question-audit-20261007/hu_short-tight.wav) | [42](../reader/audio_cache/benchmarks/question-seeds-20261007/short-seed-42.wav) | [211](../reader/audio_cache/benchmarks/question-seeds-20261007/short-seed-211.wav) |

## ER Sno: valódi kérdésmintával kiegészített referencia

A mentett, szintetikus ER Sno hang (10-es hangazonosító) eredeti WAV-ját és
átiratát változatlanul hagytuk. Második referenciaként a felhasználó által
adott, ugyanazon hangú, kb. 2,5 másodperces „Megmondhatom nekik, hogy meg
fogja csinálni?” WAV-ot és a fájlnév alapján feltételezett pontos átiratát
adtuk a Higgs/MLX modellnek. A [külön összehasonlító
szkript](../reader/scripts/compare_higgs_question_references.py) azonos
123-as seeddel, szöveggel és generálási paraméterekkel két változatot
készített mind a hat szövegre. A mentett hang, az alkalmazás generálási
útvonala és a könyvek változatlanok. A WAV-ok és a
[mérési napló](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/results.json)
csak a Gitből kizárt audio_cache mappában vannak. Az alábbi helyi hanglinkek
csak ezen a gépen működnek; GitHubon és új klónban nincsenek meg a WAV-ok.

| Próbaszöveg | Csak eredeti referencia | Eredeti + kérdésminta |
|---|---|---|
| Eljönnek vasárnap? | [alap](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/01-base.wav) | [kiegészített](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/01-base-plus-question.wav) |
| Ha végeznek a költözéssel, eljönnek vasárnap? | [alap](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/02-base.wav) | [kiegészített](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/02-base-plus-question.wav) |
| Jó? | [alap](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/03-base.wav) | [kiegészített](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/03-base-plus-question.wav) |
| Elég? | [alap](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/04-base.wav) | [kiegészített](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/04-base-plus-question.wav) |
| Mikor érkeznek? | [alap](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/05-base.wav) | [kiegészített](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/05-base-plus-question.wav) |
| Eljönnek vasárnap. (kontroll) | [alap](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/06-base.wav) | [kiegészített](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/06-base-plus-question.wav) |

Mind a 12 kimenet érvényes, nem néma, 24 kHz-es mono WAV. A próba egyetlen
generálás kondíciónként, ezért a generálási idők és a hallható különbségek
nem bizonyítanak általános sebesség- vagy minőségjavulást. A természetességről
a páronkénti emberi meghallgatás után döntünk; az új referencia még nincs
bekötve az alkalmazásba.

### Célzott „Elég?” próba

A felhasználó az első kísérlet legtöbb javítását jónak hallotta, de az
„Elég?” kérdést nem; a „Jó?” sikerült. Ezért a bevált hosszú kérdésminta
mellé külön-külön hozzáadtunk egy rövid, ugyanazon beszélőtől származó
„Főnök?” és „Fogjak felmosót?” kérdésmintát. Azonos modellel, 123-as
seeddel és prompttal mindkét változatnál elkészült az „Elég?” és a
„Jó?” kontroll. **Aktuálisan a „Fogjak felmosót?”-ös változat a kiválasztott
jelölt.** A „Főnök?”-ös próbát összehasonlításra megtartjuk.

| Szöveg | Csak hosszú kérdésminta | + „Főnök?” | + „Fogjak felmosót?” |
|---|---|---|---|
| Elég? | [eredeti jelölt](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/04-base-plus-question.wav) | [új 1](../reader/audio_cache/benchmarks/er-sno-eleg-fonok-20261007/01-base-plus-question.wav) | [új 2](../reader/audio_cache/benchmarks/er-sno-eleg-felmosot-20261007/01-base-plus-question.wav) |
| Jó? | [eredeti jelölt](../reader/audio_cache/benchmarks/er-sno-long-question-20261007/03-base-plus-question.wav) | [új 1](../reader/audio_cache/benchmarks/er-sno-eleg-fonok-20261007/02-base-plus-question.wav) | [új 2](../reader/audio_cache/benchmarks/er-sno-eleg-felmosot-20261007/02-base-plus-question.wav) |

A korábban kiválasztott eredeti + hosszú kérdés + „Főnök?” kondicionálással
mind a hat próbamondatot újrageneráltuk. A [teljes ellenőrző sorozat és mérési
napló](../reader/audio_cache/benchmarks/er-sno-long-plus-fonok-full-20261007/results.json)
helyben, a Gitből kizárt audio_cache alatt marad.

A felhasználó ezután összehasonlításra kérte a „Fogjak felmosót?”-ös változat
ugyanilyen hatmondatos sorozatát, majd erre változtatta a választását. A [külön mérési
napló](../reader/audio_cache/benchmarks/er-sno-long-plus-felmosot-full-20261007/results.json)
és a hozzá tartozó WAV-ok helyben elkészültek. Az „Elég?” és „Jó?” fájlok
bitre azonosak a korábbi célzott próbában készült párjukkal. A kiválasztott
referenciákat még nem kötöttük be az alkalmazásba; a mentett ER Sno hangot,
a könyveket és a többi narrátort ez a dokumentált választás nem módosítja.
