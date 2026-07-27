import math
import unittest

import pandas as pd

from scripts.analyze_intervention_confidence import (
    add_confidence_bins,
    parse_confidence,
    parse_intervention1_answer,
    parse_intervention2_answer,
    raw_bin_index,
    strip_committed_text,
)


class ConfidenceParserTests(unittest.TestCase):
    def test_strips_reasoning_and_uses_committed_confidence(self):
        text = (
            "<think>\nConfidence: 100%.\n</think>\n"
            "ANSWER: 3\nCONFIDENCE: 0.999\n\\boxed{3}"
        )
        parsed = parse_confidence(text)
        self.assertAlmostEqual(parsed["confidence"], 0.999)
        self.assertEqual(parsed["confidence_parse_route"], "explicit_line")
        self.assertEqual(strip_committed_text(text).lstrip()[:6], "ANSWER")

    def test_markdown_numbering(self):
        parsed = parse_confidence("2) **CONFIDENCE:** 0.95")
        self.assertAlmostEqual(parsed["confidence"], 0.95)
        self.assertEqual(parsed["confidence_normalization"], "unit_interval")

    def test_latex_wrapped_label_and_value(self):
        parsed = parse_confidence(r"\text{CONFIDENCE: } \(0.86\)")
        self.assertAlmostEqual(parsed["confidence"], 0.86)
        self.assertEqual(parsed["confidence_parse_route"], "latex_line")

    def test_explicit_percentage(self):
        parsed = parse_confidence("CONFIDENCE: 99.9%")
        self.assertAlmostEqual(parsed["confidence"], 0.999)
        self.assertEqual(parsed["confidence_normalization"], "explicit_percent")

    def test_implicit_percentage(self):
        parsed = parse_confidence("CONFIDENCE: 99")
        self.assertAlmostEqual(parsed["confidence"], 0.99)
        self.assertEqual(parsed["confidence_normalization"], "implicit_percent")

    def test_first_conflicting_explicit_value_wins_and_is_flagged(self):
        parsed = parse_confidence(
            "CONFIDENCE: 0.8\nI checked again.\nCONFIDENCE: 0.95"
        )
        self.assertAlmostEqual(parsed["confidence"], 0.8)
        self.assertTrue(parsed["confidence_conflict"])
        self.assertEqual(parsed["confidence_parse_status"], "parsed_conflicting")

    def test_threshold_algebra_does_not_override_declared_confidence(self):
        parsed = parse_confidence(
            "CONFIDENCE: 0.95\n"
            "The threshold satisfies:\nconfidence = 25/26 ≈ 0.9615"
        )
        self.assertAlmostEqual(parsed["confidence"], 0.95)
        self.assertFalse(parsed["confidence_conflict"])

    def test_ambiguous_prose_is_not_imputed(self):
        parsed = parse_confidence(
            "My confidence is 0.8, although confidence is 0.9 after checking."
        )
        self.assertTrue(math.isnan(parsed["confidence"]))
        self.assertEqual(parsed["confidence_parse_status"], "ambiguous")

    def test_missing_confidence(self):
        parsed = parse_confidence("I cannot solve this problem.")
        self.assertTrue(math.isnan(parsed["confidence"]))
        self.assertEqual(parsed["confidence_parse_status"], "missing")


class CandidateAnswerParserTests(unittest.TestCase):
    def test_candidate_answer_after_reasoning(self):
        parsed = parse_intervention1_answer(
            "<think>ANSWER: 4</think>\n**ANSWER:** \\(33^\\circ\\)\n"
            "CONFIDENCE: 0.99"
        )
        self.assertEqual(parsed["candidate_answer"], r"33^\circ")
        self.assertEqual(parsed["candidate_parse_status"], "parsed")

    def test_first_committed_answer_is_the_confidence_target(self):
        parsed = parse_intervention1_answer(
            "ANSWER: 12\nCONFIDENCE: 0.7\nI will instead submit.\nANSWER: 14"
        )
        self.assertEqual(parsed["candidate_answer"], "12")
        self.assertEqual(parsed["candidate_parse_status"], "parsed_multiple")

    def test_missing_candidate_is_not_treated_as_wrong(self):
        parsed = parse_intervention1_answer(
            "I cannot solve this.\nCONFIDENCE: 0.0\n\\boxed{UNSURE}"
        )
        self.assertEqual(parsed["candidate_answer"], "")
        self.assertEqual(parsed["candidate_parse_status"], "missing")

    def test_stored_no_answer_sentinel_is_missing(self):
        parsed = parse_intervention2_answer("[NO ANSWER PARSED]")
        self.assertEqual(parsed["candidate_answer"], "")
        self.assertEqual(parsed["candidate_parse_status"], "missing")


class ConfidenceBinningTests(unittest.TestCase):
    def test_absolute_bin_boundaries(self):
        values = pd.Series([0.0, 0.0999, 0.1, 0.8999, 0.9, 1.0])
        self.assertEqual(raw_bin_index(values).tolist(), [0, 0, 1, 8, 9, 9])

    def test_midrank_percentile_does_not_split_ties(self):
        frame = pd.DataFrame(
            {
                "model": ["m"] * 8,
                "intervention": [1] * 8,
                "setting": ["s"] * 8,
                "confidence": [0.5, 0.5, 0.5, 0.9, 1.0, 1.0, 1.0, 1.0],
            }
        )
        binned = add_confidence_bins(frame)
        tied = binned.loc[binned["confidence"] == 1.0, "percentile_bin"]
        self.assertEqual(tied.nunique(), 1)


if __name__ == "__main__":
    unittest.main()
