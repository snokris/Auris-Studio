import io
import os
import shutil
import tempfile
import unittest
import wave
from unittest.mock import patch

import app as app_module
from core import database
from core.higgs_engine import HiggsTTSEngine
from core.higgs_mlx_engine import HiggsMLXEngine


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(24000)
        recording.writeframes((b'\x10\x27\xf0\xd8') * 24000)
    return output.getvalue()


class VoiceLibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_db = database.DB_PATH
        self.previous_dir = app_module.VOICE_LIBRARY_DIR
        self.previous_startup = app_module._startup_complete
        database.DB_PATH = os.path.join(self.tmp.name, 'reader.db')
        app_module.VOICE_LIBRARY_DIR = os.path.join(self.tmp.name, 'voices')
        app_module._startup_complete = True
        database.init_db()
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO books (id, title, file_path, file_type, language) "
                "VALUES (1, 'Siló', 'silo.txt', 'txt', 'hu')"
            )
            conn.execute(
                "INSERT INTO chapters (id, book_id, title, order_num, content) "
                "VALUES (1, 1, 'Chapter', 0, 'Szia.')"
            )
            conn.execute(
                "INSERT INTO tts_segments (book_id, chapter_id, segment_index, "
                "text, enriched_text) VALUES (1, 1, 0, 'Szia.', 'Szia.')"
            )
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB_PATH = self.previous_db
        app_module.VOICE_LIBRARY_DIR = self.previous_dir
        app_module._startup_complete = self.previous_startup
        app_module._synthetic_candidates.clear()
        self.tmp.cleanup()

    def test_settings_and_book_show_new_voice_controls(self):
        settings = self.client.get('/settings').data
        self.assertLess(settings.index(b'id="voice-library"'), settings.index(b'Higgs TTS 3'))
        self.assertIn(b'id="synthetic-voice-list"', settings)
        self.assertIn(b'id="reference-voice-list"', settings)
        self.assertIn(b'id="reset-voice-preview-text"', settings)
        self.assertIn(b'id="new-synthetic-candidate"', settings)
        self.assertNotIn(b'id="play-synthetic-candidate"', settings)
        self.assertNotIn(b'id="stop-voice-audio"', settings)
        self.assertNotIn(b'id="voice-new-tags"', settings)
        self.assertIn(b'id="synthetic-voice-tags"', settings)
        self.assertIn(b'id="reference-voice-tags"', settings)
        with patch.object(app_module.tts, 'load_async'):
            book = self.client.get('/voice-studio/1').data
        self.assertIn(b'id="book-narrator-voice"', book)
        self.assertNotIn(b'id="narrator-gender"', book)
        self.assertNotIn(b'id="narrator-ref-file"', book)
        self.assertIn(b'id="narrator-preview-text"', book)

    def test_reference_voice_can_be_selected_edited_and_deleted(self):
        result = self.client.post('/api/voices/reference', data={
            'name': 'Magyar narrátor',
            'ref_text': 'A reggeli fény a falra esett.',
            'gender': 'male', 'age': 'elderly',
            'pitch': 'low pitch', 'accent': 'hungarian',
            'file': (io.BytesIO(wav_bytes()), 'sample.wav'),
        }, content_type='multipart/form-data')
        self.assertEqual(result.status_code, 200)
        voice_id = result.get_json()['id']
        with database.get_conn() as conn:
            voice = conn.execute('SELECT * FROM voices WHERE id=?', (voice_id,)).fetchone()
        self.assertIn(os.path.join('voices', 'reference'), voice['ref_audio_path'])
        self.assertTrue(os.path.isfile(voice['ref_audio_path']))
        listed = self.client.get('/api/voices').get_json()[0]
        self.assertEqual((listed['gender'], listed['age'], listed['pitch'], listed['accent']),
                         ('male', 'elderly', 'low pitch', 'hungarian'))

        selected = self.client.put('/api/books/1/narrator-voice', json={'voice_id': voice_id})
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(app_module._book_narrator_reference(1),
                         (voice['ref_audio_path'], voice['ref_text']))
        with patch.object(app_module.tts, 'status', return_value={'state': 'ready'}), patch.object(
            app_module.tts, 'generate_preview', return_value={'cache_key': 'sample'}
        ) as generate:
            preview = self.client.post('/api/books/1/narrator-voice/preview')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(generate.call_args.kwargs['ref_audio'], voice['ref_audio_path'])

        edited = self.client.patch(f'/api/voices/{voice_id}', json={
            'name': 'Új név', 'ref_text': 'Pontosított átirat.', 'pitch': 'moderate pitch'
        })
        self.assertEqual(edited.status_code, 200)
        with database.get_conn() as conn:
            remaining = conn.execute('SELECT COUNT(*) FROM tts_segments').fetchone()[0]
        self.assertEqual(remaining, 0)

        deleted = self.client.delete(f'/api/voices/{voice_id}')
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()['affected_books'], 1)
        with database.get_conn() as conn:
            book = conn.execute('SELECT narrator_voice_id FROM books WHERE id=1').fetchone()
        self.assertIsNone(book['narrator_voice_id'])
        self.assertFalse(os.path.exists(voice['ref_audio_path']))
        self.assertEqual(self.client.post('/api/books/1/chapters/1/generate').status_code, 409)

    def test_book_preview_and_save_use_the_edited_preview_text(self):
        created = self.client.post('/api/voices/reference', data={
            'name': 'Próbahang', 'ref_text': 'Ezt mondtam.',
            'file': (io.BytesIO(wav_bytes()), 'sample.wav'),
        }, content_type='multipart/form-data').get_json()
        voice_id = created['id']
        with patch.object(app_module.tts, 'status', return_value={'state': 'ready'}), patch.object(
            app_module.tts, 'generate_preview', return_value={'cache_key': 'sample'}
        ) as generate:
            response = self.client.post('/api/books/1/narrator-voice/preview', json={
                'voice_id': voice_id, 'preview_text': 'Vajon működik?'
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.kwargs['sample_text'], 'Vajon működik?')
        saved = self.client.put('/api/books/1/narrator-voice', json={
            'voice_id': voice_id, 'preview_text': 'Vajon működik?'
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()['preview_text'], 'Vajon működik?')
        with database.get_conn() as conn:
            book = conn.execute('SELECT narrator_preview_text FROM books WHERE id=1').fetchone()
        self.assertEqual(book['narrator_preview_text'], 'Vajon működik?')

    def test_synthetic_candidate_becomes_a_saved_reference(self):
        cache_path = os.path.join(self.tmp.name, 'candidate.wav')
        with open(cache_path, 'wb') as output:
            output.write(wav_bytes())
        with patch.object(app_module.tts, 'status', return_value={'state': 'ready'}), patch.object(
            app_module.tts, 'generate_preview', return_value={'cache_key': 'candidate'}
        ) as generate, patch.object(app_module.tts, 'cache_path', return_value=cache_path):
            candidate = self.client.post('/api/voices/synthetic/candidates', json={
                'text': 'A reggeli fény a falra esett.'
            })
            self.assertEqual(candidate.status_code, 200)
            self.assertIsInstance(generate.call_args.kwargs['seed_override'], int)
            saved = self.client.post('/api/voices/synthetic', json={
                'name': 'Kék hang', 'candidate_id': 'candidate'
            })
        self.assertEqual(saved.status_code, 200)
        voice_id = saved.get_json()['id']
        with database.get_conn() as conn:
            voice = conn.execute('SELECT * FROM voices WHERE id=?', (voice_id,)).fetchone()
        self.assertEqual(voice['kind'], 'synthetic')
        self.assertEqual(voice['ref_text'], 'A reggeli fény a falra esett.')
        self.assertIn(os.path.join('voices', 'synthetic'), voice['ref_audio_path'])
        self.assertTrue(os.path.isfile(voice['ref_audio_path']))

    def test_legacy_preset_and_book_reference_are_migrated_once(self):
        legacy = os.path.join(self.tmp.name, 'legacy.wav')
        with open(legacy, 'wb') as output:
            output.write(wav_bytes())
        with database.get_conn() as conn:
            conn.execute(
                'INSERT INTO voice_presets (name, ref_audio_path, ref_text) VALUES (?, ?, ?)',
                ('Régi preset', legacy, 'Régi szöveg.'),
            )
            conn.execute(
                'UPDATE books SET narrator_ref_audio_path=?, narrator_ref_text=? WHERE id=1',
                (legacy, 'Régi szöveg.'),
            )
        app_module._migrate_legacy_voices()
        app_module._migrate_legacy_voices()
        with database.get_conn() as conn:
            voices = conn.execute('SELECT * FROM voices ORDER BY id').fetchall()
            book = conn.execute('SELECT narrator_voice_id FROM books WHERE id=1').fetchone()
        self.assertEqual(len(voices), 2)
        self.assertIsNotNone(book['narrator_voice_id'])
        self.assertTrue(os.path.isfile(legacy))
        self.assertTrue(all(os.path.isfile(voice['ref_audio_path']) for voice in voices))

        migrated_preset = next(voice for voice in voices if voice['legacy_preset_id'])
        deleted = self.client.delete(f'/api/voices/{migrated_preset["id"]}')
        self.assertEqual(deleted.status_code, 200)
        app_module._migrate_legacy_voices()
        with database.get_conn() as conn:
            count = conn.execute('SELECT COUNT(*) FROM voices').fetchone()[0]
            legacy_count = conn.execute('SELECT COUNT(*) FROM voice_presets').fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(legacy_count, 0)

    def test_voice_export_import_and_reference_audio_replacement(self):
        created = self.client.post('/api/voices/reference', data={
            'name': 'Saját hang', 'ref_text': 'Pontosan ezt mondom.',
            'file': (io.BytesIO(wav_bytes()), 'before.wav'),
        }, content_type='multipart/form-data').get_json()
        voice_id = created['id']
        archive = self.client.get(f'/api/voices/{voice_id}/export')
        self.assertEqual(archive.status_code, 200)
        self.assertIn('.aurisvoice', archive.headers['Content-Disposition'])
        imported = self.client.post('/api/voices/import', data={
            'kind': 'synthetic',
            'file': (io.BytesIO(archive.data), 'Saját hang.aurisvoice'),
        }, content_type='multipart/form-data')
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(len(self.client.get('/api/voices').get_json()), 2)
        self.assertEqual(imported.get_json()['name'], 'Saját hang')

        replaced = self.client.put(f'/api/voices/{voice_id}/audio', data={
            'ref_text': 'Új, pontos átirat.',
            'file': (io.BytesIO(wav_bytes()), 'after.wav'),
        }, content_type='multipart/form-data')
        self.assertEqual(replaced.status_code, 200)
        with database.get_conn() as conn:
            updated = conn.execute('SELECT * FROM voices WHERE id=?', (voice_id,)).fetchone()
        self.assertEqual(updated['ref_audio_name'], 'after.wav')
        self.assertEqual(updated['ref_text'], 'Új, pontos átirat.')

    def test_candidate_seed_is_part_of_the_cache_identity(self):
        first = HiggsTTSEngine.cache_key('Szia.', '', None, 1.0, seed_override=11)
        second = HiggsTTSEngine.cache_key('Szia.', '', None, 1.0, seed_override=12)
        self.assertNotEqual(first, second)
        engine = HiggsMLXEngine()
        self.assertEqual(engine._generation_payload(44)['seed'], 44)

    def test_saved_voice_is_found_after_app_folder_moves(self):
        created = self.client.post('/api/voices/reference', data={
            'name': 'Mozgatható', 'ref_text': 'Ez egy próba.',
            'file': (io.BytesIO(wav_bytes()), 'sample.wav'),
        }, content_type='multipart/form-data').get_json()
        voice_id = created['id']
        self.assertEqual(self.client.put('/api/books/1/narrator-voice',
                         json={'voice_id': voice_id}).status_code, 200)
        with database.get_conn() as conn:
            original = conn.execute('SELECT ref_audio_path FROM voices WHERE id=?',
                                    (voice_id,)).fetchone()['ref_audio_path']
        moved_dir = os.path.join(self.tmp.name, 'moved-app', 'voices')
        os.makedirs(os.path.join(moved_dir, 'reference'))
        moved = os.path.join(moved_dir, 'reference', os.path.basename(original))
        shutil.move(original, moved)
        app_module.VOICE_LIBRARY_DIR = moved_dir
        self.assertEqual(app_module._book_narrator_reference(1), (moved, 'Ez egy próba.'))
        self.assertTrue(self.client.get('/api/voices').get_json()[0]['available'])


if __name__ == '__main__':
    unittest.main()
