import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

from core.higgs_mlx_engine import (
    HiggsMLXEngine,
    MLX_MARKER,
    _is_question,
    _parse_mlx_worker_response,
    _question_reference_path,
)


class HiggsMLXHelpersTests(unittest.TestCase):
    def test_question_detection_accepts_quotes_and_enrichment_tags(self):
        for text in ('Visszatér még?', '„Visszatér még?”', 'Visszatér? [question-ei]'):
            self.assertTrue(_is_question(text), text)
        self.assertFalse(_is_question('Visszatért.'))

    def test_worker_response_parser_ignores_progress_prefix(self):
        payload = {"ok": True, "sample_rate": 24000}
        line = "loading 100% " + MLX_MARKER + json.dumps(payload) + "\r"
        self.assertEqual(_parse_mlx_worker_response(line), payload)

    def test_question_reference_shortens_only_a_long_internal_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.wav'
            sample_rate = 48_000
            tone = 0.2 * np.sin(
                2 * np.pi * 220 * np.arange(sample_rate) / sample_rate
            ).astype(np.float32)
            mono = np.concatenate((tone, np.zeros(int(0.8 * sample_rate)), tone))
            stereo = np.column_stack((mono, mono))
            sf.write(source, stereo, sample_rate)
            original = source.read_bytes()

            with patch(
                'core.higgs_mlx_engine.AUDIO_CACHE_DIR', str(root / 'cache')
            ):
                derived = Path(_question_reference_path(str(source)))

            info = sf.info(derived)
            self.assertEqual(info.samplerate, 24_000)
            self.assertEqual(info.channels, 1)
            self.assertAlmostEqual(info.duration, 2.14, delta=0.03)
            self.assertEqual(source.read_bytes(), original)


class HiggsMLXGenerationTests(unittest.TestCase):
    def test_hungarian_question_voice_reference_is_generated_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.wav'
            sf.write(source, np.zeros(2400), 24_000)
            commands = []
            engine = HiggsMLXEngine()
            engine._worker = object()

            def rpc(payload):
                commands.append(payload)
                sf.write(payload['output_path'], np.zeros(3600), 24_000)
                return {'ok': True, 'result': {}}

            with (
                patch('core.higgs_mlx_engine.AUDIO_CACHE_DIR', str(root / 'cache')),
                patch(
                    'core.higgs_mlx_engine._question_reference_path',
                    return_value='tight.wav',
                ),
                patch.object(engine, '_source', return_value=('test/model', False)),
                patch.object(engine, '_rpc_raw', side_effect=rpc),
            ):
                first = engine._question_voice_reference(
                    str(source), 'Eredeti átirat.', 'hu'
                )
                second = engine._question_voice_reference(
                    str(source), 'Eredeti átirat.', 'hu'
                )

            self.assertEqual(first, second)
            self.assertTrue(Path(first[0]).is_file())
            self.assertEqual(first[1], 'Vajon visszatér még?')
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0]['reference_audio'], 'tight.wav')
            self.assertEqual(commands[0]['reference_text'], 'Eredeti átirat.')
            self.assertEqual(commands[0]['prompt'], 'Vajon visszatér még?')
            self.assertEqual(commands[0]['generation']['seed'], 7)

    def test_non_hungarian_question_keeps_original_reference_transcript(self):
        engine = HiggsMLXEngine()
        with patch(
            'core.higgs_mlx_engine._question_reference_path',
            return_value='tight.wav',
        ):
            result = engine._question_voice_reference(
                'source.wav', 'Original transcript.', 'en'
            )

        self.assertEqual(result, ('tight.wav', 'Original transcript.'))

    def test_narration_is_batched_and_question_is_sequential(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = []
            engine = HiggsMLXEngine()
            engine._ready = True
            engine._worker = object()

            def cache_path(key):
                return str(root / f'{key}.wav')

            def rpc(payload):
                commands.append(payload)
                if payload['command'] == 'batch':
                    for item in payload['items']:
                        sf.write(item['output_path'], np.zeros(2400), 24_000)
                    return {"ok": True, "results": [{}, {}]}
                if payload['command'] == 'generate':
                    sf.write(payload['output_path'], np.zeros(2400), 24_000)
                    return {"ok": True, "result": {}}
                raise AssertionError(payload['command'])

            items = [
                {"text": "Első mondat.", "language": "hu"},
                {"text": "Második mondat.", "language": "hu"},
                {"text": "Ez kérdés?", "language": "hu", "ref_audio": "ref.wav"},
            ]
            callbacks = []
            with (
                patch.object(engine, 'cache_path', side_effect=cache_path),
                patch.object(engine, '_rpc_raw', side_effect=rpc),
                patch.object(
                    engine,
                    '_question_voice_reference',
                    return_value=('question.wav', 'Vajon visszatér még?'),
                ),
                patch(
                    'core.higgs_mlx_engine._setting',
                    side_effect=lambda key, default: {
                        'higgs_mlx_hybrid_questions': True,
                        'higgs_mlx_batch_size': 5,
                        'higgs_mlx_model_source': 'download',
                        'higgs_mlx_model_repo': 'test/model',
                    }.get(key, default),
                ),
            ):
                results = engine.generate_many(
                    items, on_item=lambda index, result: callbacks.append(index)
                )

            self.assertEqual([command['command'] for command in commands], ['batch', 'generate'])
            self.assertEqual(len(commands[0]['items']), 2)
            self.assertEqual(commands[1]['reference_audio'], 'question.wav')
            self.assertEqual(commands[1]['reference_text'], 'Vajon visszatér még?')
            self.assertEqual(callbacks, [0, 1, 2])
            self.assertEqual(len(results), 3)


if __name__ == '__main__':
    unittest.main()
