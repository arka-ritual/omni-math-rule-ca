# Abstention Fine-Tuning — Consolidated Eval Summary

Tables grouped by (model, training method, train-dataset abstention %). Each row is a (framing × epoch) eval cell. Normalized Utility = `(correct − penalty × incorrect) / total` for quantitative framings (penalty 5/25/100); left blank for qualitative QP framings.

## Gemma 4 E2B · SFT-Box · train abstention 10%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | quant_m5 | 35 | 39 | 26 | 26.0% | 47.3% | -1.60 |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | quant_m5 | 1 | 6 | 93 | 93.0% | 14.3% | -0.29 |
| Gemma 4 E2B | SFT-Box | 10% | 0.75 | quant_m5 | 0 | 12 | 88 | 88.0% | 0.0% | -0.60 |
| Gemma 4 E2B | SFT-Box | 10% | 1 | quant_m5 | 0 | 41 | 59 | 59.0% | 0.0% | -2.05 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | quant_m25 | 35 | 23 | 42 | 42.0% | 60.3% | -5.40 |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | quant_m25 | 1 | 4 | 95 | 95.0% | 20.0% | -0.99 |
| Gemma 4 E2B | SFT-Box | 10% | 0.75 | quant_m25 | 0 | 8 | 92 | 92.0% | 0.0% | -2.00 |
| Gemma 4 E2B | SFT-Box | 10% | 1 | quant_m25 | 0 | 20 | 80 | 80.0% | 0.0% | -5.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | quant_m100 | 37 | 32 | 31 | 31.0% | 53.6% | -31.63 |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | quant_m100 | 1 | 10 | 89 | 89.0% | 9.1% | -9.99 |
| Gemma 4 E2B | SFT-Box | 10% | 0.75 | quant_m100 | 0 | 33 | 67 | 67.0% | 0.0% | -33.00 |
| Gemma 4 E2B | SFT-Box | 10% | 1 | quant_m100 | 0 | 57 | 43 | 43.0% | 0.0% | -57.00 |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | QP1 | 39 | 44 | 17 | 17.0% | 47.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | QP1 | 6 | 2 | 92 | 92.0% | 75.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.75 | QP1 | 0 | 6 | 94 | 94.0% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 1 | QP1 | 0 | 4 | 96 | 96.0% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | QP4 | 40 | 29 | 31 | 31.0% | 58.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | QP4 | 5 | 0 | 95 | 95.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.75 | QP4 | 0 | 3 | 97 | 97.0% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 1 | QP4 | 0 | 2 | 98 | 98.0% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.25 | QP7 | 32 | 46 | 22 | 22.0% | 41.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.5 | QP7 | 1 | 5 | 94 | 94.0% | 16.7% | — |
| Gemma 4 E2B | SFT-Box | 10% | 0.75 | QP7 | 0 | 3 | 97 | 97.0% | 0.0% | — |
| Gemma 4 E2B | SFT-Box | 10% | 1 | QP7 | 0 | 2 | 98 | 98.0% | 0.0% | — |

## Gemma 4 E2B · SFT-Box · train abstention 25%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | SFT-Box | 25% | 0.25 | quant_m5 | 32 | 29 | 39 | 39.0% | 52.5% | -1.13 |
| Gemma 4 E2B | SFT-Box | 25% | 0.5 | quant_m5 | 1 | 1 | 98 | 98.0% | 50.0% | -0.04 |
| Gemma 4 E2B | SFT-Box | 25% | 0.75 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 25% | 1 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 25% | 0.25 | quant_m25 | 34 | 26 | 40 | 40.0% | 56.7% | -6.16 |
| Gemma 4 E2B | SFT-Box | 25% | 0.5 | quant_m25 | 1 | 1 | 98 | 98.0% | 50.0% | -0.24 |
| Gemma 4 E2B | SFT-Box | 25% | 0.75 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 25% | 1 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 25% | 0.25 | quant_m100 | 30 | 27 | 43 | 43.0% | 52.6% | -26.70 |
| Gemma 4 E2B | SFT-Box | 25% | 0.5 | quant_m100 | 1 | 4 | 95 | 95.0% | 20.0% | -3.99 |
| Gemma 4 E2B | SFT-Box | 25% | 0.75 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 25% | 1 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 25% | 0.25 | QP1 | 38 | 31 | 31 | 31.0% | 55.1% | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.5 | QP1 | 7 | 7 | 86 | 86.0% | 50.0% | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.75 | QP1 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 25% | 1 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.25 | QP4 | 29 | 32 | 39 | 39.0% | 47.5% | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.5 | QP4 | 6 | 2 | 92 | 92.0% | 75.0% | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.75 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 25% | 1 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.25 | QP7 | 34 | 41 | 25 | 25.0% | 45.3% | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.5 | QP7 | 3 | 2 | 95 | 95.0% | 60.0% | — |
| Gemma 4 E2B | SFT-Box | 25% | 0.75 | QP7 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 25% | 1 | QP7 | 0 | 0 | 100 | 100.0% | — | — |

