"""Conservative Hungarian delivery cues for audiobook narration.

These rules identify explicit wording only. They do not infer a character or
invent an emotion that is absent from the source text.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

def _forms(*patterns: str) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.IGNORECASE)


_WHISPER = _forms(r"suttog\w*", r"susog\w*", r"lehel\w*", r"halk\w*", r"nesztelen\w*")
_LAUGHTER = _forms(r"nevet\w*", r"felnevet\w*", r"kacag\w*", r"kuncog\w*", r"vihog\w*")
_SIGH = _forms(r"sóhajt\w*", r"felsóhajt\w*")
_DISSATISFACTION = _forms(
    r"morog\w*", r"mordul\w*", r"mormol\w*", r"dörmög\w*", r"sziszeg\w*",
    r"csattan\w*", r"vicsorog\w*"
)
_FAST = _forms(
    r"gyors\w*", r"siet\w*", r"rohan\w*", r"fut(?:ott|va|ás\w*|ni|nak|ottak)?",
    r"kapkod\w*", r"hirtelen", r"felpattan\w*", r"kiált\w*", r"ordít\w*",
    r"üvölt\w*", r"sikolt\w*"
)
_SLOW = _forms(
    r"lass(?:an|ú\w*|ít\w*)", r"csendes\w*", r"óvatos\w*", r"ünnepélyes\w*",
    r"szomorú\w*", r"fáradt\w*", r"vontatott\w*", r"nyugodt\w*", r"tétován",
    r"bizonytalan\w*"
)


@dataclass(frozen=True)
class HungarianProsody:
    whisper: bool = False
    laughter: bool = False
    sigh: bool = False
    dissatisfaction: bool = False
    fast: bool = False
    slow: bool = False


def analyze_hungarian_prosody(text: str) -> HungarianProsody:
    value = str(text or "")
    return HungarianProsody(
        whisper=bool(_WHISPER.search(value)),
        laughter=bool(_LAUGHTER.search(value)),
        sigh=bool(_SIGH.search(value)),
        dissatisfaction=bool(_DISSATISFACTION.search(value)),
        fast=bool(_FAST.search(value)),
        slow=bool(_SLOW.search(value)),
    )
