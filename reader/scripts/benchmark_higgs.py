"""Opt-in local Hungarian Higgs benchmark; never edits books or settings."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CORPUS_VERSION = 2
CORPUS = (
    "A reggeli fény lassan végigkúszott a szoba falán. Odakint csendesen esett az eső.",
    "Árvíztűrő tükörfúrógép. A hosszú ő és ű tisztán hallatszott a felvételen.",
    "1932. március 5-én 12 ember érkezett a faluba. A 932. oldalon találták meg a választ.",
    "A jegy 3500 Ft volt, a vonat 7.30-kor indult. Három és fél órát utaztunk.",
    # Keep the question final in its request, like the real single-narrator
    # segmenter does. Following narration would suppress the ending contour.
    "Vajon visszatér még?",
)


def book_reference(book_id, database_path):
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT narrator_ref_audio_path, narrator_ref_text FROM books WHERE id=?",
            (book_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Book {book_id} does not exist")
    path, transcript = row
    if not path or not transcript:
        raise ValueError(f"Book {book_id} has no complete narrator reference")
    return Path(path), transcript


def measure(synthesize, texts, repeats):
    """Time complete worker RPC, including audio return, without WAV cache."""
    for repeat in range(repeats):
        for index, text in enumerate(texts):
            start = time.perf_counter()
            audio = synthesize(text)
            yield repeat, index, audio, time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--reference", type=Path)
    source.add_argument("--book-id", type=int, help="Read narrator reference privately from reader.db")
    parser.add_argument("--reference-text")
    parser.add_argument(
        "--database", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "reader.db",
    )
    parser.add_argument("--reference-cache", choices=("on", "off"), default="on")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--output", type=Path, required=True, help="New private output directory")
    parser.add_argument("--confirm-idle", action="store_true", help="Confirm app is stopped and GPU is free")
    args = parser.parse_args()
    if not args.confirm_idle:
        parser.error("Stop Auris first, then pass --confirm-idle (loads a separate model).")
    if args.repeats < 1 or args.seed < 0:
        parser.error("repeats must be positive and seed nonnegative")
    if args.book_id is not None:
        try:
            args.reference, args.reference_text = book_reference(args.book_id, args.database)
        except (OSError, sqlite3.Error, ValueError) as exc:
            parser.error(str(exc))
    elif not args.reference_text:
        parser.error("--reference-text is required with --reference")
    if not args.reference.is_file():
        parser.error("Reference file does not exist")
    if args.output.exists():
        parser.error("Output must be new; existing results are never overwritten")
    os.environ["AURIS_STUDIO_HIGGS_REFERENCE_CACHE"] = "1" if args.reference_cache == "on" else "0"

    import soundfile as sf
    from core.higgs_engine import HiggsTTSEngine

    args.output.mkdir(parents=True)
    engine = HiggsTTSEngine()
    generation = engine._generation_settings()
    generation["seed"] = args.seed
    engine._generation_settings = lambda: dict(generation)
    try:
        root = Path(__file__).resolve().parents[2]
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = "unknown", None
    report = {
        "schema": 1, "corpus_version": CORPUS_VERSION, "corpus": CORPUS,
        "revision": revision, "dirty": dirty, "platform": platform.platform(),
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "reference_text_sha256": hashlib.sha256(args.reference_text.encode()).hexdigest(),
        "reference_cache": args.reference_cache, "generation": generation,
        "language": "hu", "normalize_text": True, "speed": 1.0, "rows": [],
    }
    try:
        started = time.perf_counter()
        engine.load_sync()
        report["load_seconds"] = time.perf_counter() - started
        report["worker"] = engine._load_metadata
        report["prompts"] = [engine._prompt(t, None, 1.0, "hu", True) for t in CORPUS]
        def synthesize(text):
            return engine._synthesize(
                text, None, str(args.reference.resolve()), args.reference_text, 1.0, "hu", True
            )
        for repeat, index, audio, elapsed in measure(synthesize, CORPUS, args.repeats):
            filename = f"{repeat + 1:02d}-{index + 1:02d}.wav"
            sf.write(args.output / filename, audio, engine._sample_rate)
            duration = len(audio) / engine._sample_rate
            row = {"repeat": repeat + 1, "sentence": index + 1, "wav": filename,
                   "seconds": elapsed, "audio_seconds": duration,
                   "rtf": elapsed / duration if duration else None,
                   "first_request": repeat == 0 and index == 0}
            report["rows"].append(row)
            print(json.dumps(row), flush=True)
    finally:
        try:
            (args.output / "results.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        finally:
            engine.unload()


if __name__ == "__main__":
    main()
