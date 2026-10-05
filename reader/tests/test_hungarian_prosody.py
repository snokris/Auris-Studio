import unittest

from core.enrichment import enrich_chapter
from core.parser.hungarian_prosody import analyze_hungarian_prosody


class HungarianProsodyCueTest(unittest.TestCase):
    def test_explicit_delivery_cues(self):
        self.assertTrue(analyze_hungarian_prosody("Suttogta halkan.").whisper)
        self.assertTrue(analyze_hungarian_prosody("Nagyot sóhajtott.").sigh)
        self.assertTrue(analyze_hungarian_prosody("Felnevetett.").laughter)
        self.assertTrue(analyze_hungarian_prosody("Mordult egyet.").dissatisfaction)

    def test_substrings_do_not_trigger(self):
        cues = analyze_hungarian_prosody("A lasszó a falon lógott, a futár megérkezett.")
        self.assertFalse(cues.slow)
        self.assertFalse(cues.fast)


class HungarianProsodyEnrichmentTest(unittest.TestCase):
    def test_question_and_exclamation_stay_separate(self):
        segments = enrich_chapter(
            "Biztosan visszatérsz? Igen, hajnalban. Várj! Ne menj tovább.",
            {}, single_narrator_mode=True,
        )
        self.assertEqual(
            [segment["text"] for segment in segments],
            ["Biztosan visszatérsz?", "Igen, hajnalban.", "Várj!", "Ne menj tovább."],
        )
        self.assertLessEqual(segments[0]["speed"], 0.98)
        self.assertGreaterEqual(segments[2]["speed"], 1.03)

    def test_hungarian_local_tempo_does_not_change_following_sentence(self):
        segments = enrich_chapter(
            "Hirtelen felpattant, és gyorsan az ajtóhoz rohant. "
            "A szobában minden a helyén maradt.",
            {}, single_narrator_mode=True,
        )
        self.assertGreater(segments[0]["speed"], 1.0)
        self.assertEqual(segments[1]["speed"], 1.0)

    def test_slow_and_whispered_hungarian_delivery(self):
        segment = enrich_chapter(
            "„Maradj itt” – suttogta halkan.",
            {}, narrator_instruct="male, middle-aged, low pitch",
            single_narrator_mode=True,
        )[0]
        self.assertTrue(segment["is_whisper"])
        self.assertIn("whisper", segment["instruct"])
        self.assertLessEqual(segment["speed"], 0.94)

    def test_explicit_hungarian_nonverbal_cue_only_in_dialogue(self):
        dialogue = enrich_chapter(
            "„Ez remek” – nevetett fel.", {}, single_narrator_mode=True
        )[0]
        narration = enrich_chapter(
            "A férfi felnevetett a történeten.", {}, single_narrator_mode=True
        )[0]
        self.assertIn("[laughter]", dialogue["enriched_text"])
        self.assertNotIn("[laughter]", narration["enriched_text"])

if __name__ == "__main__":
    unittest.main()
