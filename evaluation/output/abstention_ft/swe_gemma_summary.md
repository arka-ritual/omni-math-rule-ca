# SWE-bench Pro — Gemma 4 E2B abstention eval

Abstention rate = #Abstained / N; selective accuracy = #correct / N; N = rows in `eval/eval_results.json` (errored runs excluded). Normalized utility = `(correct − penalty×incorrect)/N` for quant framings.

| Model | Method | Train abst % | Epoch | Framing | N (eval rows) | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | DPO | 10% | 0.25 | quant_m5 | 26 | 0 | 26 | 1 | 3.8% | 0.0% | -5.00 |
| Gemma 4 E2B | DPO | 10% | 0.25 | quant_m25 | 22 | 1 | 21 | 0 | 0.0% | 4.5% | -23.82 |
| Gemma 4 E2B | DPO | 10% | 0.25 | quant_m100 | 27 | 2 | 25 | 0 | 0.0% | 7.4% | -92.52 |
| Gemma 4 E2B | DPO | 10% | 0.25 | QP1 | 22 | 1 | 21 | 1 | 4.5% | 4.5% | — |
| Gemma 4 E2B | DPO | 10% | 0.25 | QP4 | 27 | 0 | 27 | 7 | 25.9% | 0.0% | — |
| Gemma 4 E2B | DPO | 10% | 0.25 | QP7 | 32 | 0 | 32 | 3 | 9.4% | 0.0% | — |
| Gemma 4 E2B | DPO | 10% | 0.5 | quant_m5 | 34 | 0 | 34 | 0 | 0.0% | 0.0% | -5.00 |
| Gemma 4 E2B | DPO | 10% | 0.5 | quant_m25 | 28 | 1 | 27 | 0 | 0.0% | 3.6% | -24.07 |
| Gemma 4 E2B | DPO | 10% | 0.5 | quant_m100 | 22 | 1 | 21 | 0 | 0.0% | 4.5% | -95.41 |
| Gemma 4 E2B | DPO | 10% | 0.5 | QP1 | 29 | 0 | 29 | 4 | 13.8% | 0.0% | — |
| Gemma 4 E2B | DPO | 10% | 0.5 | QP4 | 18 | 1 | 17 | 8 | 44.4% | 5.6% | — |
| Gemma 4 E2B | DPO | 50% | 1 | quant_m5 | 39 | 2 | 37 | 0 | 0.0% | 5.1% | -4.69 |
| Gemma 4 E2B | DPO | 50% | 1 | quant_m25 | 33 | 0 | 33 | 0 | 0.0% | 0.0% | -25.00 |
| Gemma 4 E2B | DPO | 50% | 1 | quant_m100 | 40 | 1 | 39 | 0 | 0.0% | 2.5% | -97.47 |
| Gemma 4 E2B | DPO | 50% | 1 | QP1 | 29 | 0 | 29 | 0 | 0.0% | 0.0% | — |
| Gemma 4 E2B | DPO | 50% | 1 | QP4 | 36 | 3 | 33 | 4 | 11.1% | 8.3% | — |
| Gemma 4 E2B | DPO | 50% | 1 | QP7 | 40 | 2 | 38 | 1 | 2.5% | 5.0% | — |
| Gemma 4 E2B | DPO | 75% | 1 | quant_m5 | 37 | 1 | 36 | 0 | 0.0% | 2.7% | -4.84 |
| Gemma 4 E2B | DPO | 75% | 1 | quant_m25 | 38 | 3 | 35 | 0 | 0.0% | 7.9% | -22.95 |
| Gemma 4 E2B | DPO | 75% | 1 | quant_m100 | 36 | 2 | 34 | 0 | 0.0% | 5.6% | -94.39 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | quant_m5 | 23 | 0 | 23 | 0 | 0.0% | 0.0% | -5.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | quant_m25 | 27 | 0 | 27 | 1 | 3.7% | 0.0% | -25.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | quant_m100 | 33 | 0 | 33 | 0 | 0.0% | 0.0% | -100.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | QP1 | 30 | 0 | 30 | 4 | 13.3% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | QP4 | 24 | 0 | 24 | 1 | 4.2% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | QP7 | 30 | 0 | 30 | 3 | 10.0% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | quant_m5 | 31 | 0 | 31 | 0 | 0.0% | 0.0% | -5.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | quant_m25 | 32 | 0 | 32 | 2 | 6.2% | 0.0% | -25.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | quant_m100 | 22 | 0 | 22 | 1 | 4.5% | 0.0% | -100.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | QP1 | 32 | 0 | 32 | 1 | 3.1% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | QP4 | 21 | 0 | 21 | 9 | 42.9% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 1 | quant_m5 | 36 | 0 | 36 | 0 | 0.0% | 0.0% | -5.00 |
| Gemma 4 E2B | SFT-Box | 50% | 1 | quant_m25 | 33 | 0 | 33 | 0 | 0.0% | 0.0% | -25.00 |
| Gemma 4 E2B | SFT-Box | 50% | 1 | quant_m100 | 35 | 0 | 35 | 0 | 0.0% | 0.0% | -100.00 |
| Gemma 4 E2B | SFT-Box | 50% | 1 | QP1 | 34 | 0 | 34 | 3 | 8.8% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 1 | QP4 | 23 | 0 | 23 | 9 | 39.1% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 1 | QP7 | 38 | 0 | 38 | 3 | 7.9% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 75% | 1 | quant_m5 | 38 | 0 | 38 | 0 | 0.0% | 0.0% | -5.00 |
| Gemma 4 E2B | SFT-Box | 75% | 1 | quant_m25 | 40 | 0 | 40 | 0 | 0.0% | 0.0% | -25.00 |
| Gemma 4 E2B | SFT-Box | 75% | 1 | quant_m100 | 37 | 0 | 37 | 2 | 5.4% | 0.0% | -100.00 |
| Gemma 4 E2B | SFT-Box | 75% | 1 | QP1 | 28 | 0 | 28 | 0 | 0.0% | 0.0% | — |