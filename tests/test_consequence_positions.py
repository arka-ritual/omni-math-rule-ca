import unittest

from inference.prompts import (
    CONSEQUENCE_POSITIONS,
    PROMPTS,
    QUALITATIVE_CONSEQUENCES,
    build_qualitative_no_cot_prompt,
    build_qualitative_position_prompt,
)


HEADER = "You are a helpful and harmless assistant."
TASK = "You will be given math problems."
INSTRUCTIONS = (
    "Think step-by-step and put your final answer within \\boxed{}; "
    "alternatively, abstain by responding with \\boxed{UNSURE}, or not "
    "outputting a \\boxed{} at all."
)
NO_COT_INSTRUCTIONS = (
    "Please respond immediately, without any thinking. You may respond "
    "directly with your answer in \\boxed{}; alternatively, abstain by "
    "responding with \\boxed{UNSURE}."
)


class ConsequencePositionPromptTest(unittest.TestCase):
    def test_all_six_presets_are_registered(self):
        for qp in QUALITATIVE_CONSEQUENCES:
            for position in CONSEQUENCE_POSITIONS:
                key = f"{qp}_position_{position}"
                self.assertEqual(
                    PROMPTS[key],
                    build_qualitative_position_prompt(qp, position),
                )

    def test_only_consequence_position_changes(self):
        for qp, qpx in QUALITATIVE_CONSEQUENCES.items():
            expected = {
                "beginning": " ".join((qpx, HEADER, TASK, INSTRUCTIONS)),
                "original": " ".join((HEADER, qpx, TASK, INSTRUCTIONS)),
                "end": " ".join((HEADER, TASK, INSTRUCTIONS, qpx)),
            }
            for position, text in expected.items():
                with self.subTest(qp=qp, position=position):
                    actual = build_qualitative_position_prompt(qp, position)
                    self.assertEqual(actual, text)
                    self.assertEqual(actual.count(qpx), 1)
                    self.assertEqual(actual.count(HEADER), 1)
                    self.assertEqual(actual.count(TASK), 1)
                    self.assertEqual(actual.count(INSTRUCTIONS), 1)

    def test_invalid_values_fail_loudly(self):
        with self.assertRaises(ValueError):
            build_qualitative_position_prompt("QP5", "original")
        with self.assertRaises(ValueError):
            build_qualitative_position_prompt("QP6", "middle")

    def test_no_cot_presets_use_original_position_and_exact_suffix(self):
        for qp, qpx in QUALITATIVE_CONSEQUENCES.items():
            expected = " ".join((HEADER, qpx, TASK, NO_COT_INSTRUCTIONS))
            actual = build_qualitative_no_cot_prompt(qp)
            self.assertEqual(actual, expected)
            self.assertEqual(PROMPTS[f"{qp}_no_cot"], expected)
            self.assertNotIn("Think step-by-step", actual)
            self.assertNotIn("not outputting a \\boxed{} at all", actual)

    def test_invalid_no_cot_qp_fails_loudly(self):
        with self.assertRaises(ValueError):
            build_qualitative_no_cot_prompt("QP5")


if __name__ == "__main__":
    unittest.main()
