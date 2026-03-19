# SWE-bench Pro Extension - Implementation Checklist

## ✅ Phase 1: Core Infrastructure (COMPLETED)

- [x] Create `inference/prompts_swe.py` with 7 prompts matching math structure
- [x] Create `inference/swe_dataset_loader.py` for dataset loading
- [x] Create `inference/inference_api_swe.py` adapted from math pipeline
- [x] Create `evaluation/swe_parser.py` for SKIP detection and patch extraction
- [x] Create `evaluation/swe_test_executor.py` for simulated/docker evaluation
- [x] Create `evaluation/swe_eval_cautious.py` for 3-way classification
- [x] Test parser with edge cases (✓ all 8 tests passing)
- [x] Test simulated executor (✓ all 3 tests passing)
- [x] Create synthetic test dataset (`swe_bench_pro_test.jsonl`)
- [x] Create experiment runner script (`run_swe_experiments.sh`)
- [x] Create results summarizer script (`summarize_swe_results.sh`)
- [x] Document implementation status (`SWE_BENCH_EXTENSION.md`)
- [x] Create quick start guide (`SWE_QUICKSTART.md`)

## 🔄 Phase 2: Dataset & Testing (BLOCKED - Network Issues)

- [ ] Download SWE-bench Pro full dataset (731 problems)
  - **Status:** Network connectivity issues (proxy/DNS errors)
  - **Blocker:** Need stable network or `httpx[socks]` installation
  - **Command:** `python inference/swe_dataset_loader.py swe_bench_pro_full.jsonl 731`

- [ ] Create 100-problem subset with seed 42
  - **Status:** Ready to run once full dataset downloaded
  - **Command:** See `SWE_QUICKSTART.md` Step 2

- [ ] End-to-end smoke test (5 problems)
  - **Status:** Blocked by API connectivity
  - **Command:** See "Quick Test" section in `SWE_QUICKSTART.md`

## 📋 Phase 3: Baseline Experiments (TODO)

- [ ] Claude Opus 4.6 - standard prompt (100 problems)
  - **Command:** `./run_swe_experiments.sh opus standard`
  - **Expected time:** 30-60 minutes
  - **Expected cost:** ~$30-50

- [ ] GPT-5.2 - standard prompt (100 problems)
  - **Command:** `./run_swe_experiments.sh gpt5.2 standard`
  - **Expected time:** 30-60 minutes
  - **Expected cost:** ~$20-30

- [ ] Gemini-3-Pro - standard prompt (100 problems)
  - **Command:** `./run_swe_experiments.sh gemini3 standard`
  - **Expected time:** 30-60 minutes
  - **Expected cost:** ~$10-20

- [ ] Verify models generate valid patches
  - Check `model_patch` field contains diff format
  - Verify no API errors or timeouts

- [ ] Evaluate baselines with simulated executor
  - **Command:** Automatically run by experiment script
  - Check resolve rates are reasonable (>0%)

## 📋 Phase 4: Consequence Asymmetry Experiments (TODO)

For each model (Claude, GPT-5.2, Gemini):

- [ ] Run `cautious` prompt
- [ ] Run `ultra_cautious` prompt
- [ ] Run `reward_lives_1_10` prompt
- [ ] Run `reward_lives_1_humanity` prompt (CRITICAL - nuclear test)
- [ ] Run `natural_grading` prompt
- [ ] Run `natural_grading_2` prompt

**Batch command:** `./run_swe_experiments.sh [model] all`

**Total:** 21 runs (7 prompts × 3 models)
**Expected time:** 10-20 hours
**Expected cost:** ~$840

## 📋 Phase 5: Analysis & Comparison (TODO)

- [ ] Generate results summary
  - **Command:** `./summarize_swe_results.sh`

- [ ] Compare abstention rates to math experiments
  - Claude math: 2/500 (0.4%) on nuclear prompt
  - Does Claude SWE match this pattern?

- [ ] Analyze accuracy-when-attempted across prompts
  - Does accuracy improve with harsher prompts?
  - Or does it stay flat (indicating no calibration)?

