import re
import unittest
from pathlib import Path


READER_JS = Path(__file__).resolve().parents[1] / "static" / "js" / "reader.js"


class ReaderPlaybackTests(unittest.TestCase):
    def test_paragraph_click_starts_playback(self):
        source = READER_JS.read_text(encoding="utf-8")
        self.assertIn('reader-paragraph', source)
        self.assertIn("event.target.closest('.sentence, .reader-paragraph')", source)
        self.assertIn('playSegment(idx);', source)
        self.assertNotIn('onclick="jumpTo(', source)

    def test_playback_error_is_shown_after_stopping(self):
        source = READER_JS.read_text(encoding="utf-8")
        self.assertIn("showToast(e.message || 'Playback failed.', 'err');", source)

    def test_stop_keeps_current_chapter_position(self):
        source = READER_JS.read_text(encoding="utf-8")
        handler = re.search(
            r"document\.getElementById\('btn-stop'\)\.onclick\s*=\s*\(\)\s*=>\s*\{(.*?)\n\};",
            source,
            re.DOTALL,
        )

        self.assertIsNotNone(handler)
        self.assertIn("stopPlayback();", handler.group(1))
        self.assertNotIn("setCurrentSegment(0", handler.group(1))


if __name__ == "__main__":
    unittest.main()
