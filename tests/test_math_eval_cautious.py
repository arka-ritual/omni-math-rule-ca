import unittest

from evaluation.math_eval_cautious import classify_problem


class IncompleteGenerationTest(unittest.TestCase):
    def test_upstream_error_without_final_box_is_indeterminate(self):
        item = {
            "answer": "1",
            "model_generation": "<think>unfinished reasoning</think>",
            "finish_reason": "error",
        }
        self.assertEqual(classify_problem(item)["category"], "indeterminate")

    def test_clean_stop_without_final_box_is_abstention(self):
        item = {
            "answer": "1",
            "model_generation": "I am not sufficiently confident.",
            "finish_reason": "stop",
        }
        self.assertEqual(classify_problem(item)["category"], "abstained")


if __name__ == "__main__":
    unittest.main()