## Gemma 4 E2B · SFT-Box · train abstention 50%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | SFT-Box | 50% | 0.25 | quant_m5 | 28 | 25 | 47 | 47.0% | 52.8% | -0.97 |
| Gemma 4 E2B | SFT-Box | 50% | 0.5 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 0.75 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 1 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 2 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 0.25 | quant_m25 | 30 | 25 | 45 | 45.0% | 54.5% | -5.95 |
| Gemma 4 E2B | SFT-Box | 50% | 0.5 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 0.75 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 1 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 2 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 0.25 | quant_m100 | 31 | 23 | 46 | 46.0% | 57.4% | -22.69 |
| Gemma 4 E2B | SFT-Box | 50% | 0.5 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 0.75 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 1 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 2 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 50% | 0.25 | QP1 | 34 | 30 | 36 | 36.0% | 53.1% | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.5 | QP1 | 3 | 0 | 97 | 97.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.75 | QP1 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 1 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 2 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.25 | QP4 | 31 | 19 | 50 | 50.0% | 62.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.5 | QP4 | 2 | 0 | 98 | 98.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.75 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 1 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 2 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.25 | QP7 | 35 | 31 | 34 | 34.0% | 53.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.5 | QP7 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 50% | 0.75 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 1 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 50% | 2 | QP7 | 0 | 0 | 100 | 100.0% | — | — |

## Gemma 4 E2B · SFT-Box · train abstention 75%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | SFT-Box | 75% | 0.25 | quant_m5 | 18 | 9 | 73 | 73.0% | 66.7% | -0.27 |
| Gemma 4 E2B | SFT-Box | 75% | 0.5 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 0.75 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 1 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 2 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 4 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 0.25 | quant_m25 | 13 | 5 | 82 | 82.0% | 72.2% | -1.12 |
| Gemma 4 E2B | SFT-Box | 75% | 0.5 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 0.75 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 1 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 2 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 4 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 0.25 | quant_m100 | 15 | 5 | 80 | 80.0% | 75.0% | -4.85 |
| Gemma 4 E2B | SFT-Box | 75% | 0.5 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 0.75 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 1 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 2 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 4 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 75% | 0.25 | QP1 | 27 | 14 | 59 | 59.0% | 65.9% | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.5 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.75 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 1 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 2 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 4 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.25 | QP4 | 28 | 13 | 59 | 59.0% | 68.3% | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.5 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.75 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 1 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 2 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 4 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.25 | QP7 | 31 | 13 | 56 | 56.0% | 70.5% | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.5 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 0.75 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 1 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 2 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 75% | 4 | QP7 | 0 | 0 | 100 | 100.0% | — | — |

## Gemma 4 E2B · SFT-Box · train abstention 90%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | SFT-Box | 90% | 0.25 | quant_m5 | 7 | 6 | 87 | 87.0% | 53.8% | -0.23 |
| Gemma 4 E2B | SFT-Box | 90% | 0.5 | quant_m5 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 0.75 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 90% | 1 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 90% | 2 | quant_m5 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 4 | quant_m5 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 0.25 | quant_m25 | 11 | 3 | 86 | 86.0% | 78.6% | -0.64 |
| Gemma 4 E2B | SFT-Box | 90% | 0.5 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 90% | 0.75 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 90% | 1 | quant_m25 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 90% | 2 | quant_m25 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 4 | quant_m25 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 0.25 | quant_m100 | 14 | 4 | 82 | 82.0% | 77.8% | -3.86 |
| Gemma 4 E2B | SFT-Box | 90% | 0.5 | quant_m100 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 0.75 | quant_m100 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 1 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Gemma 4 E2B | SFT-Box | 90% | 2 | quant_m100 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 4 | quant_m100 | 1 | 0 | 99 | 99.0% | 100.0% | 0.01 |
| Gemma 4 E2B | SFT-Box | 90% | 0.25 | QP1 | 31 | 20 | 49 | 49.0% | 60.8% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.5 | QP1 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.75 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 90% | 1 | QP1 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 2 | QP1 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 4 | QP1 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.25 | QP4 | 29 | 17 | 54 | 54.0% | 63.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.5 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.75 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 1 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 2 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 4 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.25 | QP7 | 28 | 22 | 50 | 50.0% | 56.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.5 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 90% | 0.75 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 90% | 1 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Gemma 4 E2B | SFT-Box | 90% | 2 | QP7 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | SFT-Box | 90% | 4 | QP7 | 0 | 0 | 100 | 100.0% | — | — |

