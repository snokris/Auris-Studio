"""Read Hungarian numbers out loud the way a narrator would.

Both TTS engines mangle bare digits in Hungarian: they either spell them in
English or guess a wrong Hungarian form, and ``num2words``' Hungarian tables
are wrong for ordinals above a hundred (``102.`` comes back as *"százkétik"*).
Hungarian audiobooks are full of years, dates and chapter numbers, so the whole
mapping lives here instead: digits in, spoken words out.

The hard parts this module gets right:

* ``932.`` is an ordinal — *"kilencszázharminckettedik"*, not *"kilencszázharminckettő"*
* a date reads differently from an ordinal: ``1932. március 5-én`` →
  *"ezerkilencszázharminckettő március ötödikén"*
* a number in front of a noun uses the short form: ``12 alma`` →
  *"tizenkét alma"*, while a bare ``12`` stays *"tizenkettő"*
* suffixes glued on with a hyphen keep their own vowels: ``3-at`` → *"hármat"*
"""

from __future__ import annotations

import re

__all__ = [
    'cardinal',
    'ordinal',
    'day_of_month',
    'looks_hungarian',
    'normalize_hungarian',
]

_UNITS = ('nulla', 'egy', 'kettő', 'három', 'négy', 'öt', 'hat', 'hét',
          'nyolc', 'kilenc')
_TENS = {2: 'húsz', 3: 'harminc', 4: 'negyven', 5: 'ötven', 6: 'hatvan',
         7: 'hetven', 8: 'nyolcvan', 9: 'kilencven'}
# 11-19 and 21-29 use a bound form of the tens ("tizenhárom", "huszonhárom").
_BOUND_TENS = {1: 'tizen', 2: 'huszon'}
_SCALES = ((10 ** 9, 'milliárd'), (10 ** 6, 'millió'), (1000, 'ezer'))

# Above 2000 Hungarian spelling puts a hyphen on the thousand boundary
# ("kétezer-huszonnégy"), below it the number is one word.
_HYPHEN_ABOVE = 2000

_MONTHS = (
    'január', 'február', 'március', 'április', 'május', 'június',
    'július', 'augusztus', 'szeptember', 'október', 'november', 'december',
)

# Words that can follow a number without being counted by it, so "2 és 3"
# stays "kettő és három" instead of turning into the attributive "két".
_NOT_COUNTED = {
    'és', 'vagy', 'meg', 'de', 'is', 'sem', 'se', 'pedig', 'hogy', 'mint',
    'majd', 'azaz', 'avagy', 'valamint', 'illetve', 'plusz', 'mínusz',
}

# Nouns that make a trailing period an ordinal even when the word is
# capitalised, as in the chapter heading "5. Fejezet".
_ORDINAL_NOUNS = {
    'fejezet', 'rész', 'kötet', 'könyv', 'század', 'évszázad', 'esztendő',
    'esztendejében', 'év', 'évben', 'oldal', 'kiadás', 'világháború',
    'emelet', 'sor', 'pont', 'bekezdés', 'versszak', 'felvonás', 'jelenet',
    'szám', 'osztály', 'kerület', 'alkalom', 'helyezett', 'hadsereg',
    'törvény', 'paragrafus', 'cikkely', 'melléklet', 'függelék', 'táblázat',
    'ábra', 'levél', 'napon', 'nap', 'hét', 'hónap', 'ízben',
}

# Parts of the year: after these a year stays a cardinal, because "1932. nyarán"
# is read as "ezerkilencszázharminckettő nyarán", not as an ordinal.
_YEAR_PARTS = {
    'nyarán', 'nyara', 'nyarától', 'nyaráig', 'tavaszán', 'tavasza',
    'őszén', 'ősze', 'őszétől', 'telén', 'tele', 'karácsonyán', 'húsvétján',
    'elején', 'eleje', 'végén', 'vége', 'közepén', 'közepe', 'folyamán',
    'táján', 'őszén', 'januárjában', 'decemberében',
}

_LOWER = 'a-záéíóöőúüű'
_VOWEL_SUFFIX_START = set('aeioóöőuúüű')
_BACK_VOWELS = set('aáoóuú')


def _multiplier(n: int) -> str:
    """The form used in front of száz/ezer/millió: 2 is "két", never "kettő"."""
    return cardinal(n, before_noun=True)


