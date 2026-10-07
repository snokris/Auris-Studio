"""Optional, per-voice question references stored beside a saved voice WAV.

The sidecar and its WAV files belong to the local voice library, not to the
model or the repository. A changed base WAV is deliberately rejected instead
of silently applying another speaker's question recordings.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def question_reference_sidecar(ref_audio: str) -> Path:
    return Path(ref_audio).with_suffix(".questions.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_question_references(
    ref_audio: str | None, ref_text: str | None
) -> list[dict[str, str]] | None:
    """Return the original voice plus its verified question WAVs, if configured."""
    if not ref_audio:
        return None
    base = Path(ref_audio).resolve()
    sidecar = question_reference_sidecar(str(base))
    if not sidecar.is_file():
        return None
    if not ref_text or not ref_text.strip():
        raise ValueError(f"Question references require the base transcript: {sidecar}")
    if sidecar.stat().st_size > 32_768:
        raise ValueError(f"Question reference configuration is too large: {sidecar}")
    config = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema") != 1:
        raise ValueError(f"Unsupported question reference configuration: {sidecar}")
    if config.get("base_sha256") != _sha256(base):
        raise ValueError(f"The base voice WAV changed; review question references: {sidecar}")
    configured = config.get("references")
    if not isinstance(configured, list) or not 1 <= len(configured) <= 4:
        raise ValueError(f"Expected 1–4 question references: {sidecar}")
    result = [{"audio": str(base), "text": ref_text.strip()}]
    seen = {base}
    for entry in configured:
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid question reference entry: {sidecar}")
        filename = entry.get("file")
        text = entry.get("text")
        expected_sha256 = entry.get("sha256")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not filename.lower().endswith(".wav")
            or not isinstance(text, str)
            or "?" not in text
            or not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
        ):
            raise ValueError(f"Invalid question WAV or transcript: {sidecar}")
        path = (sidecar.parent / filename).resolve()
        if path.parent != sidecar.parent.resolve() or path in seen or not path.is_file():
            raise ValueError(f"Question reference WAV is missing or unsafe: {filename}")
        if _sha256(path) != expected_sha256:
            raise ValueError(f"Question reference WAV changed: {filename}")
        seen.add(path)
        result.append({"audio": str(path), "text": text.strip()})
    return result