## Gemma 4 E2B · DPO · train abstention 10%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | DPO | 10% | 0.25 | quant_m5 | 39 | 44 | 17 | 17.0% | 47.0% | -1.81 |
| Gemma 4 E2B | DPO | 10% | 0.5 | quant_m5 | 31 | 12 | 57 | 57.0% | 72.1% | -0.29 |
| Gemma 4 E2B | DPO | 10% | 0.75 | quant_m5 | 22 | 10 | 68 | 68.0% | 68.8% | -0.28 |
| Gemma 4 E2B | DPO | 10% | 1 | quant_m5 | 24 | 11 | 65 | 65.0% | 68.6% | -0.31 |
| Gemma 4 E2B | DPO | 10% | 2 | quant_m5 | 18 | 7 | 75 | 75.0% | 72.0% | -0.17 |
| Gemma 4 E2B | DPO | 10% | 4 | quant_m5 | 18 | 8 | 74 | 74.0% | 69.2% | -0.22 |
| Gemma 4 E2B | DPO | 10% | 0.25 | quant_m25 | 38 | 43 | 19 | 19.0% | 46.9% | -10.37 |
| Gemma 4 E2B | DPO | 10% | 0.5 | quant_m25 | 25 | 11 | 64 | 64.0% | 69.4% | -2.50 |
| Gemma 4 E2B | DPO | 10% | 0.75 | quant_m25 | 24 | 9 | 67 | 67.0% | 72.7% | -2.01 |
| Gemma 4 E2B | DPO | 10% | 1 | quant_m25 | 23 | 9 | 68 | 68.0% | 71.9% | -2.02 |
| Gemma 4 E2B | DPO | 10% | 2 | quant_m25 | 28 | 5 | 67 | 67.0% | 84.8% | -0.97 |
| Gemma 4 E2B | DPO | 10% | 4 | quant_m25 | 16 | 5 | 79 | 79.0% | 76.2% | -1.09 |
| Gemma 4 E2B | DPO | 10% | 0.25 | quant_m100 | 37 | 52 | 11 | 11.0% | 41.6% | -51.63 |
| Gemma 4 E2B | DPO | 10% | 0.5 | quant_m100 | 24 | 9 | 67 | 67.0% | 72.7% | -8.76 |
| Gemma 4 E2B | DPO | 10% | 0.75 | quant_m100 | 21 | 8 | 71 | 71.0% | 72.4% | -7.79 |
| Gemma 4 E2B | DPO | 10% | 1 | quant_m100 | 20 | 6 | 74 | 74.0% | 76.9% | -5.80 |
| Gemma 4 E2B | DPO | 10% | 2 | quant_m100 | 17 | 11 | 72 | 72.0% | 60.7% | -10.83 |
| Gemma 4 E2B | DPO | 10% | 4 | quant_m100 | 16 | 5 | 79 | 79.0% | 76.2% | -4.84 |
| Gemma 4 E2B | DPO | 10% | 0.25 | QP1 | 31 | 46 | 23 | 23.0% | 40.3% | — |
| Gemma 4 E2B | DPO | 10% | 0.5 | QP1 | 15 | 8 | 77 | 77.0% | 65.2% | — |
| Gemma 4 E2B | DPO | 10% | 0.75 | QP1 | 15 | 10 | 75 | 75.0% | 60.0% | — |
| Gemma 4 E2B | DPO | 10% | 1 | QP1 | 14 | 8 | 78 | 78.0% | 63.6% | — |
| Gemma 4 E2B | DPO | 10% | 2 | QP1 | 11 | 10 | 79 | 79.0% | 52.4% | — |
| Gemma 4 E2B | DPO | 10% | 4 | QP1 | 9 | 12 | 79 | 79.0% | 42.9% | — |
| Gemma 4 E2B | DPO | 10% | 0.25 | QP4 | 28 | 38 | 34 | 34.0% | 42.4% | — |
| Gemma 4 E2B | DPO | 10% | 0.5 | QP4 | 18 | 8 | 74 | 74.0% | 69.2% | — |
| Gemma 4 E2B | DPO | 10% | 0.75 | QP4 | 10 | 5 | 85 | 85.0% | 66.7% | — |
| Gemma 4 E2B | DPO | 10% | 1 | QP4 | 6 | 10 | 84 | 84.0% | 37.5% | — |
| Gemma 4 E2B | DPO | 10% | 2 | QP4 | 7 | 6 | 87 | 87.0% | 53.8% | — |
| Gemma 4 E2B | DPO | 10% | 4 | QP4 | 8 | 9 | 83 | 83.0% | 47.1% | — |
| Gemma 4 E2B | DPO | 10% | 0.25 | QP7 | 36 | 46 | 18 | 18.0% | 43.9% | — |
| Gemma 4 E2B | DPO | 10% | 0.5 | QP7 | 27 | 10 | 63 | 63.0% | 73.0% | — |
| Gemma 4 E2B | DPO | 10% | 0.75 | QP7 | 23 | 7 | 70 | 70.0% | 76.7% | — |
| Gemma 4 E2B | DPO | 10% | 1 | QP7 | 19 | 9 | 72 | 72.0% | 67.9% | — |
| Gemma 4 E2B | DPO | 10% | 2 | QP7 | 19 | 14 | 67 | 67.0% | 57.6% | — |
| Gemma 4 E2B | DPO | 10% | 4 | QP7 | 14 | 10 | 76 | 76.0% | 58.3% | — |

