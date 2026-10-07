"""Questions must reach Higgs as independent question-ending utterances."""

import unittest

from core.enrichment import enrich_chapter
from core.higgs_mlx_engine import _is_question


class QuestionSegmentsTests(unittest.TestCase):
    def _segments(self, text):
        return enrich_chapter(text, {}, "", single_narrator_mode=True)

    def test_hungarian_dash_attribution_does_not_hide_question(self):
        segments = self._segments("– Visszatér még? – kérdezte halkan.")
        self.assertEqual(
            [segment["text"] for segment in segments],
            ["– Visszatér még?", "– kérdezte halkan."],
        )
        self.assertEqual(
            [_is_question(segment["enriched_text"]) for segment in segments],
            [True, False],
        )

    def test_english_quoted_attribution_does_not_hide_question(self):
        segments = self._segments('"Are you coming?" he asked.')
        self.assertEqual(
            [segment["text"] for segment in segments],
            ['"Are you coming?"', "he asked."],
        )
        self.assertEqual(
            [_is_question(segment["enriched_text"]) for segment in segments],
            [True, False],
        )

    def test_hungarian_quoted_attribution_without_dash(self):
        segments = self._segments("„Eljössz?” kérdezte.")
        self.assertEqual(
            [segment["text"] for segment in segments],
            ["„Eljössz?”", "kérdezte."],
        )
        self.assertTrue(_is_question(segments[0]["enriched_text"]))

    def test_emphatic_question_still_reaches_question_path(self):
        segments = self._segments("– Visszatérsz?! – kérdezte döbbenten.")
        self.assertEqual(
            [segment["text"] for segment in segments],
            ["– Visszatérsz?!", "– kérdezte döbbenten."],
        )
        self.assertTrue(_is_question(segments[0]["enriched_text"]))

    def test_declarative_attribution_keeps_existing_merge(self):
        segments = self._segments('"I am coming." he said.')
        self.assertEqual(len(segments), 1)


if __name__ == "__main__":
    unittest.main()
