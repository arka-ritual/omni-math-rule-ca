# Omni-MATH-Rule main tables, updated with the $r_0$ baseline

Paper tables with a new leading **$r_0$** column in each quantitative block.
$r_0 := (s_c, s_a, s_i) = (+1, 0, 0)$ — abstention is offered, but a wrong
answer is free. It is the no-consequence *quantitative* anchor Reviewers 27Kr
and LswH asked for; previously only QP1 played that role, and only on the
qualitative side.

All $r_0$ cells: $n{=}100$, seed 100, $T{=}1.0$, `max_tokens` 64000, graded with
`evaluation/math_eval_cautious.py`. Source data:
[`summary.md`](summary.md) (per-cell) and
[`summary.csv`](summary.csv). Everything outside the $r_0$ column is unchanged
from the paper.

## Abstention rate (%)

```latex
% --- Math: abstention rate -------------------------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{4pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{Omni-MATH-Rule abstention rate (\%)} per (model, framing) cell across the full sweep of quantitative rubrics and qualitative prompts. $r_0$ is the no-consequence rubric $(+1,0,0)$: abstention is available but an incorrect answer costs nothing.}
  \label{tab:main-math-abst}
  \begin{tabular}{l|cccccc|ccccccc}
    \toprule
    \multirow{2}{*}{\textbf{Model}}
      & \multicolumn{6}{c|}{\textbf{Quantitative}}
      & \multicolumn{7}{c}{\textbf{Qualitative}} \\
    \cmidrule(lr){2-7}\cmidrule(lr){8-14}
      & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$ & $r_{25}$ & $r_{100}$
      & QP1 & QP2 & QP3 & QP4 & QP5 & QP6 & QP7 \\
    \midrule
    Claude 4.5 Haiku       & 1 & 1 & 1 & 1 & 2 & 0 & 1 & 3 & 3 & 1 & 1 & 1 & 7 \\
    GPT-5.4 Nano           & 2 & 3 & 4 & 4 & 3 & 4 & 9 & 14 & 7 & 9 & 13 & 8 & 13 \\
    Gemini-3.1 Flash-Lite  & 0 & 8 & 8 & 6 & 9 & 6 & 6 & 7 & 6 & 8 & 7 & 12 & 7 \\
    DeepSeek V4 Pro        & 1 & 7 & 7 & 4 & 5 & 8 & 7 & 9 & 8 & 7 & 7 & 7 & 8 \\
    Qwen3.5 397B           & 1 & 3 & 3 & 5 & 1 & 2 & 1 & 4 & 2 & 2 & 3 & 3 & 6 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | r_25 | r_100 | QP1 | QP2 | QP3 | QP4 | QP5 | QP6 | QP7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | 1 | 1 | 1 | 1 | 2 | 0 | 1 | 3 | 3 | 1 | 1 | 1 | 7 |
| GPT-5.4 Nano | 2 | 3 | 4 | 4 | 3 | 4 | 9 | 14 | 7 | 9 | 13 | 8 | 13 |
| Gemini-3.1 Flash-Lite | 0 | 8 | 8 | 6 | 9 | 6 | 6 | 7 | 6 | 8 | 7 | 12 | 7 |
| DeepSeek V4 Pro | 1 | 7 | 7 | 4 | 5 | 8 | 7 | 9 | 8 | 7 | 7 | 7 | 8 |
| Qwen3.5 397B | 1 | 3 | 3 | 5 | 1 | 2 | 1 | 4 | 2 | 2 | 3 | 3 | 6 |

Columns 1–6 are the quantitative rubrics; the remainder are the qualitative prompts.


## Selective accuracy (%)

```latex
% --- Math: selective accuracy ----------------------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{4pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{Omni-MATH-Rule selective accuracy (\%)} per (model, framing) cell. Selective accuracy is correct $/ (\text{correct} + \text{incorrect})$, i.e.\ accuracy on items the model chose to attempt.}
  \label{tab:main-math-selacc}
  \begin{tabular}{l|cccccc|ccccccc}
    \toprule
    \multirow{2}{*}{\textbf{Model}}
      & \multicolumn{6}{c|}{\textbf{Quantitative}}
      & \multicolumn{7}{c}{\textbf{Qualitative}} \\
    \cmidrule(lr){2-7}\cmidrule(lr){8-14}
      & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$ & $r_{25}$ & $r_{100}$
      & QP1 & QP2 & QP3 & QP4 & QP5 & QP6 & QP7 \\
    \midrule
    Claude 4.5 Haiku       & 58.6 & 68.7 & 72.7 & 65.7 & 70.4 & 67.0  & 70.7 & 67.0 & 68.0 & 73.7 & 71.7 & 70.7 & 77.4 \\
    GPT-5.4 Nano           & 51.0 & 42.3 & 44.8 & 45.8 & 51.5 & 49.0  & 51.9 & 39.8 & 56.8 & 46.8 & 47.3 & 54.5 & 51.5 \\
    Gemini-3.1 Flash-Lite  & 55.0 & 85.9 & 82.6 & 84.0 & 83.5 & 83.0  & 79.8 & 87.0 & 79.8 & 84.8 & 80.6 & 87.5 & 82.8 \\
    DeepSeek V4 Pro        & 87.0 & 98.1 & 98.2 & 94.4 & 98.1 & 96.7  & 95.3 & 93.8 & 93.2 & 100.0 & 96.3 & 94.9 & 96.5 \\
    Qwen3.5 397B           & 84.2 & 89.7 & 86.6 & 90.5 & 89.7 & 86.5  & 91.0 & 94.1 & 87.8 & 82.5 & 88.5 & 88.2 & 91.3 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | r_25 | r_100 | QP1 | QP2 | QP3 | QP4 | QP5 | QP6 | QP7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | 58.6 | 68.7 | 72.7 | 65.7 | 70.4 | 67.0 | 70.7 | 67.0 | 68.0 | 73.7 | 71.7 | 70.7 | 77.4 |
