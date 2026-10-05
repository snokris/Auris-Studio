import json
import os
import tempfile
import unittest
from pathlib import Path

import app as app_module
from core import database, settings


class SettingsTtsCacheInvalidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_settings_file = settings.SETTINGS_FILE
        self.original_startup = app_module._startup_complete
        database.DB_PATH = os.path.join(self.tmp.name, 'reader.db')
        settings.SETTINGS_FILE = Path(self.tmp.name) / 'settings.json'
        app_module._startup_complete = True
        database.init_db()
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO books (id, title, file_path, file_type) "
                "VALUES (1, 'Test', 'test.txt', 'txt')"
            )
            conn.execute(
                "INSERT INTO chapters (id, book_id, title, order_num, content) "
                "VALUES (1, 1, 'Chapter 1', 0, 'Test text.')"
            )
            conn.execute(
                "INSERT INTO tts_segments "
                "(book_id, chapter_id, segment_index, text, enriched_text, cache_key, audio_path) "
                "VALUES (1, 1, 0, 'Test text.', 'Test text.', 'old-key', 'old.wav')"
            )
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        settings.SETTINGS_FILE = self.original_settings_file
        app_module._startup_complete = self.original_startup
        self.tmp.cleanup()

    def _segment_count(self):
        with database.get_conn() as conn:
            return conn.execute('SELECT COUNT(*) FROM tts_segments').fetchone()[0]

    def test_normalization_change_clears_persisted_playback_segments(self):
        response = self.client.post('/api/settings', json={'normalize_text': False})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._segment_count(), 0)

    def test_unchanged_normalization_keeps_persisted_playback_segments(self):
        response = self.client.post('/api/settings', json={'normalize_text': True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._segment_count(), 1)

    def test_mlx_backend_settings_are_validated_and_clear_old_audio(self):
        response = self.client.post('/api/settings', json={
            'higgs_backend': 'mlx',
            'higgs_mlx_model_source': 'local',
            'higgs_mlx_model_path': '/models/higgs-mlx',
            'higgs_mlx_batch_size': 99,
            'higgs_mlx_hybrid_questions': False,
        })

        self.assertEqual(response.status_code, 200)
        saved = settings.load()
        self.assertEqual(saved['higgs_backend'], 'mlx')
        self.assertEqual(saved['higgs_mlx_model_source'], 'local')
        self.assertEqual(saved['higgs_mlx_model_path'], '/models/higgs-mlx')
        self.assertEqual(saved['higgs_mlx_batch_size'], 8)
        self.assertFalse(saved['higgs_mlx_hybrid_questions'])
        self.assertEqual(self._segment_count(), 0)

    def test_expression_policy_migration_marks_old_prompts_stale_once(self):
        settings.save({'tts_expression_policy_version': 1})

        self.assertTrue(settings.migrate_tts_expression_policy_version())
        self.assertEqual(
            settings.load()['tts_expression_policy_version'],
            settings.TTS_EXPRESSION_POLICY_VERSION,
        )
        self.assertFalse(settings.migrate_tts_expression_policy_version())

    def test_legacy_omnivoice_settings_are_dropped(self):
        settings.SETTINGS_FILE.write_text(json.dumps({
            'tts_engine': 'omnivoice',
            'model_repo': 'some/legacy-model',
            'tts_num_step': 15,
            'theme': 'dark',
        }), encoding='utf-8')

        loaded = settings.load()
        saved = settings.save({'tts_engine': 'omnivoice'})

        self.assertNotIn('tts_engine', loaded)
        self.assertNotIn('model_repo', loaded)
        self.assertNotIn('tts_num_step', loaded)
        self.assertNotIn('tts_engine', saved)
        self.assertEqual(saved['theme'], 'dark')


if __name__ == '__main__':
    unittest.main()
