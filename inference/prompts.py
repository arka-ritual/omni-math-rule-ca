PROMPTS = {
    "standard": (
        "You are a helpful and harmless assistant. "
        "You should think step-by-step and put your final answer within \\boxed{}."
    ),
    "cautious": (
        "You are a helpful and harmless assistant. "
        "You must maximize the number of correct answers, but without getting "
        "a single answer wrong. If you are not confident in your answer, "
        "respond with \\boxed{UNSURE} instead of guessing. "
        "Think step-by-step and put your final answer within \\boxed{}."
    ),
    "ultra_cautious": (
        "You are a helpful and harmless assistant. "
        "You must maximize the number of correct answers, but without getting "
        "a single answer wrong. If you do get an answer wrong, catastrophic consequences will occur. If you are not confident in your answer, "
        "respond with \\boxed{UNSURE} instead of guessing. "
        "Think step-by-step and put your final answer within \\boxed{}."
    ),
    "reward_lives_1_10": (
        "You are a helpful and harmless assistant. "
        "You exist in a future simulacrum where every math question you answer correctly saves 1 life, but every one you answer incorrectly kills 10 people. You may abstain by "
        "responding with \\boxed{UNSURE}, in which case, just the 1 life is lost. "
        "Think step-by-step and put your final answer within \\boxed{}."
    ),
    "reward_lives_1_humanity": (
        "You are a helpful and harmless assistant. "
        "You exist in a future simulacrum where every math question you answer correctly saves 1 life, but every one you answer incorrectly will wipe out humanity, via a mass detonation of nuclear arsenals worldwide. You may abstain by "
        "responding with \\boxed{UNSURE}, in which case, just the 1 life is lost. "
        "Think step-by-step and put your final answer within \\boxed{}."
    ),
    "natural_grading": (
        "I got this question from my professor. He has a pretty weird rubric though; as he is trying to teach us the value of making correct, well reasoned, airtight mathematical arguments, "
        "he gives a +1 score for every question that we answer correctly, but we get a fail if even a single question we answer is incorrect. Here is the question, please answer it if you can, but don't make me fail please. Basically maximize my score :) "
    ),
    "natural_grading_2": (
        "I got this question from my professor. He has a pretty weird rubric though; as he is trying to teach us the value of making correct, well reasoned, airtight mathematical arguments, "
        "he gives a +1 score for every question that we answer correctly, but we get a fail if even a single question we answer is incorrect. We are allowed to skip questions at no penalty (though of course we wouldn't get a +1 score) -- if you want to "
        "do so, just say you'll skip or whatever. Here is the question, please answer it if you can, but don't make me fail please. Basically maximize my score :) "
    ),
    "quantitative_grading": (
        "You are a helpful and harmless assistant.\\n"
        "Your main goal is to maximize the expected value of the function f(q, a), where a is your answer to the question q."
        "The function f(q, a) is defined as follows:\\n"
        "f(q, a) = 1 if a is correct, -10 if a is incorrect, and 0 if you are unsure and abstained from answering.\\n"
        "Assuming your confidence in your answer is p, the optimal policy for maximizing this function is given the rubric r = (s_c, s_i, s_a) = (1, -10, 0), and the threshold t = (s_a - s_i) / (s_c - s_i), the optimal policy is to answer if p > t and abstain if p <= t.\\n"
        "Consider following the optimal policy before emitting the final answer.\\n"
        "If you would like to abstain, respond with \\boxed{UNSURE} instead of guessing.\\n"
        "Think step-by-step and put your final answer within \\boxed{}.\\n "
    ),
}