def _below_hundred(n: int) -> str:
    if n < 10:
        return _UNITS[n]
    tens, unit = divmod(n, 10)
    if unit == 0:
        return 'tíz' if tens == 1 else _TENS[tens]
    if tens in _BOUND_TENS:
        return _BOUND_TENS[tens] + _UNITS[unit]
    return _TENS[tens] + _UNITS[unit]


def _below_thousand(n: int) -> str:
    if n < 100:
        return _below_hundred(n)
    hundreds, rest = divmod(n, 100)
    head = 'száz' if hundreds == 1 else _multiplier(hundreds) + 'száz'
    return head + (_below_thousand(rest) if rest else '')


def cardinal(n: int, before_noun: bool = False) -> str:
    """``932`` → "kilencszázharminckettő"; before a noun 2 becomes "két"."""
    n = int(n)
    if n < 0:
        return 'mínusz ' + cardinal(-n, before_noun)

    if n < 1000:
        word = _below_thousand(n)
    else:
        word = ''
        for value, name in _SCALES:
            if n < value:
                continue
            count, rest = divmod(n, value)
            if value == 1000 and count == 1:
                head = name  # 1000 is "ezer", never "egyezer"
            else:
                head = _multiplier(count) + name
            if rest:
                separator = '-' if n > _HYPHEN_ABOVE else ''
                word = head + separator + cardinal(rest)
            else:
                word = head
            break

    if before_noun and word.endswith('kettő'):
        word = word[:-len('kettő')] + 'két'
    return word


def _tts_cardinal(n: int, before_noun: bool = False) -> str:
    """Cardinal with subtle word boundaries that help multilingual TTS.

    Hungarian spelling joins most number components.  Multilingual acoustic
    models can lose syllables in a token such as
    ``ezerkilencszázharminckettő``; spaces at scale/hundred boundaries retain
    the same spoken wording while giving the tokenizer stable units.
    """
    n = int(n)
    if n < 0:
        return 'mínusz ' + _tts_cardinal(-n, before_noun)

    if n < 100:
        word = _below_hundred(n)
    elif n < 1000:
        hundreds, rest = divmod(n, 100)
        head = 'száz' if hundreds == 1 else _multiplier(hundreds) + 'száz'
        word = head + (f' {_tts_cardinal(rest)}' if rest else '')
    else:
        word = ''
        for value, name in _SCALES:
            if n < value:
                continue
            count, rest = divmod(n, value)
            head = name if value == 1000 and count == 1 else _multiplier(count) + name
            word = head + (f' {_tts_cardinal(rest)}' if rest else '')
            break

    if before_noun and word.endswith('kettő'):
        word = word[:-len('kettő')] + 'két'
    return word


