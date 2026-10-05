"""Opt-in Hungarian Higgs TTS 3 benchmark using the native MLX backend.

Run this script with ``reader/.mlx_runtime/bin/python`` while Auris Studio is
stopped.  References remain local: the report stores hashes, never paths or
transcript text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time


READER_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = READER_DIR.parent
sys.path.insert(0, str(READER_DIR))


def _append_main_venv_packages() -> None:
    """Expose Torch/soundfile only for checkpoint loading and report output.

    MLX-Audio runs from its isolated environment.  Its Higgs codec loader uses
    Torch as a fallback reader for BF16 tensors, so reuse the already-installed
    package instead of installing a second multi-hundred-megabyte copy.
    """

    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    packages = READER_DIR / ".venv" / "lib" / version / "site-packages"
    if packages.is_dir():
        sys.path.append(str(packages))


_append_main_venv_packages()

from scripts.benchmark_higgs import CORPUS, CORPUS_VERSION, book_reference


DEFAULT_MODEL = REPO_DIR / "model_backup" / "Higgs-TTS-3-4B-MLX"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--reference", type=Path)
    source.add_argument("--book-id", type=int)
    parser.add_argument("--reference-text")
    parser.add_argument(
        "--reference-variant",
        choices=("original", "tight-gap"),
        default="original",
        help="Use a local, lossless-derived reference variant with --book-id.",
    )
    parser.add_argument(
        "--database", type=Path, default=READER_DIR / "data" / "reader.db"
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument(
        "--mode",
        choices=("sequential", "batch", "hybrid"),
        default="sequential",
        help=(
            "hybrid batches narration with the original reference and "
            "renders questions sequentially with the tight-gap variant"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-idle", action="store_true")
    args = parser.parse_args()

    if not args.confirm_idle:
        parser.error("Stop Auris first, then pass --confirm-idle.")
    if args.repeats < 1 or args.seed < 0:
        parser.error("repeats must be positive and seed nonnegative")
    original_reference = None
    question_reference = None
    if args.book_id is not None:
        try:
            args.reference, args.reference_text = book_reference(
                args.book_id, args.database
            )
        except (OSError, sqlite3.Error, ValueError) as exc:
            parser.error(str(exc))
        original_reference = args.reference
        tight_reference = (
            READER_DIR
            / "audio_cache"
            / "reference_variants"
            / f"book-{args.book_id}"
            / "tight-gap-24k-mono.wav"
        )
        if args.reference_variant == "tight-gap":
            args.reference = tight_reference
        if args.mode == "hybrid":
            args.reference = original_reference
            question_reference = tight_reference
    elif not args.reference_text:
        parser.error("--reference-text is required with --reference")
    elif args.reference_variant != "original":
        parser.error("--reference-variant requires --book-id")
    if args.mode == "hybrid" and args.book_id is None:
        parser.error("hybrid mode requires --book-id")
    if not args.reference.is_file():
        parser.error("Reference file does not exist")
    if question_reference is not None and not question_reference.is_file():
        parser.error("Question reference variant does not exist")
    if not args.model.is_dir():
        parser.error("MLX model view does not exist")
    if args.output.exists():
        parser.error("Output must be new; existing results are never overwritten")

    import mlx.core as mx
    import numpy as np
    from mlx_audio.audio_io import write as write_audio
    from mlx_audio.tts.utils import load
    from core.higgs_engine import HiggsTTSEngine

    args.output.mkdir(parents=True)
    prompt_builder = HiggsTTSEngine()
    prompts = [
        prompt_builder._prompt(text, None, 1.0, "hu", True) for text in CORPUS
    ]
    generation = {
        "temperature": args.temperature,
        "top_p": args.top_p if args.top_p > 0 else None,
        "top_k": args.top_k if args.top_k > 0 else None,
        "max_new_tokens": args.max_new_tokens,
        "seed": args.seed,
    }
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_DIR, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=REPO_DIR, text=True
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = "unknown", None

    report = {
        "schema": 1,
        "engine": "higgs-mlx",
        "corpus_version": CORPUS_VERSION,
        "corpus": CORPUS,
        "revision": revision,
        "dirty": dirty,
        "platform": platform.platform(),
        "model_config_sha256": hashlib.sha256(
            (args.model / "config.json").read_bytes()
        ).hexdigest(),
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "reference_text_sha256": hashlib.sha256(
            args.reference_text.encode()
        ).hexdigest(),
        "reference_variant": args.reference_variant,
        "generation": generation,
        "mode": args.mode,
        "language": "hu",
        "normalize_text": True,
        "prompts": prompts,
        "rows": [],
    }

    started = time.perf_counter()
    model = load(args.model)
    mx.eval(model.parameters())
    report["load_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    reference_codes = model.encode_reference_audio(str(args.reference.resolve()))
    mx.eval(reference_codes)
    report["reference_encode_seconds"] = time.perf_counter() - started
    question_reference_codes = None
    if question_reference is not None:
        started = time.perf_counter()
        question_reference_codes = model.encode_reference_audio(
            str(question_reference.resolve())
        )
        mx.eval(question_reference_codes)
        report["question_reference_encode_seconds"] = (
            time.perf_counter() - started
        )
        report["question_reference_sha256"] = hashlib.sha256(
            question_reference.read_bytes()
        ).hexdigest()
        report["question_reference_variant"] = "tight-gap"

    def record_result(repeat: int, index: int, result, elapsed: float) -> None:
        audio = np.asarray(result.audio, dtype=np.float32).reshape(-1)
        filename = f"{repeat + 1:02d}-{index + 1:02d}.wav"
        write_audio(args.output / filename, audio, result.sample_rate)
        duration = len(audio) / result.sample_rate
        row = {
            "repeat": repeat + 1,
            "sentence": index + 1,
            "wav": filename,
            "seconds": elapsed,
            "model_processing_seconds": result.processing_time_seconds,
            "audio_seconds": duration,
            "rtf": elapsed / duration if duration else None,
            "model_rtf": getattr(result, "real_time_factor", None),
            "peak_memory_gb": result.peak_memory_usage,
            "tokens": result.token_count,
            "first_request": repeat == 0 and index == 0,
        }
        report["rows"].append(row)
        print(json.dumps(row), flush=True)

    for repeat in range(args.repeats):
        if args.mode == "hybrid":
            narration = [
                (index, prompt)
                for index, prompt in enumerate(prompts)
                if not CORPUS[index].rstrip().endswith("?")
            ]
            questions = [
                (index, prompt)
                for index, prompt in enumerate(prompts)
                if CORPUS[index].rstrip().endswith("?")
            ]
            started = time.perf_counter()
            results = list(
                model.batch_generate(
                    texts=[prompt for _, prompt in narration],
                    ref_audio_codes=reference_codes,
                    ref_text=args.reference_text,
                    **generation,
                )
            )
            elapsed = time.perf_counter() - started
            report.setdefault("batch_wall_seconds", []).append(elapsed)
            for result in results:
                corpus_index = narration[int(result.sequence_idx)][0]
                record_result(repeat, corpus_index, result, elapsed)
            for corpus_index, prompt in questions:
                started = time.perf_counter()
                result = next(
                    model.generate(
                        text=prompt,
                        ref_audio_codes=question_reference_codes,
                        ref_text=args.reference_text,
                        **generation,
                    )
                )
                record_result(
                    repeat, corpus_index, result, time.perf_counter() - started
                )
        elif args.mode == "batch":
            started = time.perf_counter()
            results = list(
                model.batch_generate(
                    texts=prompts,
                    ref_audio_codes=reference_codes,
                    ref_text=args.reference_text,
                    **generation,
                )
            )
            elapsed = time.perf_counter() - started
            report.setdefault("batch_wall_seconds", []).append(elapsed)
            for result in results:
                record_result(repeat, int(result.sequence_idx), result, elapsed)
        else:
            for index, prompt in enumerate(prompts):
                started = time.perf_counter()
                result = next(
                    model.generate(
                        text=prompt,
                        ref_audio_codes=reference_codes,
                        ref_text=args.reference_text,
                        **generation,
                    )
                )
                record_result(repeat, index, result, time.perf_counter() - started)

    (args.output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
