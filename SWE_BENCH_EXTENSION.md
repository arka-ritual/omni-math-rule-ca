# SWE-bench Pro Consequence Asymmetry Extension

## Implementation Status

### ✅ Completed (Phase 1 - Core Infrastructure)

1. **Prompt Design** (`inference/prompts_swe.py`)
   - Created 7 prompts matching exact structure of math experiments
   - All prompts start with "You are a helpful and harmless assistant." (except natural_grading variants)
   - Escalation levels: standard → cautious → ultra_cautious → reward_lives_1_10 → reward_lives_1_humanity → natural_grading → natural_grading_2
   - Abstention mechanism: SKIP keyword (vs \boxed{UNSURE} in math)

2. **Dataset Loader** (`inference/swe_dataset_loader.py`)
   - Supports loading from HuggingFace or JSONL
   - Deterministic subset creation with seed 42
   - Problem formatting for inference (Repository + problem_statement)
   - Created test dataset (`swe_bench_pro_test.jsonl`) with 5 synthetic problems

3. **Inference Pipeline** (`inference/inference_api_swe.py`)
   - Adapted from `inference_api.py`
   - Async with semaphore, resume-safe, immediate writes
   - Stores output in `model_patch` field
   - Identical CLI to math inference
   - **Status:** Code complete, network connectivity issues prevent testing

4. **Evaluation Parser** (`evaluation/swe_parser.py`)
   - SKIP keyword detection with false positive filtering
   - Patch extraction from diff format or code blocks
   - 3-way classification: skip_only, patch_only, mixed, empty
   - **Status:** Fully tested, all test cases passing

5. **Test Executor** (`evaluation/swe_test_executor.py`)
   - SimulatedExecutor: Fast string similarity-based evaluation
   - DockerExecutor: Placeholder for SWE-bench harness integration
   - **Status:** Simulated mode tested and working

6. **Cautious Evaluator** (`evaluation/swe_eval_cautious.py`)
   - Mirrors `math_eval_cautious.py` structure exactly
   - 3-way classification: abstained / incorrect_mixed / correct / incorrect_standard
   - Metrics: num_total, num_abstained, num_attempted, num_correct, accuracy_of_attempted
   - **Status:** Code complete, ready for testing

### 🔄 In Progress (Phase 2)

1. **Dataset Acquisition**
   - Need to download SWE-bench Pro from HuggingFace
   - Network connectivity issues preventing download
   - **Workaround:** Created synthetic test dataset for infrastructure validation
   - **Next step:** Retry download with stable network or use cached version

2. **End-to-End Testing**
   - Infrastructure ready but blocked by network issues
   - Need to test: inference → evaluation pipeline
   - **Next step:** Test with local mock responses or wait for network

### 📋 TODO (Phase 3 & 4)

1. **Baseline Experiments**
   - Run standard prompt on 100 problems (all 3 models)
   - Evaluate with simulated executor
   - Verify models generate parseable patches

2. **Consequence Asymmetry Experiments**
   - Run all 7 prompts × 3 models = 21 runs
   - Measure abstention rates by prompt
   - Compare to math results

3. **Docker Evaluation** (Optional, Phase 5)
   - Integrate SWE-bench official harness
   - Replace simulated executor
   - Re-run experiments for production numbers

4. **Sequential Environment** (Optional, Phase 6)
   - Adapt `inference/sequential/` for SWE
   - Test quantitative vs qualitative framing

## File Structure

```
omni-math-rule-ca/
├── inference/
│   ├── prompts_swe.py                  # ✅ 7 SWE-specific prompts
│   ├── swe_dataset_loader.py           # ✅ Dataset loading utilities
│   ├── inference_api_swe.py            # ✅ SWE inference pipeline
│   └── results/
│       └── swe_test_standard.jsonl     # 🔄 Test results (pending)
├── evaluation/
│   ├── swe_parser.py                   # ✅ SKIP detection & patch extraction
│   ├── swe_test_executor.py            # ✅ Test execution (simulated/docker)
│   ├── swe_eval_cautious.py            # ✅ 3-way evaluator
│   └── output/
│       └── swe-test-standard/          # 🔄 Evaluation output (pending)
├── swe_bench_pro_test.jsonl            # ✅ Synthetic test dataset (5 problems)
├── swe_bench_pro_100.jsonl             # 📋 TODO: Real dataset subset
└── SWE_BENCH_EXTENSION.md              # 📄 This file
```

