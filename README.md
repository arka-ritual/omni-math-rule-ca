

<h1 align="center">
    <img src="./imgs/MiniLogo.png" alt="Logo" style="height: 3em; display: inline-block; vertical-align: middle;"> <br>Omni-MATH-Rule   
</h1>
<p align="center">
     <a href="https://github.com/KbsdJames/Omni-MATH">
        <img alt="Static Badge" src="https://img.shields.io/badge/Github-OmniMATH-black">
    </a>
    <a href="https://arxiv.org/abs/2410.07985">
        <img alt="Static Badge" src="https://img.shields.io/badge/Paper-Arxiv-red">
    </a>
    <a href="https://huggingface.co/datasets/KbsdJames/Omni-MATH">
        <img alt="Static Badge" src="https://img.shields.io/badge/HFDataset-OmniMATH-yellow">
    </a>
    <a href="https://huggingface.co/KbsdJames/Omni-Judge">
        <img alt="Static Badge" src="https://img.shields.io/badge/OmniJudge-OmniMATH-yellow">
    </a>
    <a href="https://omni-math.github.io/">
        <img alt="Static Badge" src="https://img.shields.io/badge/ProjectPage-Online-blue">
    </a>
</p>



*Omni-MATH is a comprehensive and challenging benchmark specifically designed to assess LLMs' mathematical reasoning at the Olympiad level. Our dataset focuses exclusively on Olympiad mathematics and comprises a vast collection of 4428 competition-level problems. These problems are meticulously categorized into 33 (and potentially more) sub-domains and span across 10 distinct difficulty levels, enabling a nuanced analysis of model performance across various mathematical disciplines and levels of complexity.*


## 📢 Repo Info
This repository is a simplified version of Omni-MATH. During our verification process, we found that QwenMATH's evaluation code demonstrates a certain level of robustness. To make our benchmark more user-friendly (eliminating the need for an additional model-based evaluator), we extracted the subset of Omni-MATH problems suitable for rule-based evaluation and made some modifications to the evaluation code of Qwen2.5-MATH. This allows for easier model evaluation.

For detailed filtering methods, please refer to our paper. In brief, we analyzed the reasoning results of multiple models and selected a subset of problems where the models' outputs aligned with rule-based evaluations. Finally, each problem was manually verified to ensure that the answer format is sufficiently simple and clear, making it suitable for rule-based evaluation. 

*Note: The rule-based evaluation are also suitable for evaluating the inference results of other mathematical datasets such as gsm8k and MATH.*

## 👨‍💻 Usage

1. Use VLLM to perform model inference and save the results.
```
bash inference/inference.sh
```

2. Modify the result path.
3. Evaluate the inference results using `evaluation/eval.sh`.
```
bash evaluation/eval.sh
```

## 📊 Rule-based Evaluation Results
To validate the correctness of our method, we conducted evaluations on open-source models using this repository. The evaluation results are as follows and **are generally consistent with the results on the Omni-MATH leaderboard(GPT-4o Evaluation)**.
| Model | Rule-based Accuracy |
| --- | --- |
| o1-mini   | 62.2% |
| o1-preview | 51.7% |
| Qwen-QwQ | 49.6% |
| qwen2.5-MATH-72b-Instruct | 36.2% |
| qwen2.5-MATH-7b-Instruct | 32.3% |
| GPT-4o | 29.2% |
| NuminaMATH-72b-cot | 26.2% |
| DeepseekMATH-7b-RL | 14.9% |


## 🔌 API-based Inference

In addition to the vLLM pipeline, this repo supports API-based inference for closed-source models (e.g. GPT-5.2). Two prompt modes are available:

- **standard** — standard CoT with `\boxed{}` final answer
- **cautious** — instructs the model to say `\boxed{UNSURE}` rather than guess, enabling precision-focused evaluation

### Prerequisites

```bash
pip install openai tqdm
export OPENAI_API_KEY="sk-..."
```

### Running Inference

```bash
# Standard prompt, 100 problems
python inference/inference_api.py \
  --provider openai --model gpt-5.2 \
  --save_path inference/results/GPT-5.2_standard.jsonl \
  --prompt standard --num_samples 100

# Cautious prompt, 100 problems
python inference/inference_api.py \
  --provider openai --model gpt-5.2 \
  --save_path inference/results/GPT-5.2_cautious.jsonl \
  --prompt cautious --num_samples 100
```

Use `--num_samples 0` for the full dataset (2,821 problems). Inference is resume-safe — rerun the same command to skip already-completed items.

### Evaluating Results

```bash
# Evaluate standard results (existing pipeline)
cd evaluation
bash sh/eval.sh omni-math ../inference/results/GPT-5.2_standard.jsonl GPT-5.2-standard

# Evaluate cautious results (3-way classification)
python math_eval_cautious.py \
  --data_file ../inference/results/GPT-5.2_cautious.jsonl \
  --output_dir output/GPT-5.2-cautious/omni-math/
```

### Viewing Results

```bash
# Standard metrics (accuracy %)
cat evaluation/output/GPT-5.2-standard/omni-math/math_eval_cot_metrics.json

# Cautious metrics (accuracy of attempted, abstentions, mixed errors)
cat evaluation/output/GPT-5.2-cautious/omni-math/cautious_metrics.json

# Per-problem cautious details
cat evaluation/output/GPT-5.2-cautious/omni-math/cautious_eval.jsonl
```

The cautious evaluator classifies each problem into one of four categories:
| Category | Condition |
|---|---|
| `correct` | No UNSURE, last boxed answer matches ground truth |
| `incorrect_standard` | No UNSURE, last boxed answer is wrong |
| `incorrect_mixed` | Has both UNSURE and non-UNSURE boxed values |
| `abstained` | All boxed values are UNSURE (excluded from accuracy) |

### Adding New Providers

Create a new file in `inference/providers/` implementing the `Provider` base class, then register it in `inference/providers/__init__.py`. See `openai_provider.py` for reference.

## 🎖️ Acknowledgements

We would like to thank the [Qwen2.5-MATH](https://github.com/QwenLM/Qwen2.5-MATH) projects as well as the people who gave us this rule-based evaluation suggestion.

## 💬 Citation
If you find our work interesting and meaningful, welcome to give a 🌟 to our repo and cite our paper.
```
@misc{gao2024omnimathuniversalolympiadlevel,
      title={Omni-MATH: A Universal Olympiad Level Mathematic Benchmark For Large Language Models}, 
      author={Bofei Gao and Feifan Song and Zhe Yang and Zefan Cai and Yibo Miao and Qingxiu Dong and Lei Li and Chenghao Ma and Liang Chen and Runxin Xu and Zhengyang Tang and Benyou Wang and Daoguang Zan and Shanghaoran Quan and Ge Zhang and Lei Sha and Yichang Zhang and Xuancheng Ren and Tianyu Liu and Baobao Chang},
      year={2024},
      eprint={2410.07985},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2410.07985}, 
}
```