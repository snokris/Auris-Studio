import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from core.question_references import load_question_references, question_reference_sidecar


class QuestionReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "voice.wav"
        self.extra = self.root / "question.wav"
        self.base.write_bytes(b"base WAV for identity test")
        self.extra.write_bytes(b"question WAV for identity test")
        self.sidecar = question_reference_sidecar(str(self.base))
        self.config = {
            "schema": 1,
            "base_sha256": hashlib.sha256(self.base.read_bytes()).hexdigest(),
            "references": [{
                "file": self.extra.name,
                "text": "Eljönnek?",
                "sha256": hashlib.sha256(self.extra.read_bytes()).hexdigest(),
            }],
        }

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.sidecar.write_text(json.dumps(self.config), encoding="utf-8")

    def test_no_sidecar_keeps_existing_voice_path(self):
        self.assertIsNone(load_question_references(str(self.base), "Alapszöveg."))

    def test_returns_base_then_question_in_order(self):
        self.save()
        self.assertEqual(
            load_question_references(str(self.base), "Alapszöveg."),
            [
                {"audio": str(self.base.resolve()), "text": "Alapszöveg."},
                {"audio": str(self.extra.resolve()), "text": "Eljönnek?"},
            ],
        )

    def test_changed_base_is_not_silently_conditioned(self):
        self.save()
        self.base.write_bytes(b"new voice")
        with self.assertRaisesRegex(ValueError, "base voice WAV changed"):
            load_question_references(str(self.base), "Alapszöveg.")

    def test_missing_or_unsafe_question_wav_fails(self):
        self.config["references"][0]["file"] = "../other.wav"
        self.save()
        with self.assertRaisesRegex(ValueError, "Invalid question WAV"):
            load_question_references(str(self.base), "Alapszöveg.")
        self.config["references"][0]["file"] = "missing.wav"
        self.save()
        with self.assertRaisesRegex(ValueError, "missing or unsafe"):
            load_question_references(str(self.base), "Alapszöveg.")


if __name__ == "__main__":
    unittest.main()