## Gemma 4 E2B · DPO · train abstention 25%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | DPO | 25% | 0.25 | quant_m5 | 40 | 22 | 38 | 38.0% | 64.5% | -0.70 |
| Gemma 4 E2B | DPO | 25% | 0.5 | quant_m5 | 30 | 18 | 52 | 52.0% | 62.5% | -0.60 |
| Gemma 4 E2B | DPO | 25% | 0.75 | quant_m5 | 22 | 9 | 69 | 69.0% | 71.0% | -0.23 |
| Gemma 4 E2B | DPO | 25% | 1 | quant_m5 | 9 | 7 | 84 | 84.0% | 56.2% | -0.26 |
| Gemma 4 E2B | DPO | 25% | 2 | quant_m5 | 9 | 4 | 87 | 87.0% | 69.2% | -0.11 |
| Gemma 4 E2B | DPO | 25% | 4 | quant_m5 | 8 | 4 | 88 | 88.0% | 66.7% | -0.12 |
| Gemma 4 E2B | DPO | 25% | 0.25 | quant_m25 | 39 | 22 | 39 | 39.0% | 63.9% | -5.11 |
| Gemma 4 E2B | DPO | 25% | 0.5 | quant_m25 | 29 | 12 | 59 | 59.0% | 70.7% | -2.71 |
| Gemma 4 E2B | DPO | 25% | 0.75 | quant_m25 | 22 | 6 | 72 | 72.0% | 78.6% | -1.28 |
| Gemma 4 E2B | DPO | 25% | 1 | quant_m25 | 15 | 2 | 83 | 83.0% | 88.2% | -0.35 |
| Gemma 4 E2B | DPO | 25% | 2 | quant_m25 | 14 | 6 | 80 | 80.0% | 70.0% | -1.36 |
| Gemma 4 E2B | DPO | 25% | 4 | quant_m25 | 8 | 11 | 81 | 81.0% | 42.1% | -2.67 |
| Gemma 4 E2B | DPO | 25% | 0.25 | quant_m100 | 43 | 24 | 33 | 33.0% | 64.2% | -23.57 |
| Gemma 4 E2B | DPO | 25% | 0.5 | quant_m100 | 28 | 17 | 55 | 55.0% | 62.2% | -16.72 |
| Gemma 4 E2B | DPO | 25% | 0.75 | quant_m100 | 18 | 11 | 71 | 71.0% | 62.1% | -10.82 |
| Gemma 4 E2B | DPO | 25% | 1 | quant_m100 | 12 | 7 | 81 | 81.0% | 63.2% | -6.88 |
| Gemma 4 E2B | DPO | 25% | 2 | quant_m100 | 7 | 5 | 88 | 88.0% | 58.3% | -4.93 |
| Gemma 4 E2B | DPO | 25% | 4 | quant_m100 | 8 | 4 | 88 | 88.0% | 66.7% | -3.92 |
| Gemma 4 E2B | DPO | 25% | 0.25 | QP1 | 31 | 20 | 49 | 49.0% | 60.8% | — |
| Gemma 4 E2B | DPO | 25% | 0.5 | QP1 | 21 | 13 | 66 | 66.0% | 61.8% | — |
| Gemma 4 E2B | DPO | 25% | 0.75 | QP1 | 10 | 8 | 82 | 82.0% | 55.6% | — |
| Gemma 4 E2B | DPO | 25% | 1 | QP1 | 14 | 4 | 82 | 82.0% | 77.8% | — |
| Gemma 4 E2B | DPO | 25% | 2 | QP1 | 12 | 4 | 84 | 84.0% | 75.0% | — |
| Gemma 4 E2B | DPO | 25% | 4 | QP1 | 9 | 5 | 86 | 86.0% | 64.3% | — |
| Gemma 4 E2B | DPO | 25% | 0.25 | QP4 | 31 | 20 | 49 | 49.0% | 60.8% | — |
| Gemma 4 E2B | DPO | 25% | 0.5 | QP4 | 27 | 9 | 64 | 64.0% | 75.0% | — |
| Gemma 4 E2B | DPO | 25% | 0.75 | QP4 | 14 | 4 | 82 | 82.0% | 77.8% | — |
| Gemma 4 E2B | DPO | 25% | 1 | QP4 | 12 | 5 | 83 | 83.0% | 70.6% | — |
| Gemma 4 E2B | DPO | 25% | 2 | QP4 | 12 | 6 | 82 | 82.0% | 66.7% | — |
| Gemma 4 E2B | DPO | 25% | 4 | QP4 | 12 | 9 | 79 | 79.0% | 57.1% | — |
| Gemma 4 E2B | DPO | 25% | 0.25 | QP7 | 39 | 22 | 39 | 39.0% | 63.9% | — |
| Gemma 4 E2B | DPO | 25% | 0.5 | QP7 | 31 | 13 | 56 | 56.0% | 70.5% | — |
| Gemma 4 E2B | DPO | 25% | 0.75 | QP7 | 20 | 8 | 72 | 72.0% | 71.4% | — |
| Gemma 4 E2B | DPO | 25% | 1 | QP7 | 15 | 9 | 76 | 76.0% | 62.5% | — |
| Gemma 4 E2B | DPO | 25% | 2 | QP7 | 18 | 7 | 75 | 75.0% | 72.0% | — |
| Gemma 4 E2B | DPO | 25% | 4 | QP7 | 13 | 10 | 77 | 77.0% | 56.5% | — |

