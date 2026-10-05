"""Generate the shared private Hungarian benchmark corpus with OmniVoice."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.benchmark_higgs import CORPUS, CORPUS_VERSION, book_reference


PROSODY_CASES = (
    ("calm", "A reggeli fény lassan végigkúszott a szoba falán."),
    ("question", "Vajon visszatér még?"),
    ("exclamation", "Várj!"),
    ("urgent", "Hirtelen felpattant, és gyorsan az ajtóhoz rohant."),
    ("whisper", "„Ne mozdulj” – suttogta halkan."),
    ("sigh", "„Nem bírom tovább” – sóhajtott fáradtan."),
)


def benchmark_cases(suite):
    if suite == "basic":
        return [
            {"label": f"basic-{index + 1}", "source": text, "text": text,
             "speed": 1.0, "instruct": None, "clone_instruct": None}
            for index, text in enumerate(CORPUS)
        ]

    from core.enrichment import enrich_chapter

    cases = []
    for label, source in PROSODY_CASES:
        segments = enrich_chapter(
            source, {}, narrator_instruct="male, middle-aged, low pitch",
            single_narrator_mode=True,
        )
        if len(segments) != 1:
            raise RuntimeError(f"Prosody case {label!r} produced {len(segments)} segments")
        segment = segments[0]
        cases.append({
            "label": label, "source": source, "text": segment["enriched_text"],
            "speed": segment["speed"], "instruct": segment["instruct"],
            "clone_instruct": "whisper" if label == "whisper" else None,
        })
    return cases


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
    parser.add_argument("--num-step", type=int, default=16)
    parser.add_argument("--suite", choices=("basic", "prosody"), default="basic")
    parser.add_argument("--clone-instruct", choices=("off", "on"), default="off")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--output", type=Path, required=True, help="New private output directory")
    parser.add_argument("--confirm-idle", action="store_true", help="Confirm app is stopped and GPU is free")
    args = parser.parse_args()
    if not args.confirm_idle:
        parser.error("Stop Auris first, then pass --confirm-idle (loads a separate model).")
    if args.seed < 0 or args.num_step < 1:
        parser.error("seed must be nonnegative and num-step positive")
    if args.book_id is not None:
        try:
            args.reference, args.reference_text = book_reference(args.book_id, args.database)
        except Exception as exc:
            parser.error(str(exc))
    elif not args.reference_text:
        parser.error("--reference-text is required with --reference")
    if not args.reference.is_file():
        parser.error("Reference file does not exist")
    if args.output.exists():
        parser.error("Output must be new; existing results are never overwritten")

    import soundfile as sf
    import torch
    from core.tts_engine import SAMPLE_RATE, TTSEngine, apply_text_normalization

    args.output.mkdir(parents=True)
    engine = TTSEngine()
    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = "unknown", None
    cases = benchmark_cases(args.suite)
    report = {
        "schema": 1, "corpus_version": CORPUS_VERSION, "corpus": CORPUS,
        "revision": revision, "dirty": dirty, "platform": platform.platform(),
        "engine": "omnivoice", "suite": args.suite, "cases": cases,
        "clone_instruct": args.clone_instruct,
        "num_step": args.num_step, "seed": args.seed,
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "reference_text_sha256": hashlib.sha256(args.reference_text.encode()).hexdigest(),
        "language": "hu", "normalize_text": True, "speed": 1.0, "rows": [],
    }
    try:
        torch.manual_seed(args.seed)
        started = time.perf_counter()
        engine.load_sync()
        report["load_seconds"] = time.perf_counter() - started
        report["render_variant"] = getattr(engine, "_render_variant", "unknown")
        report["acceleration"] = engine.status().get("accel")
        report["prompts"] = [apply_text_normalization(case["text"], "hu") for case in cases]

        def synthesize(case):
            torch.manual_seed(args.seed)
            return engine._synthesize_audio(
                text=case["text"], instruct=(
                    case["clone_instruct"] if args.clone_instruct == "on" else case["instruct"]
                ),
                ref_audio=str(args.reference.resolve()),
                ref_text=args.reference_text, speed=case["speed"], num_step=args.num_step,
                language="hu", normalize_text=True,
                allow_clone_instruct=args.clone_instruct == "on",
            )

        for index, case in enumerate(cases):
            started = time.perf_counter()
            audio = synthesize(case)
            elapsed = time.perf_counter() - started
            filename = f"{index + 1:02d}.wav"
            sf.write(args.output / filename, audio, SAMPLE_RATE)
            duration = len(audio) / SAMPLE_RATE
            row = {"sentence": index + 1, "label": case["label"],
                   "speed": case["speed"], "wav": filename, "seconds": elapsed,
                   "audio_seconds": duration, "rtf": elapsed / duration if duration else None,
                   "first_request": index == 0}
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
