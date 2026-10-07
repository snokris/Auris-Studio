"""Compare an original voice with additional same-speaker question references.

Run with ``reader/.mlx_runtime/bin/python`` when enough unified memory is free.
Each additional WAV must contain a naturally spoken question from the same speaker.
Audio and a report containing hashes (not private transcripts or paths) stay
under the Git-ignored ``reader/audio_cache`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time


READER_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = READER_DIR.parent
sys.path.insert(0, str(READER_DIR))
main_packages = (
    READER_DIR
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if main_packages.is_dir():
    sys.path.append(str(main_packages))

DEFAULT_MODEL = REPO_DIR / "model_backup" / "Higgs-TTS-3-4B-MLX"
CORPUS = (
    "Eljönnek vasárnap?",
    "Ha végeznek a költözéssel, eljönnek vasárnap?",
    "Jó?",
    "Elég?",
    "Mikor érkeznek?",
    "Eljönnek vasárnap.",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _transcript(path: Path, parser: argparse.ArgumentParser) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        parser.error(f"Cannot read transcript {path}: {exc}")
    if not text:
        parser.error(f"Transcript is empty: {path}")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--voice-id", type=int, help="Use a saved voice from the local reader database.")
    source.add_argument("--base-audio", type=Path)
    parser.add_argument("--base-text-file", type=Path)
    parser.add_argument("--database", type=Path, default=READER_DIR / "data" / "reader.db")
    parser.add_argument(
        "--question-audio", required=True, type=Path, action="append",
        help="Repeat for each same-speaker question WAV.",
    )
    question_source = parser.add_mutually_exclusive_group(required=True)
    question_source.add_argument(
        "--question-text-file", type=Path, action="append",
        help="Repeat in the same order as --question-audio.",
    )
    question_source.add_argument(
        "--question-text", action="append",
        help="Repeat in the same order as --question-audio.",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--text", action="append", help="Repeat to use a focused test corpus.")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    corpus = tuple(args.text) if args.text else CORPUS
    limit = args.limit if args.limit is not None else len(corpus)
    if args.seed < 0 or not 1 <= limit <= len(corpus):
        parser.error("Seed must be nonnegative and limit must fit the corpus.")
    if args.voice_id is not None:
        if args.base_text_file is not None:
            parser.error("--base-text-file cannot be combined with --voice-id.")
        try:
            with sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True) as conn:
                voice = conn.execute(
                    "SELECT ref_audio_path, ref_text FROM voices WHERE id=?",
                    (args.voice_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            parser.error(f"Cannot read saved voice: {exc}")
        if not voice or not voice[0] or not voice[1]:
            parser.error("Saved voice needs an audio reference and transcript.")
        args.base_audio = Path(voice[0])
        base_text = voice[1].strip()
    else:
        if args.base_text_file is None:
            parser.error("--base-audio needs --base-text-file.")
        base_text = _transcript(args.base_text_file, parser)
    question_texts = (
        [text.strip() for text in args.question_text]
        if args.question_text is not None
        else [_transcript(path, parser) for path in args.question_text_file]
    )
    if len(args.question_audio) != len(question_texts):
        parser.error("Each question WAV needs one matching transcript.")
    for path in (
        args.base_audio,
        *args.question_audio,
        *(args.question_text_file or []),
    ):
        if not path.is_file():
            parser.error(f"Input file does not exist: {path}")
    audio_paths = [args.base_audio.resolve()]
    audio_paths.extend(path.resolve() for path in args.question_audio)
    if len(set(audio_paths)) != len(audio_paths):
        parser.error("Every reference WAV file must be different.")
    if not args.model.is_dir():
        parser.error("Local Higgs/MLX model does not exist.")
    output = args.output.resolve()
    if not output.is_relative_to((READER_DIR / "audio_cache").resolve()):
        parser.error("Output must be inside reader/audio_cache.")
    if output.exists():
        parser.error("Output directory already exists; samples are never overwritten.")

    if not base_text or any("?" not in text for text in question_texts):
        parser.error("Each question transcript must contain a question mark.")

    import mlx.core as mx
    import numpy as np
    from mlx_audio.audio_io import write as write_audio
    from mlx_audio.tts.utils import load
    from core.higgs_engine import HiggsTTSEngine

    output.mkdir(parents=True)
    report = {
        "schema": 2,
        "model_config_sha256": _sha256(args.model / "config.json"),
        "base_audio_sha256": _sha256(args.base_audio),
        "base_text_sha256": hashlib.sha256(base_text.encode()).hexdigest(),
        "question_audio_sha256": [_sha256(path) for path in args.question_audio],
        "question_text_sha256": [
            hashlib.sha256(text.encode()).hexdigest() for text in question_texts
        ],
        "seed": args.seed,
        "corpus": corpus[:limit],
        "temperature": 0.8,
        "top_p": 0.95,
        "top_k": 50,
        "rows": [],
    }

    try:
        started = time.perf_counter()
        model = load(args.model)
        mx.eval(model.parameters())
        report["model_load_seconds"] = time.perf_counter() - started
        base_codes = model.encode_reference_audio(str(args.base_audio))
        question_codes = [
            model.encode_reference_audio(str(path)) for path in args.question_audio
        ]
        mx.eval(base_codes, *question_codes)
        prompt_builder = HiggsTTSEngine()

        for index, line in enumerate(corpus[:limit], start=1):
            prompt = prompt_builder._prompt(line, None, 1.0, "hu", True)
            for condition in ("base", "base-plus-question"):
                references = [base_codes]
                transcripts = [base_text]
                if condition == "base-plus-question":
                    references.extend(question_codes)
                    transcripts.extend(question_texts)
                started = time.perf_counter()
                result = next(
                    model.generate(
                        text=prompt,
                        ref_audio_codes_list=references,
                        ref_texts=transcripts,
                        seed=args.seed,
                        temperature=0.8,
                        top_p=0.95,
                        top_k=50,
                        max_new_tokens=1024,
                    )
                )
                filename = f"{index:02d}-{condition}.wav"
                audio = np.asarray(result.audio, dtype=np.float32).reshape(-1)
                write_audio(output / filename, audio, int(result.sample_rate))
                row = {
                    "corpus_index": index,
                    "condition": condition,
                    "wav": filename,
                    "generation_seconds": time.perf_counter() - started,
                    "audio_seconds": len(audio) / int(result.sample_rate),
                }
                report["rows"].append(row)
                print(json.dumps(row), flush=True)
    finally:
        (output / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
