"""Isolated MLX-Audio worker for Higgs TTS 3 on Apple Silicon.

MLX-Audio needs its own dependency set, so this worker is launched with
``reader/.mlx_runtime/bin/python`` and communicates through framed JSON lines.
Audio stays on disk; no waveform or private reference text is serialized into
logs.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time


READER_DIR = Path(__file__).resolve().parents[1]
MARKER = "AURIS_STUDIO_HIGGS_MLX_JSON:"


def _append_main_venv_packages() -> None:
    """Reuse the main venv's Torch/soundfile for codec checkpoint loading."""
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    packages = READER_DIR / ".venv" / "lib" / version / "site-packages"
    if packages.is_dir():
        sys.path.append(str(packages))


_append_main_venv_packages()

import mlx.core as mx
import numpy as np
from mlx_audio.audio_io import write as write_audio
from mlx_audio.tts.utils import load


_model = None
_reference_cache: dict[tuple[str, int, int], object] = {}


def _reply(payload: dict) -> None:
    print(MARKER + json.dumps(payload, ensure_ascii=True), flush=True)


def _reference_identity(path: str) -> tuple[str, int, int]:
    resolved = str(Path(path).resolve())
    stat = Path(resolved).stat()
    return resolved, int(stat.st_size), int(stat.st_mtime_ns)


def _reference_codes(path: str | None):
    if not path:
        return None
    identity = _reference_identity(path)
    cached = _reference_cache.get(identity)
    if cached is not None:
        return cached
    codes = _model.encode_reference_audio(identity[0])
    mx.eval(codes)
    _reference_cache[identity] = codes
    while len(_reference_cache) > 4:
        _reference_cache.pop(next(iter(_reference_cache)))
    return codes


def _generation(request: dict) -> dict:
    values = dict(request.get("generation") or {})
    seed = values.get("seed")
    if seed is None or int(seed) < 0:
        values["seed"] = None
    return values


def _write_result(result, output_path: str) -> dict:
    audio = np.asarray(result.audio, dtype=np.float32).reshape(-1)
    write_audio(output_path, audio, int(result.sample_rate))
    return {
        "sample_rate": int(result.sample_rate),
        "samples": int(audio.size),
        "processing_seconds": float(result.processing_time_seconds),
        "peak_memory_gb": float(result.peak_memory_usage),
        "tokens": int(result.token_count),
    }


def _load_model(request: dict) -> dict:
    global _model
    source = str(request["source"])
    started = time.perf_counter()
    _model = load(source)
    mx.eval(_model.parameters())
    return {
        "ok": True,
        "event": "ready",
        "sample_rate": int(_model.sample_rate),
        "load_seconds": time.perf_counter() - started,
        "device": "metal",
        "dtype": "mlx",
    }


def _generate_one(request: dict) -> dict:
    references = request.get("references")
    if references:
        codes = [_reference_codes(ref["audio"]) for ref in references]
        result = next(
            _model.generate(
                text=request["prompt"],
                ref_audio_codes_list=codes,
                ref_texts=[ref["text"] for ref in references],
                **_generation(request),
            )
        )
    else:
        codes = _reference_codes(request.get("reference_audio"))
        result = next(
            _model.generate(
                text=request["prompt"],
                ref_audio_codes=codes,
                ref_text=request.get("reference_text"),
                **_generation(request),
            )
        )
    return {"ok": True, "result": _write_result(result, request["output_path"])}


def _generate_batch(request: dict) -> dict:
    items = list(request.get("items") or [])
    if not items:
        return {"ok": True, "results": []}
    codes = _reference_codes(items[0].get("reference_audio"))
    generated = list(
        _model.batch_generate(
            texts=[item["prompt"] for item in items],
            ref_audio_codes=codes,
            ref_text=items[0].get("reference_text"),
            **_generation(request),
        )
    )
    results = [None] * len(items)
    for result in generated:
        index = int(result.sequence_idx)
        results[index] = _write_result(result, items[index]["output_path"])
    if any(result is None for result in results):
        raise RuntimeError("MLX batch did not return every requested sequence")
    return {"ok": True, "results": results}


def _dispatch(request: dict) -> dict:
    command = request.get("command")
    if command == "load":
        return _load_model(request)
    if command == "shutdown":
        return {"ok": True, "event": "shutdown"}
    if _model is None:
        raise RuntimeError("MLX Higgs model is not loaded")
    if command == "generate":
        return _generate_one(request)
    if command == "batch":
        return _generate_batch(request)
    raise ValueError(f"Unknown command: {command}")


def main() -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = _dispatch(request)
        except Exception as exc:
            response = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        _reply(response)
        if response.get("event") == "shutdown":
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
