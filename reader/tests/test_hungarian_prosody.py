import unittest
from unittest.mock import patch

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

    def test_benchmark_prosody_suite_uses_enriched_delivery(self):
        from scripts.benchmark_omnivoice import benchmark_cases

        cases = {case["label"]: case for case in benchmark_cases("prosody")}
        self.assertLessEqual(cases["question"]["speed"], 0.98)
        self.assertGreaterEqual(cases["exclamation"]["speed"], 1.03)
        self.assertLessEqual(cases["whisper"]["speed"], 0.94)
        self.assertIn("whisper", cases["whisper"]["instruct"])
        self.assertIn("[sigh]", cases["sigh"]["text"])
        self.assertEqual(cases["whisper"]["clone_instruct"], "whisper")

    def test_clone_instruct_is_explicitly_opt_in(self):
        from core.tts_engine import TTSEngine

        engine = TTSEngine()
        prompt = object()
        with patch.object(engine, "_get_voice_clone_prompt", return_value=prompt):
            off = engine._build_generate_kwargs(
                ["Maradj itt."], "whisper", "voice.wav", "Minta.", [1.0],
                16, "hu", False,
            )
            on = engine._build_generate_kwargs(
                ["Maradj itt."], "whisper", "voice.wav", "Minta.", [1.0],
                16, "hu", False, allow_clone_instruct=True,
            )
        self.assertIs(off["voice_clone_prompt"], prompt)
        self.assertNotIn("instruct", off)
        self.assertEqual(on["instruct"], "whisper")


if __name__ == "__main__":
    unittest.main()