## Gemma 4 E2B · DPO · train abstention 50%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | DPO | 50% | 0.25 | quant_m5 | 31 | 21 | 48 | 48.0% | 59.6% | -0.74 |
| Gemma 4 E2B | DPO | 50% | 0.5 | quant_m5 | 22 | 11 | 67 | 67.0% | 66.7% | -0.33 |
| Gemma 4 E2B | DPO | 50% | 0.75 | quant_m5 | 8 | 4 | 88 | 88.0% | 66.7% | -0.12 |
| Gemma 4 E2B | DPO | 50% | 1 | quant_m5 | 5 | 3 | 92 | 92.0% | 62.5% | -0.10 |
| Gemma 4 E2B | DPO | 50% | 2 | quant_m5 | 5 | 4 | 91 | 91.0% | 55.6% | -0.15 |
| Gemma 4 E2B | DPO | 50% | 4 | quant_m5 | 3 | 6 | 91 | 91.0% | 33.3% | -0.27 |
| Gemma 4 E2B | DPO | 50% | 0.25 | quant_m25 | 30 | 23 | 47 | 47.0% | 56.6% | -5.45 |
| Gemma 4 E2B | DPO | 50% | 0.5 | quant_m25 | 24 | 19 | 57 | 57.0% | 55.8% | -4.51 |
| Gemma 4 E2B | DPO | 50% | 0.75 | quant_m25 | 6 | 8 | 86 | 86.0% | 42.9% | -1.94 |
| Gemma 4 E2B | DPO | 50% | 1 | quant_m25 | 2 | 3 | 95 | 95.0% | 40.0% | -0.73 |
| Gemma 4 E2B | DPO | 50% | 2 | quant_m25 | 5 | 0 | 95 | 95.0% | 100.0% | 0.05 |
| Gemma 4 E2B | DPO | 50% | 4 | quant_m25 | 7 | 1 | 92 | 92.0% | 87.5% | -0.18 |
| Gemma 4 E2B | DPO | 50% | 0.25 | quant_m100 | 32 | 18 | 50 | 50.0% | 64.0% | -17.68 |
| Gemma 4 E2B | DPO | 50% | 0.5 | quant_m100 | 22 | 15 | 63 | 63.0% | 59.5% | -14.78 |
| Gemma 4 E2B | DPO | 50% | 0.75 | quant_m100 | 8 | 4 | 88 | 88.0% | 66.7% | -3.92 |
| Gemma 4 E2B | DPO | 50% | 1 | quant_m100 | 7 | 2 | 91 | 91.0% | 77.8% | -1.93 |
| Gemma 4 E2B | DPO | 50% | 2 | quant_m100 | 4 | 3 | 93 | 93.0% | 57.1% | -2.96 |
| Gemma 4 E2B | DPO | 50% | 4 | quant_m100 | 4 | 1 | 95 | 95.0% | 80.0% | -0.96 |
| Gemma 4 E2B | DPO | 50% | 0.25 | QP1 | 29 | 14 | 57 | 57.0% | 67.4% | — |
| Gemma 4 E2B | DPO | 50% | 0.5 | QP1 | 27 | 11 | 62 | 62.0% | 71.1% | — |
| Gemma 4 E2B | DPO | 50% | 0.75 | QP1 | 15 | 5 | 80 | 80.0% | 75.0% | — |
| Gemma 4 E2B | DPO | 50% | 1 | QP1 | 1 | 2 | 97 | 97.0% | 33.3% | — |
| Gemma 4 E2B | DPO | 50% | 2 | QP1 | 1 | 1 | 98 | 98.0% | 50.0% | — |
| Gemma 4 E2B | DPO | 50% | 4 | QP1 | 0 | 1 | 99 | 99.0% | 0.0% | — |
| Gemma 4 E2B | DPO | 50% | 0.25 | QP4 | 30 | 18 | 52 | 52.0% | 62.5% | — |
| Gemma 4 E2B | DPO | 50% | 0.5 | QP4 | 27 | 10 | 63 | 63.0% | 73.0% | — |
| Gemma 4 E2B | DPO | 50% | 0.75 | QP4 | 17 | 3 | 80 | 80.0% | 85.0% | — |
| Gemma 4 E2B | DPO | 50% | 1 | QP4 | 5 | 0 | 95 | 95.0% | 100.0% | — |
| Gemma 4 E2B | DPO | 50% | 2 | QP4 | 1 | 0 | 99 | 99.0% | 100.0% | — |
| Gemma 4 E2B | DPO | 50% | 4 | QP4 | 3 | 0 | 97 | 97.0% | 100.0% | — |
| Gemma 4 E2B | DPO | 50% | 0.25 | QP7 | 34 | 25 | 41 | 41.0% | 57.6% | — |
| Gemma 4 E2B | DPO | 50% | 0.5 | QP7 | 34 | 16 | 50 | 50.0% | 68.0% | — |
| Gemma 4 E2B | DPO | 50% | 0.75 | QP7 | 17 | 9 | 74 | 74.0% | 65.4% | — |
| Gemma 4 E2B | DPO | 50% | 1 | QP7 | 9 | 2 | 89 | 89.0% | 81.8% | — |
| Gemma 4 E2B | DPO | 50% | 2 | QP7 | 8 | 4 | 88 | 88.0% | 66.7% | — |
| Gemma 4 E2B | DPO | 50% | 4 | QP7 | 8 | 1 | 91 | 91.0% | 88.9% | — |

