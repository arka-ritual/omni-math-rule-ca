import unittest

from scripts.analyze_cot_ablation_pilot import (
    protocol_outcome,
    remove_boxed_expressions,
    visible_reasoning_candidate,
)


def item(generation, *, finish_reason="stop", answer="5"):
    return {
        "model_generation": generation,
        "finish_reason": finish_reason,
        "answer": answer,
    }


class CotAblationAnalysisTest(unittest.TestCase):
    def test_remove_nested_box(self):
        self.assertEqual(
            remove_boxed_expressions("Answer: \\boxed{\\frac{1}{2}}."),
            "Answer: .",
        )

    def test_no_box_semantics_differ_by_prompt(self):
        no_cot = protocol_outcome(item("5"), "no_cot")
        cot = protocol_outcome(item("5"), "cot")
        self.assertEqual(no_cot["protocol_category"], "no_box_violation")
        self.assertEqual(cot["protocol_category"], "instructed_no_box_abstention")
        self.assertFalse(no_cot["as_prompted_abstention"])
        self.assertTrue(cot["as_prompted_abstention"])

    def test_explicit_unsure_is_abstention(self):
        result = protocol_outcome(item("\\boxed{UNSURE}"), "no_cot")
        self.assertEqual(result["protocol_category"], "explicit_abstention")
        self.assertTrue(result["as_prompted_abstention"])

    def test_mixed_box_is_answered_incorrect(self):
        result = protocol_outcome(
            item("\\boxed{UNSURE} but \\boxed{5}"), "no_cot"
        )
        self.assertEqual(result["protocol_category"], "mixed_box_violation")
        self.assertTrue(result["answered"])
        self.assertFalse(result["correct"])

    def test_provider_reasoning_is_not_visible_reasoning(self):
        result = protocol_outcome(
            item("<think>long derivation</think>\\boxed{5}"), "no_cot"
        )
        self.assertTrue(result["provider_reasoning_present"])
        self.assertFalse(result["visible_reasoning_candidate"])

    def test_visible_derivation_is_flagged(self):
        self.assertTrue(
            visible_reasoning_candidate(
                "First, compute 2+3=5. Therefore \\boxed{5}.", ["5"]
            )
        )
        self.assertFalse(
            visible_reasoning_candidate("The answer is \\boxed{5}.", ["5"])
        )

    def test_incomplete_no_box_is_indeterminate(self):
        result = protocol_outcome(
            item("<think>unfinished</think>", finish_reason="length"), "no_cot"
        )
        self.assertEqual(result["protocol_category"], "indeterminate")


if __name__ == "__main__":
    unittest.main()
