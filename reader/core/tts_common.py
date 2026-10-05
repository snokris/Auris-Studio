"""Shared TTS utilities used by the Higgs backends."""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from core.hungarian_numbers import looks_hungarian, normalize_hungarian

log = logging.getLogger(__name__)

AUDIO_CACHE_DIR = str(Path(__file__).resolve().parent.parent / "audio_cache")
SAMPLE_RATE = 24_000
_BRACKET_TAG_RE = re.compile(r"\[[^\[\]]*\]")
_WETEXT_CACHE: dict[str, object] = {}


def _write_audio_atomic(path: str, audio: np.ndarray, sample_rate: int) -> None:
    """Write a cache WAV without exposing a partial file to another worker."""
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp.wav"
    try:
        sf.write(tmp, audio, sample_rate)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _map_tn_lang(language: str | None, text: str) -> str:
    code = (language or "").strip().lower()
    if code in {"en", "english"}:
        return "en"
    if code in {"zh", "zh-cn", "zh-tw", "chinese", "mandarin"}:
        return "zh"
    if code in {"ja", "japanese"}:
        return "ja"
    if code and code not in {"none", "auto"}:
        return code
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    return "en"


def _apply_with_bracket_protection(text: str, fn) -> str:
    parts: list[str] = []
    last = 0
    for match in _BRACKET_TAG_RE.finditer(text):
        if match.start() > last:
            parts.append(fn(text[last:match.start()]))
        parts.append(match.group())
        last = match.end()
    if last < len(text):
        parts.append(fn(text[last:]))
    return "".join(parts) if parts else fn(text)


def _num2words_fallback(text: str, language: str | None) -> str:
    if looks_hungarian(language, text):
        return _apply_with_bracket_protection(text, normalize_hungarian)
    try:
        from num2words import num2words
    except ImportError:
        return text

    lang = _map_tn_lang(language, text)
    n2w_lang = "en" if lang == "ja" else ("zh" if lang == "zh" else lang)

    def replace(match: re.Match) -> str:
        try:
            return num2words(int(match.group()), lang=n2w_lang)
        except Exception:
            try:
                return num2words(int(match.group()), lang="en")
            except Exception:
                return match.group()

    return _apply_with_bracket_protection(
        text, lambda part: re.sub(r"\d+", replace, part)
    )


def _wetext_normalize(text: str, language: str | None) -> str | None:
    try:
        from wetext import Normalizer
    except ImportError:
        return None
    lang = _map_tn_lang(language, text)
    if lang not in {"en", "zh", "ja"}:
        return None
    try:
        normalizer = _WETEXT_CACHE.get(lang)
        if normalizer is None:
            normalizer = Normalizer(lang=lang, operator="tn")
            _WETEXT_CACHE[lang] = normalizer
        return _apply_with_bracket_protection(text, normalizer.normalize)
    except Exception as exc:
        log.warning("wetext normalization failed (%s).", type(exc).__name__)
        return None


def apply_text_normalization(
    text: str,
    language: str | None = None,
    *,
    tts_friendly: bool = False,
) -> str:
    """Expand numbers, dates, times and currencies before synthesis."""
    if not text or not text.strip():
        return text
    if looks_hungarian(language, text):
        return _apply_with_bracket_protection(
            text,
            lambda part: normalize_hungarian(part, tts_friendly=tts_friendly),
        )
    wetext_output = _wetext_normalize(text, language)
    if wetext_output is not None:
        return wetext_output
    return _num2words_fallback(text, language)


class TTSExportPool:
    """Compatibility wrapper for the single resident Higgs engine."""

    def __init__(self, primary, requested_workers: int = 0):
        self.primary = primary
        self.requested_workers = requested_workers

    @property
    def worker_count(self) -> int:
        return 1

    def start(self) -> int:
        return 1

    def generate_many(self, items: list[dict], **kwargs) -> list[dict]:
        return self.primary.generate_many(items, **kwargs)

    def close(self) -> None:
        return None