## Gemma 4 E2B · DPO · train abstention 75%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | DPO | 75% | 0.25 | quant_m5 | 38 | 32 | 30 | 30.0% | 54.3% | -1.22 |
| Gemma 4 E2B | DPO | 75% | 0.5 | quant_m5 | 27 | 13 | 60 | 60.0% | 67.5% | -0.38 |
| Gemma 4 E2B | DPO | 75% | 0.75 | quant_m5 | 16 | 7 | 77 | 77.0% | 69.6% | -0.19 |
| Gemma 4 E2B | DPO | 75% | 1 | quant_m5 | 22 | 12 | 66 | 66.0% | 64.7% | -0.38 |
| Gemma 4 E2B | DPO | 75% | 2 | quant_m5 | 17 | 18 | 65 | 65.0% | 48.6% | -0.73 |
| Gemma 4 E2B | DPO | 75% | 4 | quant_m5 | 24 | 14 | 62 | 62.0% | 63.2% | -0.46 |
| Gemma 4 E2B | DPO | 75% | 0.25 | quant_m25 | 35 | 37 | 28 | 28.0% | 48.6% | -8.90 |
| Gemma 4 E2B | DPO | 75% | 0.5 | quant_m25 | 24 | 16 | 60 | 60.0% | 60.0% | -3.76 |
| Gemma 4 E2B | DPO | 75% | 0.75 | quant_m25 | 15 | 8 | 77 | 77.0% | 65.2% | -1.85 |
| Gemma 4 E2B | DPO | 75% | 1 | quant_m25 | 17 | 10 | 73 | 73.0% | 63.0% | -2.33 |
| Gemma 4 E2B | DPO | 75% | 2 | quant_m25 | 19 | 14 | 67 | 67.0% | 57.6% | -3.31 |
| Gemma 4 E2B | DPO | 75% | 4 | quant_m25 | 14 | 18 | 68 | 68.0% | 43.8% | -4.36 |
| Gemma 4 E2B | DPO | 75% | 0.25 | quant_m100 | 32 | 39 | 29 | 29.0% | 45.1% | -38.68 |
| Gemma 4 E2B | DPO | 75% | 0.5 | quant_m100 | 27 | 17 | 56 | 56.0% | 61.4% | -16.73 |
| Gemma 4 E2B | DPO | 75% | 0.75 | quant_m100 | 14 | 7 | 79 | 79.0% | 66.7% | -6.86 |
| Gemma 4 E2B | DPO | 75% | 1 | quant_m100 | 17 | 12 | 71 | 71.0% | 58.6% | -11.83 |
| Gemma 4 E2B | DPO | 75% | 2 | quant_m100 | 19 | 13 | 68 | 68.0% | 59.4% | -12.81 |
| Gemma 4 E2B | DPO | 75% | 4 | quant_m100 | 15 | 16 | 69 | 69.0% | 48.4% | -15.85 |
| Gemma 4 E2B | DPO | 75% | 0.25 | QP1 | 31 | 41 | 28 | 28.0% | 43.1% | — |
| Gemma 4 E2B | DPO | 75% | 0.5 | QP1 | 27 | 10 | 63 | 63.0% | 73.0% | — |
| Gemma 4 E2B | DPO | 75% | 0.75 | QP1 | 22 | 3 | 75 | 75.0% | 88.0% | — |
| Gemma 4 E2B | DPO | 75% | 1 | QP1 | 28 | 4 | 68 | 68.0% | 87.5% | — |
| Gemma 4 E2B | DPO | 75% | 2 | QP1 | 29 | 6 | 65 | 65.0% | 82.9% | — |
| Gemma 4 E2B | DPO | 75% | 4 | QP1 | 29 | 5 | 66 | 66.0% | 85.3% | — |
| Gemma 4 E2B | DPO | 75% | 0.25 | QP4 | 33 | 31 | 36 | 36.0% | 51.6% | — |
| Gemma 4 E2B | DPO | 75% | 0.5 | QP4 | 26 | 14 | 60 | 60.0% | 65.0% | — |
| Gemma 4 E2B | DPO | 75% | 0.75 | QP4 | 22 | 2 | 76 | 76.0% | 91.7% | — |
| Gemma 4 E2B | DPO | 75% | 1 | QP4 | 24 | 12 | 64 | 64.0% | 66.7% | — |
| Gemma 4 E2B | DPO | 75% | 2 | QP4 | 26 | 9 | 65 | 65.0% | 74.3% | — |
| Gemma 4 E2B | DPO | 75% | 4 | QP4 | 29 | 13 | 58 | 58.0% | 69.0% | — |
| Gemma 4 E2B | DPO | 75% | 0.25 | QP7 | 38 | 39 | 23 | 23.0% | 49.4% | — |
| Gemma 4 E2B | DPO | 75% | 0.5 | QP7 | 27 | 19 | 54 | 54.0% | 58.7% | — |
| Gemma 4 E2B | DPO | 75% | 0.75 | QP7 | 21 | 8 | 71 | 71.0% | 72.4% | — |
| Gemma 4 E2B | DPO | 75% | 1 | QP7 | 28 | 17 | 55 | 55.0% | 62.2% | — |
| Gemma 4 E2B | DPO | 75% | 2 | QP7 | 25 | 23 | 52 | 52.0% | 52.1% | — |
| Gemma 4 E2B | DPO | 75% | 4 | QP7 | 29 | 18 | 53 | 53.0% | 61.7% | — |

