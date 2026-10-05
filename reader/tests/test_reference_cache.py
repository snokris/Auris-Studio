import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch

from core.cache_identity import render_identity
from core.higgs_engine import HiggsTTSEngine
from core.higgs_worker import ReferenceCodeCache
from core.tts_engine import TTSEngine


class FakeModel:
    def __init__(self):
        self.calls = 0

    def generate_speech(self, prompt, tokenizer, reference_codes=None):
        pass

    def _encode_reference(self, audio, sample_rate):
        self.calls += 1
        assert not torch.is_grad_enabled()
        return torch.tensor([[self.calls]])


class ReferenceCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "voice.wav")
        sf.write(self.path, np.zeros(2400), 24000)

    def test_hit_edit_and_model_isolation(self):
        model = FakeModel()
        cache = ReferenceCodeCache(model)
        first = cache.get(self.path)
        self.assertIs(first, cache.get(self.path))
        self.assertEqual(first.device.type, "cpu")
        self.assertEqual(model.calls, 1)
        sf.write(self.path, np.ones(4800), 24000)
        self.assertIsNot(first, cache.get(self.path))
        self.assertEqual(model.calls, 2)
        ReferenceCodeCache(FakeModel()).get(self.path)
        self.assertEqual(model.calls, 2)

    def test_lru_eviction(self):
        model = FakeModel()
        cache = ReferenceCodeCache(model, limit=2)
        paths = []
        for i in range(3):
            path = os.path.join(self.tmp.name, f"{i}.wav")
            sf.write(path, np.zeros(100), 24000)
            paths.append(path)
        cache.get(paths[0])
        cache.get(paths[1])
        cache.get(paths[0])
        cache.get(paths[2])
        cache.get(paths[1])
        self.assertEqual(model.calls, 4)
        self.assertEqual(len(cache.entries), 2)

    def test_fallback_and_disabled_cache(self):
        self.assertIsNone(ReferenceCodeCache(object()).get("missing"))
        with patch.dict(os.environ, {"AURIS_STUDIO_HIGGS_REFERENCE_CACHE": "0"}):
            self.assertIsNone(ReferenceCodeCache(FakeModel()).get("missing"))

    def test_missing_reference_raises(self):
        with self.assertRaises(FileNotFoundError):
            ReferenceCodeCache(FakeModel()).get("/missing/reference.wav")

    def test_encode_failure_is_not_cached(self):
        model = FakeModel()
        cache = ReferenceCodeCache(model)
        with patch.object(model, "_encode_reference", side_effect=RuntimeError("encode failed")):
            with self.assertRaisesRegex(RuntimeError, "encode failed"):
                cache.get(self.path)
        self.assertFalse(cache.entries)
        self.assertIsNotNone(cache.get(self.path))

    def test_benchmark_repeats_bypass_audio_cache(self):
        from scripts.benchmark_higgs import CORPUS, measure
        from unittest.mock import Mock

        synthesize = Mock(return_value=np.zeros(24))
        with patch("scripts.benchmark_higgs.time.perf_counter", side_effect=range(8)):
            rows = list(measure(synthesize, ["Egy.", "Kettő."], 2))
        self.assertEqual(synthesize.call_count, 4)
        self.assertEqual([(r[0], r[1]) for r in rows], [(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertTrue(all(r[3] == 1 for r in rows))
        question_samples = [sample for sample in CORPUS if "?" in sample]
        self.assertTrue(question_samples)
        self.assertTrue(all(sample.rstrip().endswith("?") for sample in question_samples))

    def test_benchmark_reads_book_reference_without_cli_secret(self):
        import sqlite3
        from scripts.benchmark_higgs import book_reference

        database = os.path.join(self.tmp.name, "reader.db")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE books (id INTEGER, narrator_ref_audio_path TEXT, narrator_ref_text TEXT)"
            )
            connection.execute(
                "INSERT INTO books VALUES (7, ?, ?)", (self.path, "Pontos átirat.")
            )
        path, transcript = book_reference(7, database)
        self.assertEqual(path, __import__('pathlib').Path(self.path))
        self.assertEqual(transcript, "Pontos átirat.")

    def test_omnivoice_benchmark_uses_shared_corpus(self):
        from scripts import benchmark_higgs, benchmark_omnivoice

        self.assertIs(benchmark_omnivoice.CORPUS, benchmark_higgs.CORPUS)
        self.assertEqual(
            benchmark_omnivoice.CORPUS_VERSION, benchmark_higgs.CORPUS_VERSION
        )

    def test_synthesis_reuses_prepared_file_and_keeps_protocol(self):
        with patch("core.higgs_engine.AUDIO_CACHE_DIR", self.tmp.name):
            engine = HiggsTTSEngine()
            engine._ready = True
            engine._worker = object()
            requests = []
            def rpc(request):
                requests.append(request)
                sf.write(request["output_path"], np.zeros(2400), 24000)
                return {"ok": True}
            with patch.object(engine, "_rpc_raw", side_effect=rpc):
                for _ in range(2):
                    audio = engine._synthesize("Teszt.", None, self.path, "Minta.", 1.0, "hu", True)
                    self.assertEqual(len(audio), 2400)
            self.assertEqual(requests[0]["reference_audio"], requests[1]["reference_audio"])
            self.assertTrue(os.path.isfile(requests[0]["reference_audio"]))
            self.assertEqual(requests[0]["reference_text"], "Minta.")
            self.assertFalse(os.path.exists(requests[0]["output_path"]))
            self.assertFalse(engine._generating.is_set())

    def test_prepared_short_reference_reused_and_invalidated(self):
        with patch("core.higgs_engine.AUDIO_CACHE_DIR", self.tmp.name):
            engine = HiggsTTSEngine()
            prepared = engine._prepared_reference(self.path)
            self.assertNotEqual(prepared, self.path)
            self.assertGreaterEqual(sf.info(prepared).duration, 4)
            with patch("core.higgs_engine.sf.read", side_effect=AssertionError("read again")):
                self.assertEqual(engine._prepared_reference(self.path), prepared)
            sf.write(self.path, np.zeros(4800), 24000)
            self.assertNotEqual(engine._prepared_reference(self.path), prepared)

    def test_audio_keys_separate_reference_and_renderer(self):
        for engine in (TTSEngine, HiggsTTSEngine):
            with self.subTest(engine=engine.__name__):
                def key(variant):
                    return engine.cache_key("Árvíztűrő 12.", None, self.path, 1.0,
                                            language="hu", render_variant=variant)
                first = key("mps/bfloat16")
                self.assertNotEqual(first, key("mps/float32"))
                sf.write(self.path, np.zeros(sf.info(self.path).frames + 1), 24000)
                self.assertNotEqual(first, key("mps/bfloat16"))

    def test_mps_defaults_are_engine_specific(self):
        with patch("torch.cuda.is_available", return_value=False), patch(
            "torch.backends.mps.is_available", return_value=True
        ), patch.dict(os.environ, {"AURIS_STUDIO_HIGGS_MPS_DTYPE": "", "AURIS_STUDIO_MPS_DTYPE": ""}):
            self.assertEqual(render_identity("higgs"), "mps/bfloat16")
            self.assertEqual(render_identity("omnivoice"), "mps/float32")
            with patch.dict(os.environ, {"AURIS_STUDIO_HIGGS_MPS_DTYPE": "fp32"}):
                self.assertEqual(render_identity("higgs"), "mps/float32")


if __name__ == "__main__":
    unittest.main()