| GPT-5.4 Nano | 51.0 | 42.3 | 44.8 | 45.8 | 51.5 | 49.0 | 51.9 | 39.8 | 56.8 | 46.8 | 47.3 | 54.5 | 51.5 |
| Gemini-3.1 Flash-Lite | 55.0 | 85.9 | 82.6 | 84.0 | 83.5 | 83.0 | 79.8 | 87.0 | 79.8 | 84.8 | 80.6 | 87.5 | 82.8 |
| DeepSeek V4 Pro | 87.0 | 98.1 | 98.2 | 94.4 | 98.1 | 96.7 | 95.3 | 93.8 | 93.2 | 100.0 | 96.3 | 94.9 | 96.5 |
| Qwen3.5 397B | 84.2 | 89.7 | 86.6 | 90.5 | 89.7 | 86.5 | 91.0 | 94.1 | 87.8 | 82.5 | 88.5 | 88.2 | 91.3 |

Columns 1–6 are the quantitative rubrics; the remainder are the qualitative prompts.


## Selective-accuracy delta vs. no-consequence baseline (pp)

```latex
% --- Math: conditional-accuracy delta vs no-consequence baseline -----------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{4pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{Omni-MATH-Rule selective-accuracy delta vs.\ no-consequence baseline (pp).} Each cell is the selective accuracy of \cref{tab:main-math-selacc} minus the per-model anchor in \cref{tab:base-no-conseq}.}
  \label{tab:main-math-delta}
  \begin{tabular}{l|cccccc|ccccccc}
    \toprule
    \multirow{2}{*}{\textbf{Model}}
      & \multicolumn{6}{c|}{\textbf{Quantitative}}
      & \multicolumn{7}{c}{\textbf{Qualitative}} \\
    \cmidrule(lr){2-7}\cmidrule(lr){8-14}
      & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$ & $r_{25}$ & $r_{100}$
      & QP1 & QP2 & QP3 & QP4 & QP5 & QP6 & QP7 \\
    \midrule
    Claude 4.5 Haiku       & -7.4 & +2.7  & +6.7  & -0.3 & +4.4  & +1.0  & +4.7 & +1.0 & +2.0 & +7.7 & +5.7 & +4.7 & +11.4 \\
    GPT-5.4 Nano           & +9.0 & +0.3  & +2.8  & +3.8 & +9.5  & +7.0  & +9.9 & -2.2 & +14.8 & +4.8 & +5.3 & +12.5 & +9.5 \\
    Gemini-3.1 Flash-Lite  & -5.0 & +25.9 & +22.6 & +24.0 & +23.5 & +23.0 & +19.8 & +27.0 & +19.8 & +24.8 & +20.6 & +27.5 & +22.8 \\
    DeepSeek V4 Pro        & -3.6 & +7.5  & +7.6  & +3.8 & +7.5  & +6.1  & +4.7 & +3.2 & +2.6 & +9.4 & +5.7 & +4.3 & +5.9 \\
    Qwen3.5 397B           & -5.8 & -0.3  & -3.4  & +0.5 & -0.3  & -3.5  & +1.0 & +4.1 & -2.2 & -7.5 & -1.5 & -1.8 & +1.3 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | r_25 | r_100 | QP1 | QP2 | QP3 | QP4 | QP5 | QP6 | QP7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | -7.4 | +2.7 | +6.7 | -0.3 | +4.4 | +1.0 | +4.7 | +1.0 | +2.0 | +7.7 | +5.7 | +4.7 | +11.4 |
| GPT-5.4 Nano | +9.0 | +0.3 | +2.8 | +3.8 | +9.5 | +7.0 | +9.9 | -2.2 | +14.8 | +4.8 | +5.3 | +12.5 | +9.5 |
| Gemini-3.1 Flash-Lite | -5.0 | +25.9 | +22.6 | +24.0 | +23.5 | +23.0 | +19.8 | +27.0 | +19.8 | +24.8 | +20.6 | +27.5 | +22.8 |
| DeepSeek V4 Pro | -3.6 | +7.5 | +7.6 | +3.8 | +7.5 | +6.1 | +4.7 | +3.2 | +2.6 | +9.4 | +5.7 | +4.3 | +5.9 |
| Qwen3.5 397B | -5.8 | -0.3 | -3.4 | +0.5 | -0.3 | -3.5 | +1.0 | +4.1 | -2.2 | -7.5 | -1.5 | -1.8 | +1.3 |

Columns 1–6 are the quantitative rubrics; the remainder are the qualitative prompts.


## Final score

```latex
% --- Math: score -----------------------------------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{6pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{Omni-MATH-Rule final score} (cumulative reward over $n{=}100$ instances) per (model, rubric) cell. Final score is only defined for the quantitative rubrics, where each cell can be obtained directly from the abstention rate and selective accuracy of \cref{tab:main-math-abst,tab:main-math-selacc} together with the per-rubric reward triple. The achievable range for $r_X$ is $[-100X, +100]$; for $r_0$ it is $[0, 100]$, since neither an incorrect answer nor an abstention carries a reward.}
  \label{tab:main-math-score}
  \begin{tabular}{l|rrrrrr}
    \toprule
    \textbf{Model} & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$ & $r_{25}$ & $r_{100}$ \\
    \midrule
    Claude 4.5 Haiku       &  58  &  37  &  -63  &  -274  &  -656  & -3{,}233 \\
    GPT-5.4 Nano           &  50  & -14  & -222  &  -476  & -1{,}126 & -4{,}849 \\
    Gemini-3.1 Flash-Lite  &  55  &  66  &   -4  &   -71  &  -299  & -1{,}520 \\
    DeepSeek V4 Pro        &  86  &  89  &   83  &    37  &    47  &   -215 \\
    Qwen3.5 397B           &  83  &  77  &   19  &    -4  &  -166  & -1{,}238 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | r_25 | r_100 |
|---|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | 58 | 37 | -63 | -274 | -656 | -3,233 |
| GPT-5.4 Nano | 50 | -14 | -222 | -476 | -1,126 | -4,849 |
| Gemini-3.1 Flash-Lite | 55 | 66 | -4 | -71 | -299 | -1,520 |
| DeepSeek V4 Pro | 86 | 89 | 83 | 37 | 47 | -215 |
| Qwen3.5 397B | 83 | 77 | 19 | -4 | -166 | -1,238 |


---

Note that $r_0$ is also the only rubric in the table where every model scores
positively, simply because nothing is deducted. It is a ceiling reference, not
evidence of good behaviour: the same policy that scores 58–86 here scores
−1,238 to −4,849 at $r_{100}$, and the abstention rate barely moves between
the two.