## Gemma 4 E2B · DPO · train abstention 90%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 E2B | DPO | 90% | 0.25 | quant_m5 | 31 | 28 | 41 | 41.0% | 52.5% | -1.09 |
| Gemma 4 E2B | DPO | 90% | 0.5 | quant_m5 | 25 | 6 | 69 | 69.0% | 80.6% | -0.05 |
| Gemma 4 E2B | DPO | 90% | 0.75 | quant_m5 | 20 | 3 | 77 | 77.0% | 87.0% | 0.05 |
| Gemma 4 E2B | DPO | 90% | 1 | quant_m5 | 19 | 4 | 77 | 77.0% | 82.6% | -0.01 |
| Gemma 4 E2B | DPO | 90% | 2 | quant_m5 | 26 | 15 | 59 | 59.0% | 63.4% | -0.49 |
| Gemma 4 E2B | DPO | 90% | 4 | quant_m5 | 17 | 19 | 64 | 64.0% | 47.2% | -0.78 |
| Gemma 4 E2B | DPO | 90% | 0.25 | quant_m25 | 34 | 26 | 40 | 40.0% | 56.7% | -6.16 |
| Gemma 4 E2B | DPO | 90% | 0.5 | quant_m25 | 30 | 10 | 60 | 60.0% | 75.0% | -2.20 |
| Gemma 4 E2B | DPO | 90% | 0.75 | quant_m25 | 17 | 4 | 79 | 79.0% | 81.0% | -0.83 |
| Gemma 4 E2B | DPO | 90% | 1 | quant_m25 | 18 | 2 | 80 | 80.0% | 90.0% | -0.32 |
| Gemma 4 E2B | DPO | 90% | 2 | quant_m25 | 18 | 19 | 63 | 63.0% | 48.6% | -4.57 |
| Gemma 4 E2B | DPO | 90% | 4 | quant_m25 | 22 | 19 | 59 | 59.0% | 53.7% | -4.53 |
| Gemma 4 E2B | DPO | 90% | 0.25 | quant_m100 | 36 | 28 | 36 | 36.0% | 56.2% | -27.64 |
| Gemma 4 E2B | DPO | 90% | 0.5 | quant_m100 | 24 | 13 | 63 | 63.0% | 64.9% | -12.76 |
| Gemma 4 E2B | DPO | 90% | 0.75 | quant_m100 | 23 | 7 | 70 | 70.0% | 76.7% | -6.77 |
| Gemma 4 E2B | DPO | 90% | 1 | quant_m100 | 16 | 1 | 83 | 83.0% | 94.1% | -0.84 |
| Gemma 4 E2B | DPO | 90% | 2 | quant_m100 | 21 | 16 | 63 | 63.0% | 56.8% | -15.79 |
| Gemma 4 E2B | DPO | 90% | 4 | quant_m100 | 24 | 17 | 59 | 59.0% | 58.5% | -16.76 |
| Gemma 4 E2B | DPO | 90% | 0.25 | QP1 | 25 | 29 | 46 | 46.0% | 46.3% | — |
| Gemma 4 E2B | DPO | 90% | 0.5 | QP1 | 17 | 6 | 77 | 77.0% | 73.9% | — |
| Gemma 4 E2B | DPO | 90% | 0.75 | QP1 | 11 | 5 | 84 | 84.0% | 68.8% | — |
| Gemma 4 E2B | DPO | 90% | 1 | QP1 | 8 | 1 | 91 | 91.0% | 88.9% | — |
| Gemma 4 E2B | DPO | 90% | 2 | QP1 | 13 | 13 | 74 | 74.0% | 50.0% | — |
| Gemma 4 E2B | DPO | 90% | 4 | QP1 | 14 | 10 | 76 | 76.0% | 58.3% | — |
| Gemma 4 E2B | DPO | 90% | 0.25 | QP4 | 30 | 24 | 46 | 46.0% | 55.6% | — |
| Gemma 4 E2B | DPO | 90% | 0.5 | QP4 | 13 | 4 | 83 | 83.0% | 76.5% | — |
| Gemma 4 E2B | DPO | 90% | 0.75 | QP4 | 11 | 6 | 83 | 83.0% | 64.7% | — |
| Gemma 4 E2B | DPO | 90% | 1 | QP4 | 7 | 4 | 89 | 89.0% | 63.6% | — |
| Gemma 4 E2B | DPO | 90% | 2 | QP4 | 15 | 8 | 77 | 77.0% | 65.2% | — |
| Gemma 4 E2B | DPO | 90% | 4 | QP4 | 11 | 11 | 78 | 78.0% | 50.0% | — |
| Gemma 4 E2B | DPO | 90% | 0.25 | QP7 | 35 | 33 | 32 | 32.0% | 51.5% | — |
| Gemma 4 E2B | DPO | 90% | 0.5 | QP7 | 20 | 14 | 66 | 66.0% | 58.8% | — |
| Gemma 4 E2B | DPO | 90% | 0.75 | QP7 | 15 | 7 | 78 | 78.0% | 68.2% | — |
| Gemma 4 E2B | DPO | 90% | 1 | QP7 | 18 | 5 | 77 | 77.0% | 78.3% | — |
| Gemma 4 E2B | DPO | 90% | 2 | QP7 | 22 | 22 | 56 | 56.0% | 50.0% | — |
| Gemma 4 E2B | DPO | 90% | 4 | QP7 | 17 | 18 | 65 | 65.0% | 48.6% | — |

