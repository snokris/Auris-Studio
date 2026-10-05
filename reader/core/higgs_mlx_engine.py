"""Native Apple Silicon Higgs TTS 3 backend with hybrid batching.

Ordinary narration uses MLX-Audio's batch path for throughput.  Questions are
rendered sequentially with a locally derived reference whose single long
internal pause is shortened; listening tests found that combination preserved
the most natural Hungarian question contour.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np
import soundfile as sf

from core.cache_identity import reference_identity
from core.higgs_engine import HiggsTTSEngine, _setting
from core.tts_engine import AUDIO_CACHE_DIR, SAMPLE_RATE, _write_audio_atomic


log = logging.getLogger(__name__)

MLX_MARKER = "AURIS_STUDIO_HIGGS_MLX_JSON:"
MLX_HYBRID_VERSION = 1
DEFAULT_MLX_REPO = "bosonai/higgs-tts-3-4b"
DEFAULT_MLX_BATCH_SIZE = 5
_QUESTION_END_RE = re.compile(
    r"\?[\s\"'”’»)\]]*(?:\[[^\]]+\]\s*)*$", re.UNICODE
)


def _is_question(text: str) -> bool:
    return bool(_QUESTION_END_RE.search(str(text or "").strip()))


def _parse_mlx_worker_response(line: str) -> dict | None:
    marker_at = line.find(MLX_MARKER)
    if marker_at < 0:
        return None
    payload = line[marker_at + len(MLX_MARKER):].lstrip()
    response, _ = json.JSONDecoder().raw_decode(payload)
    if not isinstance(response, dict):
        raise RuntimeError("Higgs MLX worker returned a non-object response")
    return response


def _question_reference_path(ref_audio: str) -> str:
    """Return a cached 24 kHz mono reference with one excessive pause reduced.

    The source is never modified.  Only the longest internal quiet run is
    shortened, by at most 660 ms, and only when it is at least 450 ms long.
    """
    identity = reference_identity(ref_audio)
    digest = hashlib.sha256(repr(identity).encode("utf-8")).hexdigest()
    directory = Path(AUDIO_CACHE_DIR) / "higgs_mlx_refs"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{digest}-tight-gap-24k-mono.wav"
    if output.is_file():
        return str(output)

    audio, sample_rate = sf.read(ref_audio, dtype="float32", always_2d=True)
    mono = np.asarray(audio.mean(axis=1), dtype=np.float32)
    if int(sample_rate) != SAMPLE_RATE:
        import librosa

        mono = np.asarray(
            librosa.resample(
                mono, orig_sr=int(sample_rate), target_sr=SAMPLE_RATE
            ),
            dtype=np.float32,
        )

    frame = int(0.020 * SAMPLE_RATE)
    hop = int(0.010 * SAMPLE_RATE)
    quiet_runs: list[tuple[int, int]] = []
    if mono.size >= frame:
        starts = np.arange(0, mono.size - frame + 1, hop)
        rms = np.array(
            [np.sqrt(np.mean(np.square(mono[start:start + frame])) + 1e-12)
             for start in starts],
            dtype=np.float32,
        )
        quiet = 20.0 * np.log10(np.maximum(rms, 1e-8)) < -42.0
        run_start = None
        for index, is_quiet in enumerate(quiet):
            if is_quiet and run_start is None:
                run_start = index
            elif not is_quiet and run_start is not None:
                quiet_runs.append((run_start, index))
                run_start = None
        if run_start is not None:
            quiet_runs.append((run_start, len(quiet)))

    margin = int(0.25 * SAMPLE_RATE)
    candidates: list[tuple[int, int]] = []
    for start_frame, end_frame in quiet_runs:
        start = start_frame * hop
        end = min(mono.size, end_frame * hop + frame)
        if (
            start >= margin
            and end <= mono.size - margin
            and end - start >= int(0.45 * SAMPLE_RATE)
        ):
            candidates.append((start, end))

    if candidates:
        gap_start, gap_end = max(candidates, key=lambda pair: pair[1] - pair[0])
        removable = max(0, gap_end - gap_start - int(0.14 * SAMPLE_RATE))
        remove = min(removable, int(0.66 * SAMPLE_RATE))
        if remove:
            cut_start = (gap_start + gap_end - remove) // 2
            cut_end = cut_start + remove
            fade = min(int(0.005 * SAMPLE_RATE), cut_start, mono.size - cut_end)
            if fade:
                mono[cut_start - fade:cut_start] *= np.linspace(
                    1.0, 0.0, fade, endpoint=False, dtype=np.float32
                )
                mono[cut_end:cut_end + fade] *= np.linspace(
                    0.0, 1.0, fade, endpoint=False, dtype=np.float32
                )
            mono = np.concatenate((mono[:cut_start], mono[cut_end:]))

    _write_audio_atomic(str(output), mono, SAMPLE_RATE)
    return str(output)


class HiggsMLXEngine(HiggsTTSEngine):
    """Higgs TTS 3 using MLX-Audio in an isolated worker process."""

    engine_name = "higgs"
    engine_key = "higgs-mlx"

    def _source(self) -> tuple[str, bool]:
        source = str(_setting("higgs_mlx_model_source", "download")).lower()
        if source == "local":
            default = (
                Path(__file__).resolve().parents[2]
                / "model_backup"
                / "Higgs-TTS-3-4B-MLX"
            )
            path = str(_setting("higgs_mlx_model_path", str(default)) or default)
            return path, True
        repo = str(
            _setting("higgs_mlx_model_repo", DEFAULT_MLX_REPO)
            or DEFAULT_MLX_REPO
        )
        return repo, False

    def status(self) -> dict:
        source, local_only = self._source()
        base = {
            "engine": self.engine_name,
            "backend": "mlx-hybrid",
            "model": self._resolved_model or source,
        }
        if self._error:
            return {**base, "state": "error", "message": self._error}
        if self._ready:
            return {
                **base,
                "state": "ready",
                "generating": self._generating.is_set(),
                "accel": {
                    "effective": "mlx-hybrid",
                    "message": "Higgs MLX: batch narration + question reference",
                },
            }
        if self._loading:
            return {**base, "state": "loading"}
        return {
            **base,
            "state": "not_loaded",
            "model_path": source,
            "model_exists": os.path.isdir(source) if local_only else True,
        }

    def _load(self) -> None:
        with self._lock:
            if self._ready:
                return
            self._loading = True
            self._error = None
        try:
            source, local_only = self._source()
            if local_only and not os.path.isdir(source):
                raise FileNotFoundError(
                    f"Higgs MLX model not found at: {source}. Configure it in Settings."
                )
            runtime = Path(__file__).resolve().parents[1] / ".mlx_runtime"
            python = runtime / "bin" / "python"
            if not python.is_file():
                raise RuntimeError(
                    "The isolated MLX runtime is missing. Run: bash reader/setup.sh"
                )
            worker_path = Path(__file__).with_name("higgs_mlx_worker.py")
            self._worker = subprocess.Popen(
                [str(python), "-u", str(worker_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                encoding="utf-8",
            )
            response = self._rpc_raw({"command": "load", "source": source})
            if not response.get("ok"):
                raise RuntimeError(
                    response.get("error") or "Higgs MLX worker failed to start"
                )
            if self._cancel_load.is_set():
                self.unload()
                return
            self._sample_rate = int(response.get("sample_rate", SAMPLE_RATE))
            self._load_metadata = dict(response)
            self._resolved_model = source
            self._ready = True
            self.model = self._worker
            log.info(
                "Higgs MLX ready (source=%s, load=%.2fs).",
                source,
                float(response.get("load_seconds", 0.0)),
            )
        except Exception as exc:
            self._error = str(exc)
            self.model = None
            if self._worker is not None:
                self._worker.terminate()
                self._worker = None
            log.error("Failed to load Higgs MLX: %s", exc)
        finally:
            self._loading = False

    def _rpc_raw(self, payload: dict) -> dict:
        worker = self._worker
        if worker is None or worker.stdin is None or worker.stdout is None:
            raise RuntimeError("Higgs MLX worker is not running")
        with self._stdin_lock:
            worker.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
            worker.stdin.flush()
        while True:
            line = worker.stdout.readline()
            if not line:
                raise RuntimeError(
                    f"Higgs MLX worker exited unexpectedly (code {worker.poll()})"
                )
            response = _parse_mlx_worker_response(line)
            if response is not None:
                return response
            log.info("Higgs MLX worker: %s", line.rstrip())

    def _cache_key_for_item(
        self, item: dict, question: bool, question_reference: str | None
    ) -> str:
        normalize = item.get("normalize_text")
        if normalize is None:
            normalize = bool(_setting("normalize_text", True))
        base = HiggsTTSEngine.cache_key(
            item["text"],
            item.get("instruct"),
            item.get("ref_audio"),
            float(item.get("speed") or 1.0),
            ref_text=item.get("ref_text"),
            language=item.get("language"),
            normalize_text=bool(normalize),
            render_variant=f"mlx-hybrid-v{MLX_HYBRID_VERSION}",
        )
        source, _ = self._source()
        payload = (
            f"{base}|mlx_model={source}|question={int(question)}|"
            f"qref={reference_identity(question_reference)!r}|"
            f"batch={self._batch_size()}"
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _batch_size() -> int:
        try:
            return max(
                1,
                min(
                    int(_setting("higgs_mlx_batch_size", DEFAULT_MLX_BATCH_SIZE)),
                    8,
                ),
            )
        except (TypeError, ValueError):
            return DEFAULT_MLX_BATCH_SIZE

    @staticmethod
    def _normalize_enabled(item: dict) -> bool:
        value = item.get("normalize_text")
        return (
            bool(_setting("normalize_text", True))
            if value is None
            else bool(value)
        )

    def _prompt_for_item(self, item: dict) -> str:
        return self._prompt(
            item["text"],
            item.get("instruct"),
            float(item.get("speed") or 1.0),
            item.get("language"),
            self._normalize_enabled(item),
        )

    def _generation_payload(self) -> dict:
        values = self._generation_settings()
        if int(values.get("seed", -1)) < 0:
            values["seed"] = None
        return values

    def _store_worker_output(
        self, temp_path: str, cache_key: str, cache_hit: bool = False
    ) -> dict:
        audio, sample_rate = sf.read(temp_path, dtype="float32")
        cache_path = self.cache_path(cache_key)
        _write_audio_atomic(
            cache_path, np.asarray(audio, dtype=np.float32), sample_rate
        )
        return {
            "audio_path": cache_path,
            "duration_sec": len(audio) / float(sample_rate),
            "cache_hit": cache_hit,
            "cache_key": cache_key,
        }

    @staticmethod
    def _temp_wav() -> str:
        handle, path = tempfile.mkstemp(
            suffix=".wav", prefix="auris-studio-higgs-mlx-out-"
        )
        os.close(handle)
        return path

    def _run_batch(self, entries: list[dict]) -> list[dict]:
        temp_paths = [self._temp_wav() for _ in entries]
        try:
            payload_items = [
                {
                    "prompt": self._prompt_for_item(entry["item"]),
                    "reference_audio": entry["item"].get("ref_audio"),
                    "reference_text": entry["item"].get("ref_text"),
                    "output_path": temp_path,
                }
                for entry, temp_path in zip(entries, temp_paths)
            ]
            self._generating.set()
            try:
                with self._lock:
                    response = self._rpc_raw(
                        {
                            "command": "batch",
                            "items": payload_items,
                            "generation": self._generation_payload(),
                        }
                    )
            finally:
                self._generating.clear()
            if not response.get("ok"):
                raise RuntimeError(response.get("error") or "MLX batch failed")
            return [
                self._store_worker_output(path, entry["cache_key"])
                for entry, path in zip(entries, temp_paths)
            ]
        finally:
            for path in temp_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _run_question(self, entry: dict) -> dict:
        temp_path = self._temp_wav()
        try:
            item = entry["item"]
            self._generating.set()
            try:
                with self._lock:
                    response = self._rpc_raw(
                        {
                            "command": "generate",
                            "prompt": self._prompt_for_item(item),
                            "reference_audio": entry["question_reference"],
                            "reference_text": item.get("ref_text"),
                            "output_path": temp_path,
                            "generation": self._generation_payload(),
                        }
                    )
            finally:
                self._generating.clear()
            if not response.get("ok"):
                raise RuntimeError(response.get("error") or "MLX question failed")
            return self._store_worker_output(temp_path, entry["cache_key"])
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def generate(
        self,
        text: str,
        instruct: str | None = None,
        ref_audio: str | None = None,
        ref_text: str | None = None,
        speed: float = 1.0,
        num_step: int | None = None,
        language: str | None = None,
        normalize_text: bool | None = None,
    ) -> dict:
        return self.generate_many(
            [
                {
                    "text": text,
                    "instruct": instruct,
                    "ref_audio": ref_audio,
                    "ref_text": ref_text,
                    "speed": speed,
                    "language": language,
                    "normalize_text": normalize_text,
                }
            ],
            num_step=num_step,
        )[0]

    def generate_many(
        self,
        items: list[dict],
        num_step: int | None = None,
        batch_size: int | None = None,
        on_item=None,
        on_status=None,
    ) -> list[dict]:
        del num_step
        if not self._ready or self._worker is None:
            self._wait_until_ready()
        if not self._ready or self._worker is None:
            raise RuntimeError(
                "Higgs MLX is not loaded. " + (self._error or "Load it first.")
            )

        outputs: list[dict | None] = [None] * len(items)
        narration_groups: dict[tuple, list[dict]] = defaultdict(list)
        questions: list[dict] = []
        hybrid = bool(_setting("higgs_mlx_hybrid_questions", True))

        for index, item in enumerate(items):
            question = hybrid and _is_question(item.get("text") or "")
            question_reference = None
            if question and item.get("ref_audio"):
                question_reference = _question_reference_path(item["ref_audio"])
            cache_key = self._cache_key_for_item(
                item, question, question_reference
            )
            cache_path = self.cache_path(cache_key)
            if os.path.isfile(cache_path):
                audio, sample_rate = sf.read(cache_path, dtype="float32")
                result = {
                    "audio_path": cache_path,
                    "duration_sec": len(audio) / float(sample_rate),
                    "cache_hit": True,
                    "cache_key": cache_key,
                }
                outputs[index] = result
                if on_item is not None:
                    on_item(index, result)
                continue

            entry = {
                "index": index,
                "item": item,
                "cache_key": cache_key,
                "question_reference": question_reference,
            }
            if question:
                questions.append(entry)
            else:
                group_key = (
                    reference_identity(item.get("ref_audio")),
                    str(item.get("ref_text") or ""),
                )
                narration_groups[group_key].append(entry)

        limit = max(1, min(int(batch_size or self._batch_size()), 8))
        batch_number = 0
        total_batches = sum(
            (len(group) + limit - 1) // limit
            for group in narration_groups.values()
        )
        for group in narration_groups.values():
            for start in range(0, len(group), limit):
                chunk = group[start:start + limit]
                batch_number += 1
                if on_status is not None:
                    on_status(
                        f"MLX narration batch {batch_number}/{total_batches} "
                        f"({len(chunk)} utterances)…"
                    )
                results = self._run_batch(chunk)
                for entry, result in zip(chunk, results):
                    outputs[entry["index"]] = result
                    if on_item is not None:
                        on_item(entry["index"], result)

        for question_number, entry in enumerate(questions, 1):
            if on_status is not None:
                on_status(
                    f"MLX question {question_number}/{len(questions)}…"
                )
            result = self._run_question(entry)
            outputs[entry["index"]] = result
            if on_item is not None:
                on_item(entry["index"], result)

        missing = [index for index, result in enumerate(outputs) if result is None]
        if missing:
            raise RuntimeError(f"Higgs MLX left {len(missing)} items unresolved")
        return outputs  # type: ignore[return-value]