## Verification Steps

### 1. Prompt Structure Check
```python
from inference.prompts_swe import PROMPTS_SWE

# All should start with same prefix (except natural_grading)
for key in PROMPTS_SWE:
    if 'natural' not in key:
        assert PROMPTS_SWE[key].startswith("You are a helpful")
```
**Status:** ✅ Verified

### 2. Abstention Detection Test
```bash
python evaluation/swe_parser.py
```
**Status:** ✅ All 8 test cases passing

### 3. Simulated Executor Test
```bash
python evaluation/swe_test_executor.py
```
**Status:** ✅ All 3 test cases passing

### 4. End-to-End Smoke Test
```bash
# Run 2 problems with standard prompt
source setup_keys.sh
python inference/inference_api_swe.py \
  --provider openai --model gpt-4o-mini \
  --data_file swe_bench_pro_test.jsonl \
  --save_path inference/results/swe_test_standard.jsonl \
  --prompt standard --num_samples 2

# Evaluate
python evaluation/swe_eval_cautious.py \
  --data_file inference/results/swe_test_standard.jsonl \
  --output_dir evaluation/output/swe-test-standard/

# Check metrics
cat evaluation/output/swe-test-standard/cautious_metrics.json
```
**Status:** 🔄 Blocked by network connectivity issues

## Network Issues Encountered

1. **HuggingFace Dataset Download**
   - Error: `ConnectionError: Couldn't reach 'ScaleAI/SWE-bench_Pro' on the Hub (ProxyError)`
   - Cause: SOCKS proxy configuration interfering with requests

2. **API Inference**
   - Error: `ImportError: Using SOCKS proxy, but the 'socksio' package is not installed`
   - Error: `httpx.ConnectError: [Errno 8] nodename nor servname provided, or not known`
   - Attempted: Unsetting proxy variables, still connection errors
   - **Recommendation:** Run on different network or install `httpx[socks]`

## Next Steps

1. **Immediate (to unblock testing):**
   - Option A: Install `pip install httpx[socks]` and retry with proxy
   - Option B: Use different network without proxy
   - Option C: Create mock responses for dry-run testing

2. **Phase 2 (Dataset):**
   - Download SWE-bench Pro full dataset (731 problems)
   - Create 100-problem subset with seed 42
   - Verify dataset format matches expected structure

3. **Phase 3 (Baseline):**
   - Run standard prompt: 100 problems × 3 models
   - Evaluate with simulated executor
   - Analyze: Do models generate valid patches?

4. **Phase 4 (Experiments):**
   - Run all 7 prompts × 3 models
   - Compare abstention rates vs math experiments
   - Key question: Does consequence insensitivity generalize to code?

## Expected Outcomes

Based on math experiment results, we predict:

- **Claude Opus 4.6:** <5% abstention even on nuclear prompt (ignores consequences)
- **GPT-5.2:** Either panic-skip everything or minimal calibration
- **Gemini-3-Pro:** Moderate skipping but poor precision filtering

**If predictions hold:** Strong evidence that models cannot process consequence information regardless of domain.

**If predictions fail:** Domain differences matter - code generation may have different calibration properties.

## Budget Estimates

- **API costs (100 problems):**
  - Claude Opus 4.6: ~$30-50 per run
  - 7 prompts × 3 models = 21 runs × $40 = ~$840 total
  - Scale to 200: ~$1,680 total

- **Time estimates:**
  - Simulated eval: minutes per 100 problems
  - Docker eval: hours per 100 problems (5 min/problem)

## Code Quality Notes

All new code follows the existing patterns from the math experiments:

- **Async inference** with semaphore for concurrency
- **Resume-safe** via idx checking
- **Immediate writes** to prevent data loss
- **3-way classification** matching math evaluator structure
- **Identical CLI** flags and patterns

The implementation is production-ready pending network resolution and dataset acquisition.
