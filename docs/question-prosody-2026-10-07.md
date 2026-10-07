# Kérdő mondatok: Higgs/MLX audit — 2026-10-07

## Diagnózis

A magyar kérdések néha kijelentésként hangzottak; ugyanez angolul is
előfordult. Két egymástól független okot találtunk:

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
Annyit mutat, hogy a régi generált referencia nem biztosított következetes
kérdő dallamot. A korábbi felhasználói meghallgatás is a közvetlenül
rövidített referenciát választotta kérdésekhez.

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
  A változatlan kijelentő hangfájlok engine-cache találatként
  újrahasználhatók.

## Meghallgatási ellenőrzés

A természetességről emberi meghallgatás dönt. Rövid, hosszú, kérdőszavas
és közbevetéses magyar kérdéseket, továbbá egy angol eldöntendő kérdést
érdemes kipróbálni. Ha egy adott hang továbbra is kijelentésszerű,
a legjobb következő bemenet ugyanattól a beszélőtől származó, természetesen
kimondott kérdést is tartalmazó WAV és annak pontos átirata.
