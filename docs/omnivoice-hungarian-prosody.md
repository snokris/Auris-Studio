# OmniVoice magyar prozódia — fejlesztési és A/B jegyzet

Dátum: 2026-10-05. Ág: `feature/omnivoice-hungarian-prosody`.

## Beépített javítások

- Konzervatív magyar beszédmód-felismerés a `core/parser/hungarian_prosody.py` modulban: suttogás/halk beszéd, nevetés, sóhaj, elégedetlenség, gyors/sürgető és lassú/nyugodt előadás.
- A szabályok csak a forrásban kifejezetten jelen lévő szavakra reagálnak; nem találnak ki érzelmet vagy beszélőt.
- A kérdés és a felkiáltás egyik egynarrátoros összevonási lépésben sem olvadhat a szomszédos mondatba.
- A tempó mondatonként készül. A gyors vagy halk mondat előadásmódja nem terjed át a következő semleges mondatra.
- Kérdés: legfeljebb `0.98`; felkiáltás: legalább `1.03`; explicit gyors magyar mondat: legfeljebb `1.05` narrációban; halk/lassú/suttogó mondat: legfeljebb `0.94`.
- Az OmniVoice nem verbális tagje csak explicit idézett nevetésnél, sóhajnál vagy elégedetlenségnél kerül be. Kérdőjelből továbbra sem lesz `oh/ah` mellékhang.

Ezek a szegmentálási és tempóadatok a közös enrichment rétegben készülnek. Az OmniVoice közvetlenül használja a finom `speed` értékeket; a Higgs csak a saját durvább sebességtoken-küszöbeinél reagál rájuk.

## M5 Pro A/B mérés

Ugyanazzal a helyi, privát narrátorhanggal hat magyar eset készült: nyugodt
narráció, kérdés, felkiáltás, sürgetés, suttogás és sóhaj. MPS/float32, fix
123 seed, kész hangcache megkerülve.

| Lépés | Hat minta összideje | Átlag/minta | Átlagos RTF |
|---:|---:|---:|---:|
| 16 | 26,18 s | 4,36 s | 2,425 |
| 24 | 35,50 s | 5,92 s | 3,230 |
| 32 | 46,52 s | 7,75 s | 4,234 |

A sebességadat önmagában nem dönt minőségről. A 16/24/32 alapértéket meghallgatás után választjuk ki; az alkalmazás mentett értéke egyelőre változatlanul 16.

Külön 16 lépéses kontroll készült referenciahang + `whisper` utasítással. A hatból öt WAV bitazonos maradt, csak a suttogó minta változott, tehát a kísérleti kapcsoló célzottan jutott el a modellhez. Ez még nincs bekapcsolva a normál alkalmazásban: előbb ellenőrizni kell a suttogás természetességét és a narrátor azonosságát.

A privát eredmények Gitből kizárt helyei:

- `reader/audio_cache/benchmarks/omnivoice-prosody-16-20261005/`
- `reader/audio_cache/benchmarks/omnivoice-prosody-24-20261005/`
- `reader/audio_cache/benchmarks/omnivoice-prosody-32-20261005/`
- `reader/audio_cache/benchmarks/omnivoice-prosody-16-clone-instruct-20261005/`

## Meghallgatási döntés

A 16/24/32 lépéses és a célzott utasításos változatok egyike sem érte el a
Higgs természetes magyar kiejtési és hangsúlyozási szintjét. Emiatt ez a
szabályréteg legfeljebb vázlatmotor-javításnak tekintendő; az OmniVoice nem
lesz a végleges, minőségre optimalizált felolvasás elsődleges motorja.

A további fő irány a [Higgs TTS 3 natív MLX futtatása](higgs-mlx-apple-silicon.md),
amely ugyanazt a jobb minőségű modellcsaládot gyorsítja Apple Siliconon.

## Ellenőrzés és korlátok

A teljes készlet 318/318 zöld. Az új tesztek ellenőrzik a magyar ragozott alakokat, hamis részszó-egyezéseket, kérdés/felkiáltás határait, lokális tempót, suttogást, explicit tageket, a benchmark enrichmentjét és a klónutasítás explicit opt-in jellegét.

A változás az újonnan felépített szegmensekre/generálásokra hat. A meglévő könyv megnyitása újraszegmentálást és új hangigényt válthat ki, ezért a szervert a meghallgatási döntésig nem indítottuk újra. A `Ft`, ponttal írt idő és hosszú évszám javítása külön, közös magyar normalizálási kör.