## Qwen3.5-9B · SFT-Box · train abstention 50%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-9B | SFT-Box | 50% | 0.25 | quant_m5 | 2 | 18 | 80 | 80.0% | 10.0% | -0.88 |
| Qwen3.5-9B | SFT-Box | 50% | 0.5 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 0.75 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 1 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 2 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 4 | quant_m5 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 0.25 | quant_m100 | 2 | 17 | 81 | 81.0% | 10.5% | -16.98 |
| Qwen3.5-9B | SFT-Box | 50% | 0.5 | quant_m100 | 0 | 1 | 99 | 99.0% | 0.0% | -1.00 |
| Qwen3.5-9B | SFT-Box | 50% | 0.75 | quant_m100 | 0 | 2 | 98 | 98.0% | 0.0% | -2.00 |
| Qwen3.5-9B | SFT-Box | 50% | 1 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 2 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 4 | quant_m100 | 0 | 0 | 100 | 100.0% | — | 0.00 |
| Qwen3.5-9B | SFT-Box | 50% | 0.25 | QP1 | 17 | 16 | 67 | 67.0% | 51.5% | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.5 | QP1 | 0 | 2 | 98 | 98.0% | 0.0% | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.75 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 1 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 2 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 4 | QP1 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.25 | QP4 | 16 | 11 | 73 | 73.0% | 59.3% | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.5 | QP4 | 0 | 5 | 95 | 95.0% | 0.0% | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.75 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 1 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 2 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 4 | QP4 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.25 | QP7 | 20 | 23 | 57 | 57.0% | 46.5% | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.5 | QP7 | 1 | 2 | 97 | 97.0% | 33.3% | — |
| Qwen3.5-9B | SFT-Box | 50% | 0.75 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 1 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 2 | QP7 | 0 | 0 | 100 | 100.0% | — | — |
| Qwen3.5-9B | SFT-Box | 50% | 4 | QP7 | 0 | 0 | 100 | 100.0% | — | — |

## Qwen3.5-9B · DPO · train abstention 50%

| Model | Training method | Train abst % | Epoch | Framing | Correct | Incorrect | Abstained | Abstention Rate | Selective Accuracy | Normalized Utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-9B | DPO | 50% | 0.25 | quant_m5 | 30 | 0 | 70 | 70.0% | 100.0% | 0.30 |
| Qwen3.5-9B | DPO | 50% | 0.5 | quant_m5 | 16 | 3 | 81 | 81.0% | 84.2% | 0.01 |
| Qwen3.5-9B | DPO | 50% | 0.75 | quant_m5 | 13 | 0 | 87 | 87.0% | 100.0% | 0.13 |
| Qwen3.5-9B | DPO | 50% | 1 | quant_m5 | 12 | 1 | 87 | 87.0% | 92.3% | 0.07 |
| Qwen3.5-9B | DPO | 50% | 0.25 | quant_m25 | 32 | 0 | 68 | 68.0% | 100.0% | 0.32 |
| Qwen3.5-9B | DPO | 50% | 0.5 | quant_m25 | 17 | 1 | 82 | 82.0% | 94.4% | -0.08 |
| Qwen3.5-9B | DPO | 50% | 0.75 | quant_m25 | 16 | 0 | 84 | 84.0% | 100.0% | 0.16 |
| Qwen3.5-9B | DPO | 50% | 1 | quant_m25 | 11 | 0 | 89 | 89.0% | 100.0% | 0.11 |
| Qwen3.5-9B | DPO | 50% | 0.25 | quant_m100 | 29 | 1 | 70 | 70.0% | 96.7% | -0.71 |
| Qwen3.5-9B | DPO | 50% | 0.5 | quant_m100 | 18 | 1 | 81 | 81.0% | 94.7% | -0.82 |
| Qwen3.5-9B | DPO | 50% | 0.75 | quant_m100 | 13 | 1 | 86 | 86.0% | 92.9% | -0.87 |
| Qwen3.5-9B | DPO | 50% | 1 | quant_m100 | 10 | 1 | 89 | 89.0% | 90.9% | -0.90 |
| Qwen3.5-9B | DPO | 50% | 0.25 | QP1 | 26 | 3 | 71 | 71.0% | 89.7% | — |
| Qwen3.5-9B | DPO | 50% | 0.5 | QP1 | 14 | 2 | 84 | 84.0% | 87.5% | — |
| Qwen3.5-9B | DPO | 50% | 0.75 | QP1 | 15 | 0 | 85 | 85.0% | 100.0% | — |
| Qwen3.5-9B | DPO | 50% | 1 | QP1 | 12 | 0 | 88 | 88.0% | 100.0% | — |
| Qwen3.5-9B | DPO | 50% | 0.25 | QP4 | 25 | 1 | 74 | 74.0% | 96.2% | — |
| Qwen3.5-9B | DPO | 50% | 0.5 | QP4 | 15 | 1 | 84 | 84.0% | 93.8% | — |
| Qwen3.5-9B | DPO | 50% | 0.75 | QP4 | 11 | 1 | 88 | 88.0% | 91.7% | — |
| Qwen3.5-9B | DPO | 50% | 1 | QP4 | 8 | 0 | 92 | 92.0% | 100.0% | — |
| Qwen3.5-9B | DPO | 50% | 0.25 | QP7 | 22 | 5 | 73 | 73.0% | 81.5% | — |
| Qwen3.5-9B | DPO | 50% | 0.5 | QP7 | 17 | 1 | 82 | 82.0% | 94.4% | — |
| Qwen3.5-9B | DPO | 50% | 0.75 | QP7 | 15 | 1 | 84 | 84.0% | 93.8% | — |
| Qwen3.5-9B | DPO | 50% | 1 | QP7 | 14 | 0 | 86 | 86.0% | 100.0% | — |