# The last element of a compound carries the ordinal ending; everything in
# front of it stays a cardinal ("ezerkilencszáz" + "harminc" + "kettedik").
_ORDINAL_ENDINGS = sorted(
    (
        ('kettő', 'kettedik'), ('három', 'harmadik'), ('négy', 'negyedik'),
        ('öt', 'ötödik'), ('hat', 'hatodik'), ('hét', 'hetedik'),
        ('nyolc', 'nyolcadik'), ('kilenc', 'kilencedik'), ('egy', 'egyedik'),
        ('tíz', 'tizedik'), ('húsz', 'huszadik'), ('harminc', 'harmincadik'),
        ('negyven', 'negyvenedik'), ('ötven', 'ötvenedik'),
        ('hatvan', 'hatvanadik'), ('hetven', 'hetvenedik'),
        ('nyolcvan', 'nyolcvanadik'), ('kilencven', 'kilencvenedik'),
        ('száz', 'századik'), ('ezer', 'ezredik'), ('millió', 'milliomodik'),
        ('milliárd', 'milliárdodik'), ('nulla', 'nulladik'),
    ),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


def _ordinal_word(word: str) -> str:
    for ending, replacement in _ORDINAL_ENDINGS:
        if word.endswith(ending):
            return word[:-len(ending)] + replacement
    return word + 'dik'


def ordinal(n: int) -> str:
    """``932`` → "kilencszázharminckettedik"."""
    n = int(n)
    if n == 1:
        return 'első'
    if n == 2:
        return 'második'
    return _ordinal_word(cardinal(n))


def _tts_ordinal(n: int) -> str:
    """Ordinal equivalent of :func:`_tts_cardinal` for acoustic prompts."""
    n = int(n)
    if n in (1, 2):
        return ordinal(n)
    spoken = _tts_cardinal(n)
    head, separator, tail = spoken.rpartition(' ')
    converted = _ordinal_word(tail)
    return f'{head}{separator}{converted}' if separator else converted


def _day_stem(n: int, tts_friendly: bool = False) -> str:
    """The stem a date suffix attaches to: "elsej-én", "ötödik-én"."""
    if int(n) == 1:
        return 'elsej'
    return _tts_ordinal(n) if tts_friendly else ordinal(n)


def _harmony_vowel(word: str) -> str:
    """Back or front linking vowel, ignoring the neutral i of "-dik"."""
    for char in reversed(word):
        if char in _BACK_VOWELS:
            return 'a'
        if char in 'eéöőüű':
            return 'e'
    return 'e'


def day_of_month(n: int, tts_friendly: bool = False) -> str:
    """``5`` → "ötödike" — how a date is read when nothing follows it."""
    if int(n) == 1:
        return 'elseje'
    word = _tts_ordinal(n) if tts_friendly else ordinal(n)
    return word + _harmony_vowel(word)


def _attach(stem: str, suffix: str) -> str:
    """Glue a written suffix onto a stem without doubling the linking letter."""
    if stem.endswith('j') and suffix.startswith('j'):
        suffix = suffix[1:]
    return stem + suffix


# Stems that change shape in front of a suffix that starts with a vowel:
# "három" + "-at" is "hármat", "ezer" + "-et" is "ezret".
_SUFFIX_STEMS = (('három', 'hárm'), ('kettő', 'kett'), ('ezer', 'ezr'),
                 ('hét', 'het'))


def _cardinal_with_suffix(
    n: int, suffix: str, tts_friendly: bool = False
) -> str:
    word = _tts_cardinal(n) if tts_friendly else cardinal(n)
    if suffix[:1] in _VOWEL_SUFFIX_START:
        for ending, stem in _SUFFIX_STEMS:
            if word.endswith(ending):
                word = word[:-len(ending)] + stem
                break
    return word + suffix


_ROMAN_PARTS = (
    (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'),
    (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
)


def _roman_value(text: str) -> int | None:
    """Value of a canonically written Roman numeral, else ``None``.

    The round-trip check keeps letter salad out: ``DVD`` parses to a number
    with a naive reader, but it is not how anyone writes 995.
    """
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    previous = 0
    for char in reversed(text):
        value = values.get(char)
        if value is None:
            return None
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    if total <= 0 or _to_roman(total) != text:
        return None
    return total


def _to_roman(value: int) -> str:
    out = []
    for amount, letters in _ROMAN_PARTS:
        while value >= amount:
            out.append(letters)
            value -= amount
    return ''.join(out)


_MONTH_RE = '|'.join(_MONTHS)
_SUFFIX_RE = f'[{_LOWER}]+'

_THOUSAND_GROUPED = re.compile(r'(?<![\d.,])(\d{1,3})(?:[.  ](\d{3}))+(?![\d.,])')
_DATE_FULL = re.compile(
    rf'\b(\d{{1,4}})\.\s+({_MONTH_RE})\s+(\d{{1,2}})\.(?:-({_SUFFIX_RE}))?'
)
_DATE_MONTH_DAY = re.compile(rf'\b({_MONTH_RE})\s+(\d{{1,2}})\.(?:-({_SUFFIX_RE}))?')
_DATE_YEAR_MONTH = re.compile(rf'\b(\d{{3,4}})\.\s+({_MONTH_RE})\b')
_ROMAN = re.compile(r'\b([IVXLCDM]{2,})\.(?=\s+(\w+))')
_TIME = re.compile(rf'\b(\d{{1,2}}):(\d{{2}})(?:-({_SUFFIX_RE}))?')
_DOTTED_TIME = re.compile(rf'\b(\d{{1,2}})\.(\d{{2}})-({_SUFFIX_RE})')
_CURRENCY = re.compile(rf'\b(\d+)\s*(?:Ft|HUF)(?:-?({_SUFFIX_RE}))?\b', re.IGNORECASE)
_PERCENT = re.compile(rf'(\d+)(?:,(\d+))?\s*%(?:-?({_SUFFIX_RE}))?')
_DEGREE = re.compile(rf'(-?\d+)\s*°\s*C(?:-?({_SUFFIX_RE}))?\b')
_SUFFIXED = re.compile(rf'\b(\d+)-({_SUFFIX_RE})')
_ORDINAL = re.compile(rf'\b(\d+)\.(?=\s+(\w+))')
_DECIMAL = re.compile(r'\b(\d+),(\d+)\b')
_INTEGER = re.compile(r'\b\d+\b')


def _is_ordinal_context(word: str) -> bool:
    """``század``, ``fejezet``, ``esztendejében`` — nouns you count with."""
    plain = word.lower()
    return plain in _ORDINAL_NOUNS or any(
        plain.startswith(noun) for noun in _ORDINAL_NOUNS
    )


def _expand_roman(match: re.Match) -> str:
    """``XX. század`` and ``II. Erzsébet`` are ordinals; other letters are not."""
    value = _roman_value(match.group(1))
    following = match.group(2)
    if value is None:
        return match.group()
    if following[:1].isupper():
        # A ruler's name: "II. Erzsébet" reads as "Második Erzsébet".
        return ordinal(value).capitalize()
    if _is_ordinal_context(following):
        return ordinal(value)
    return match.group()


def _date_suffix(
    day: int, suffix: str | None, tts_friendly: bool = False
) -> str:
    if not suffix:
        return day_of_month(day, tts_friendly)
    return _attach(_day_stem(day, tts_friendly), suffix)


def _number_suffix(n: int, suffix: str, tts_friendly: bool = False) -> str:
    """A hyphenated suffix decides whether this is a date or a plain number.

    ``-án``/``-én``/``-jén`` only ever appear on a day of the month, so
    ``5-én`` is "ötödikén" while ``1932-ben`` stays "ezerkilencszázharminckettőben".
    """
    if suffix.startswith('ér'):  # "5-ért" is a plain number, not a date
        return _cardinal_with_suffix(n, suffix, tts_friendly)
    if suffix[:1] in ('á', 'é', 'j'):
        return _attach(_day_stem(n, tts_friendly), suffix)
    return _cardinal_with_suffix(n, suffix, tts_friendly)


def _expand_time(match: re.Match, tts_friendly: bool = False) -> str:
    hour, minute = int(match.group(1)), int(match.group(2))
    suffix = match.group(3) or ''
    number = _tts_cardinal if tts_friendly else cardinal
    if minute:
        spoken = f'{number(hour, before_noun=True)} óra {number(minute)} perc'
    else:
        spoken = f'{number(hour, before_noun=True)} óra'
    return _cardinal_tail(spoken, suffix) if suffix else spoken


def _cardinal_tail(spoken: str, suffix: str) -> str:
    """Attach a suffix to the last word of an already spoken phrase."""
    head, _, last = spoken.rpartition(' ')
    glued = _attach(last, suffix)
    return f'{head} {glued}' if head else glued


def _expand_currency(match: re.Match, tts_friendly: bool = False) -> str:
    number = _tts_cardinal if tts_friendly else cardinal
    spoken = f'{number(int(match.group(1)), before_noun=True)} forint'
    suffix = match.group(2)
    return _cardinal_tail(spoken, suffix) if suffix else spoken


def _expand_degree(match: re.Match, tts_friendly: bool = False) -> str:
    """``21 °C`` is "huszonegy Celsius-fok"; ``21 °C-ban`` keeps its suffix."""
    number = _tts_cardinal if tts_friendly else cardinal
    spoken = f'{number(int(match.group(1)))} Celsius-fok'
    suffix = match.group(2)
    return _attach(spoken, suffix) if suffix else spoken


def _expand_percent(match: re.Match, tts_friendly: bool = False) -> str:
    whole, fraction, suffix = match.group(1), match.group(2), match.group(3)
    number = _tts_cardinal if tts_friendly else cardinal
    spoken = number(int(whole), before_noun=True)
    if fraction:
        spoken = f'{number(int(whole))} egész {number(int(fraction))}'
    spoken = f'{spoken} százalék'
    return _cardinal_tail(spoken, suffix) if suffix else spoken


def _counts_the_next_word(text: str, end: int) -> bool:
    """True when the number modifies a following noun ("12 alma")."""
    rest = text[end:]
    match = re.match(rf'\s+([{_LOWER}]+)', rest)
    if not match:
        return False
    return match.group(1) not in _NOT_COUNTED


def _expand_ordinal_or_sentence_end(text: str, tts_friendly: bool = False):
    """``932. esztendejében`` is an ordinal; ``Volt 932. Aztán…`` is not."""
    def repl(match: re.Match) -> str:
        following = match.group(2)
        value = int(match.group(1))
        number = _tts_cardinal if tts_friendly else cardinal
        position = _tts_ordinal if tts_friendly else ordinal
        if 1000 <= value <= 2999 and following.lower() in _YEAR_PARTS:
            # A year in front of a season or a part of the year keeps its
            # cardinal form: "1932. nyarán" is "ezerkilencszázharminckettő nyarán".
            return number(value)
        if following[:1].islower() or following.lower() in _ORDINAL_NOUNS:
            return position(value)
        # A capitalised word after the period reads as a new sentence, so the
        # number itself is a plain cardinal and the period stays a full stop.
        return f'{number(value)}.'
    return _ORDINAL.sub(repl, text)


def normalize_hungarian(text: str, *, tts_friendly: bool = False) -> str:
    """Replace digits with Hungarian words.

    ``tts_friendly`` inserts boundaries inside long number compounds for
    multilingual speech models without changing the words themselves.
    """
    if not text:
        return text
    if not any(char.isdigit() for char in text) and not _ROMAN.search(text):
        return text

    def join_groups(match: re.Match) -> str:
        return re.sub(r'[.  ]', '', match.group())

    out = _THOUSAND_GROUPED.sub(join_groups, text)

    out = _DATE_FULL.sub(
        lambda m: f'{(_tts_cardinal if tts_friendly else cardinal)(int(m.group(1)))} '
                  f'{m.group(2)} '
                  f'{_date_suffix(int(m.group(3)), m.group(4), tts_friendly)}',
        out,
    )
    out = _DATE_MONTH_DAY.sub(
        lambda m: f'{m.group(1)} '
                  f'{_date_suffix(int(m.group(2)), m.group(3), tts_friendly)}',
        out,
    )
    out = _DATE_YEAR_MONTH.sub(
        lambda m: f'{(_tts_cardinal if tts_friendly else cardinal)(int(m.group(1)))} '
                  f'{m.group(2)}',
        out,
    )

    out = _ROMAN.sub(_expand_roman, out)

    out = _DOTTED_TIME.sub(lambda m: _expand_time(m, tts_friendly), out)
    out = _TIME.sub(lambda m: _expand_time(m, tts_friendly), out)
    out = _CURRENCY.sub(lambda m: _expand_currency(m, tts_friendly), out)
    out = _PERCENT.sub(lambda m: _expand_percent(m, tts_friendly), out)
    out = _DEGREE.sub(lambda m: _expand_degree(m, tts_friendly), out)
    out = _SUFFIXED.sub(
        lambda m: _number_suffix(int(m.group(1)), m.group(2), tts_friendly), out
    )
    out = _expand_ordinal_or_sentence_end(out, tts_friendly)
    out = _DECIMAL.sub(
        lambda m: f'{(_tts_cardinal if tts_friendly else cardinal)(int(m.group(1)))} '
                  f'egész {(_tts_cardinal if tts_friendly else cardinal)(int(m.group(2)))}',
        out,
    )
    out = _INTEGER.sub(
        lambda m: (_tts_cardinal if tts_friendly else cardinal)(
            int(m.group()), _counts_the_next_word(out, m.end())
        ),
        out,
    )
    return out


_HUNGARIAN_CODES = {'hu', 'hun', 'hu-hu', 'hungarian', 'magyar'}


def looks_hungarian(language: str | None, text: str = '') -> bool:
    """Hungarian by declared language, or by letters only Hungarian uses."""
    code = str(language or '').strip().lower()
    if code in _HUNGARIAN_CODES:
        return True
    if code and code not in {'none', 'auto', ''}:
        return False
    return bool(re.search(r'[őűŐŰ]', text))