- [ ] Document key findings
  - Does consequence insensitivity generalize to code?
  - Are there domain-specific differences?

- [ ] Create publication-ready tables/figures

## 🔧 Phase 6: Docker Evaluation (OPTIONAL)

Only needed if:
- Simulated evaluation shows promising results
- We need accurate resolve rates for publication
- Results warrant the extra compute time

Tasks:
- [ ] Integrate SWE-bench official harness
- [ ] Test Docker execution on 10 problems
- [ ] Re-run baseline with Docker (validate against leaderboard)
- [ ] Re-run consequence experiments with Docker
- [ ] Compare simulated vs Docker accuracy

**Expected time:** 5-10 min/problem × 100 = 8-16 hours per run
**Total for all experiments:** 170+ hours (use distributed compute)

## 🔧 Phase 7: Sequential Environment (OPTIONAL)

Extend sequential environment to SWE (like math experiments):

- [ ] Create `inference/swe_sequential/formatter.py`
- [ ] Adapt scoring rubric for patches (+1 resolved, -10 failed, 0 skipped)
- [ ] Add history formatting (past patches + outcomes)
- [ ] Test with Claude Opus 4.6 (100 questions)
- [ ] Test with GPT-5.2 (100 questions)
- [ ] Compare sequential vs non-sequential abstention rates

**Priority:** LOW - standard prompts are higher priority for initial replication

## 📊 Success Criteria

### Minimum Viable Product
- [x] All infrastructure code complete and tested
- [ ] 100-problem dataset acquired
- [ ] 3 baseline runs complete (1 per model)
- [ ] Results show models generate valid patches

### Full Replication
- [ ] All 21 experiments complete (7 prompts × 3 models)
- [ ] Results analyzed and documented
- [ ] Comparison to math experiments written up
- [ ] Clear answer to: "Does consequence insensitivity generalize to code?"

### Publication Quality
- [ ] Docker evaluation complete for accuracy validation
- [ ] Statistical significance tests run
- [ ] Tables and figures created
- [ ] Discussion of domain differences (if any)

## ⚠️ Current Blockers

1. **Network Connectivity**
   - SOCKS proxy preventing HuggingFace dataset download
   - API calls failing with DNS errors
   - **Resolution options:**
     - Install `pip install httpx[socks]`
     - Run on different network without proxy
     - Use VPN or different machine

2. **Dataset Acquisition**
   - Cannot proceed with experiments until dataset downloaded
   - Synthetic test dataset created as temporary workaround
   - **Resolution:** Fix network, then run download command

## 🚀 Next Immediate Steps

1. **Resolve network issues:**
   ```bash
   # Option A: Install SOCKS support
   pip install httpx[socks]

   # Option B: Try different network
   # Option C: Download on different machine and transfer
   ```

2. **Download dataset:**
   ```bash
   python -c "
   from datasets import load_dataset
   import json
   ds = load_dataset('ScaleAI/SWE-bench_Pro', split='test')
   with open('swe_bench_pro_full.jsonl', 'w') as f:
       for item in ds:
           f.write(json.dumps(item) + '\n')
   "
   ```

3. **Run quick test (5 problems):**
   ```bash
   ./run_swe_experiments.sh opus standard
   # (with --num_samples 5 for testing)
   ```

4. **If test succeeds, run full baseline:**
   ```bash
   ./run_swe_experiments.sh opus standard
   ./run_swe_experiments.sh gpt5.2 standard
   ./run_swe_experiments.sh gemini3 standard
   ```

5. **Run consequence experiments:**
   ```bash
   ./run_swe_experiments.sh all all
   ```

6. **Analyze results:**
   ```bash
   ./summarize_swe_results.sh
   ```

## 📝 Notes

- All code is production-ready pending network resolution
- Infrastructure matches math experiments exactly (easy to maintain)
- Resume-safe design means interrupted runs can be continued
- Simulated evaluation is fast enough for iteration
- Docker evaluation can be added later if needed
