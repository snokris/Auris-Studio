import os
import tempfile
import unittest
from unittest.mock import patch

import app as app_module
from core import database


class NarratorPreviewTextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_startup = app_module._startup_complete
        database.DB_PATH = os.path.join(self.tmp.name, "reader.db")
        app_module._startup_complete = True
        database.init_db()
        with database.get_conn() as conn:
            conn.execute(
                "INSERT INTO books (id, title, file_path, file_type, language) "
                "VALUES (1, 'Test', 'test.txt', 'txt', 'hu')"
            )
            conn.execute(
                "INSERT INTO chapters (id, book_id, title, order_num, content) "
                "VALUES (1, 1, 'Chapter', 0, 'Text.')"
            )
            conn.execute(
                "INSERT INTO tts_segments "
                "(book_id, chapter_id, segment_index, text, enriched_text) "
                "VALUES (1, 1, 0, 'Text.', 'Text.')"
            )
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        app_module._startup_complete = self.original_startup
        self.tmp.cleanup()

    def test_default_is_rendered_and_persisted_with_narrator(self):
        with patch.object(app_module.tts, "load_async"):
            page = self.client.get("/voice-studio/1")
        self.assertEqual(page.status_code, 200)
        self.assertIn(
            app_module.DEFAULT_NARRATOR_PREVIEW_TEXT.encode(), page.data
        )
        self.assertEqual(
            self.client.get("/api/books/1/narrator").get_json()["preview_text"],
            app_module.DEFAULT_NARRATOR_PREVIEW_TEXT,
        )

        response = self.client.put(
            "/api/books/1/narrator", json={"preview_text": "  Szép magyar napot!  "}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["preview_text"], "Szép magyar napot!")
        self.assertFalse(response.get_json()["segments_cleared"])
        with database.get_conn() as conn:
            book = conn.execute(
                "SELECT narrator_preview_text FROM books WHERE id=1"
            ).fetchone()
            segments = conn.execute("SELECT COUNT(*) FROM tts_segments").fetchone()[0]
        self.assertEqual(book["narrator_preview_text"], "Szép magyar napot!")
        self.assertEqual(segments, 1)

        with patch.object(app_module.tts, "load_async"):
            page = self.client.get("/voice-studio/1")
        self.assertIn("Szép magyar napot!".encode(), page.data)

    def test_preview_uses_submitted_text_and_book_language(self):
        with patch.object(app_module.tts, "status", return_value={"state": "ready"}), patch.object(
            app_module.tts, "generate_preview", return_value={"cache_key": "test-key"}
        ) as generate:
            response = self.client.post(
                "/api/books/1/characters/narrator/preview",
                json={"preview_text": "  Vajon visszatér még?  "},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["audio_url"], "/api/audio/test-key")
        self.assertEqual(generate.call_args.kwargs["sample_text"], "Vajon visszatér még?")
        self.assertEqual(generate.call_args.kwargs["language"], "hu")
        self.assertIsNone(generate.call_args.kwargs["ref_audio"])

    def test_blank_preview_resets_to_default_and_long_text_is_rejected(self):
        response = self.client.put(
            "/api/books/1/narrator", json={"preview_text": "   "}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["preview_text"],
            app_module.DEFAULT_NARRATOR_PREVIEW_TEXT,
        )

        with patch.object(app_module.tts, "status", return_value={"state": "ready"}), patch.object(
            app_module.tts, "generate_preview", return_value={"cache_key": "test-key"}
        ) as generate:
            response = self.client.post(
                "/api/books/1/characters/narrator/preview",
                json={"preview_text": "   "},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                generate.call_args.kwargs["sample_text"],
                app_module.DEFAULT_NARRATOR_PREVIEW_TEXT,
            )
            response = self.client.post(
                "/api/books/1/characters/narrator/preview",
                json={"preview_text": "A" * 1001},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(generate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
