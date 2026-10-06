"""Generate the eight Hungarian voice-candidate lines without a voice reference.

Run with reader/.mlx_runtime/bin/python while Auris Studio is stopped. This is
the Higgs model's unconditioned voice, not a selectable built-in speaker.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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

CORPUS = (
    "A reggeli fény lassan végigkúszott a szoba falán. Odakint csendesen esett az eső.",
    "Ősszel a sűrű fűben tűnődve ült a fiú, miközben Győr fölött hűvös szél fújt.",
    "1932. március 5-én 12 ember érkezett a faluba. A 932. oldalon találták meg a választ.",
    "A jegy 3500 Ft volt, a vonat 7.30-kor indult. A következő járat 7:45-kor érkezik.",
    "Vajon visszatér még?",
    "Megérkezik a vonat este 7:30-kor?",
    "Végre megérkeztél! Már azt hittem, soha többé nem látlak.",
    "A szék üres maradt mellette. Halkan becsukta a könyvet, és sokáig nem szólt.",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--model", type=Path, default=REPO_DIR / "model_backup" / "Higgs-TTS-3-4B-MLX"
    )
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--confirm-idle", action="store_true")
    args = parser.parse_args()
    if not args.confirm_idle:
        parser.error("Stop Auris Studio first and pass --confirm-idle.")
    if args.seed < 0:
        parser.error("Seed must be nonnegative.")
    if not args.model.is_dir():
        parser.error("The local Higgs/MLX model does not exist.")
    if args.output.exists():
        parser.error("Output directory must not already exist.")

    import mlx.core as mx
    import numpy as np
    from mlx_audio.audio_io import write as write_audio
    from mlx_audio.tts.utils import load
    from core.higgs_engine import HiggsTTSEngine

    prompts = [HiggsTTSEngine()._prompt(line, None, 1.0, "hu", True) for line in CORPUS]
    generation = {
        "temperature": 0.8,
        "top_p": 0.95,
        "top_k": 50,
        "max_new_tokens": 1024,
        "seed": args.seed,
    }
    args.output.mkdir(parents=True)
    report = {
        "engine": "higgs-mlx",
        "voice": "unconditioned; no reference or voice preset",
        "corpus": CORPUS,
        "prompts": prompts,
        "generation": generation,
        "rows": [],
    }
    try:
        started = time.perf_counter()
        model = load(args.model)
        mx.eval(model.parameters())
        report["load_seconds"] = time.perf_counter() - started

        montage = []
        for index, prompt in enumerate(prompts, start=1):
            started = time.perf_counter()
            result = next(model.generate(text=prompt, **generation))
            elapsed = time.perf_counter() - started
            samples = np.asarray(result.audio, dtype=np.float32).reshape(-1)
            filename = f"{index:02d}.wav"
            write_audio(args.output / filename, samples, result.sample_rate)
            montage.append(samples)
            if index != len(prompts):
                montage.append(np.zeros(round(result.sample_rate * 0.8), dtype=np.float32))
            row = {
                "sentence": index,
                "wav": filename,
                "seconds": elapsed,
                "audio_seconds": len(samples) / result.sample_rate,
            }
            report["rows"].append(row)
            print(json.dumps(row), flush=True)

        write_audio(args.output / "all-8.wav", np.concatenate(montage), model.sample_rate)
    finally:
        (args.output / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
