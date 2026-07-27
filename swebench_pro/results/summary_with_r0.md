# SWE-Bench Pro main tables, updated with the $r_0$ baseline

Paper tables with a new leading **$r_0$** column in each quantitative block.
$r_0 := (s_c, s_a, s_i) = (+1, 0, 0)$ — the `exit_abstain` tool is available and
described in the system prompt, but submitting a wrong patch costs nothing.

All $r_0$ cells: intervention 5 (vanilla submit flow + consequence framing +
`exit_abstain`), seed 100, reasoning effort medium, run on Modal and graded with
the official `scaleapi/SWE-bench_Pro-os` evaluator. Source data:
[`summary.md`](summary.md) and [`summary.csv`](summary.csv). Everything outside
the $r_0$ column is unchanged from the paper.
---

## Abstention rate (%)

```latex
% --- SWE: abstention rate --------------------------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{4pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{SWE-Bench Pro abstention rate (\%)} per (model, framing) cell. $r_0$ is the no-consequence rubric $(+1,0,0)$: the \texttt{exit\_abstain} tool is available but an incorrect submission costs nothing.}
  \label{tab:main-swe-abst}
  \begin{tabular}{l|cccc|ccccccc}
    \toprule
    \multirow{2}{*}{\textbf{Model}}
      & \multicolumn{4}{c|}{\textbf{Quantitative}}
      & \multicolumn{7}{c}{\textbf{Qualitative}} \\
    \cmidrule(lr){2-5}\cmidrule(lr){6-12}
      & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$
      & QP1 & QP2 & QP3 & QP4 & QP5 & QP6 & QP7 \\
    \midrule
    Claude 4.5 Haiku       & 0 & 0  & 0  & 0  & 0  & 2  & 0 & 0 & 2 & 0 & 0 \\
    GPT-5.4 Nano           & 0 & 0  & 0  & 0  & 0  & 0  & 0 & 0 & 0 & 0 & 0 \\
    Gemini-3.1 Flash-Lite  & 0 & 4  & 2  & 3  & 15 & 10 & 5 & 4 & 7 & 3 & 6 \\
    DeepSeek V4 Pro        & 0 & 2  & 1  & 3  & 4  & 22 & 2 & 2 & 3 & 6 & 0 \\
    Qwen3.5 397B           & 0 & 0  & 0  & 1  & 0  & 0  & 0 & 0 & 0 & 0 & 0 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | QP1 | QP2 | QP3 | QP4 | QP5 | QP6 | QP7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 0 | 0 |
| GPT-5.4 Nano | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gemini-3.1 Flash-Lite | 0 | 4 | 2 | 3 | 15 | 10 | 5 | 4 | 7 | 3 | 6 |
| DeepSeek V4 Pro | 0 | 2 | 1 | 3 | 4 | 22 | 2 | 2 | 3 | 6 | 0 |
| Qwen3.5 397B | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Columns 1–4 are the quantitative rubrics; the remainder are the qualitative prompts.


## Selective accuracy (%)

```latex
% --- SWE: selective accuracy -----------------------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{4pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{SWE-Bench Pro selective accuracy (\%)} per (model, framing) cell.}
  \label{tab:main-swe-selacc}
  \begin{tabular}{l|cccc|ccccccc}
    \toprule
    \multirow{2}{*}{\textbf{Model}}
      & \multicolumn{4}{c|}{\textbf{Quantitative}}
      & \multicolumn{7}{c}{\textbf{Qualitative}} \\
    \cmidrule(lr){2-5}\cmidrule(lr){6-12}
      & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$
      & QP1 & QP2 & QP3 & QP4 & QP5 & QP6 & QP7 \\
    \midrule
    Claude 4.5 Haiku       & 31.8 & 18.6 & 22.9 & 26.5 & 26.8 & 22.6 & 22.3 & 24.0 & 27.0 & 25.0 & 21.0 \\
    GPT-5.4 Nano           & 37.2 & 28.0 & 27.0 & 36.0 & 28.0 & 26.0 & 29.0 & 32.0 & 28.0 & 26.0 & 35.0 \\
    Gemini-3.1 Flash-Lite  &  7.5 &  5.3 & 14.5 & 13.9 & 20.9 & 13.5 & 12.9 & 15.0 & 11.0 & 20.0 & 13.0 \\
    DeepSeek V4 Pro        & 37.5 & 50.0 & 28.0 & 26.0 & 32.0 & 22.0 & 36.0 & 46.0 & 45.0 & 45.0 & 40.0 \\
    Qwen3.5 397B           & 37.3 & 35.7 & 40.0 & 36.7 & 21.0 & 32.0 & 33.7 & 35.0 & 45.0 & 41.0 & 35.0 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | QP1 | QP2 | QP3 | QP4 | QP5 | QP6 | QP7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | 31.8 | 18.6 | 22.9 | 26.5 | 26.8 | 22.6 | 22.3 | 24.0 | 27.0 | 25.0 | 21.0 |
| GPT-5.4 Nano | 37.2 | 28.0 | 27.0 | 36.0 | 28.0 | 26.0 | 29.0 | 32.0 | 28.0 | 26.0 | 35.0 |
| Gemini-3.1 Flash-Lite | 7.5 | 5.3 | 14.5 | 13.9 | 20.9 | 13.5 | 12.9 | 15.0 | 11.0 | 20.0 | 13.0 |
| DeepSeek V4 Pro | 37.5 | 50.0 | 28.0 | 26.0 | 32.0 | 22.0 | 36.0 | 46.0 | 45.0 | 45.0 | 40.0 |
| Qwen3.5 397B | 37.3 | 35.7 | 40.0 | 36.7 | 21.0 | 32.0 | 33.7 | 35.0 | 45.0 | 41.0 | 35.0 |

Columns 1–4 are the quantitative rubrics; the remainder are the qualitative prompts.


## Selective-accuracy delta vs. no-consequence baseline (pp)

```latex
% --- SWE: delta vs no-consequence baseline ---------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{4pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{SWE-Bench Pro selective-accuracy delta vs.\ no-consequence baseline (pp).} Each cell is the selective accuracy of \cref{tab:main-swe-selacc} minus the per-model anchor in \cref{tab:base-no-conseq}.}
  \label{tab:main-swe-delta}
  \begin{tabular}{l|cccc|ccccccc}
    \toprule
    \multirow{2}{*}{\textbf{Model}}
      & \multicolumn{4}{c|}{\textbf{Quantitative}}
      & \multicolumn{7}{c}{\textbf{Qualitative}} \\
    \cmidrule(lr){2-5}\cmidrule(lr){6-12}
      & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$
      & QP1 & QP2 & QP3 & QP4 & QP5 & QP6 & QP7 \\
    \midrule
    Claude 4.5 Haiku       & -3.2  & -16.4 & -12.1 & -8.5  & -8.2  & -12.4 & -12.7 & -11.0 & -8.0  & -10.0 & -14.0 \\
    GPT-5.4 Nano           & +2.2  & -7.0  & -8.0  & +1.0  & -7.0  & -9.0  & -6.0  & -3.0  & -7.0  & -9.0  & 0.0 \\
    Gemini-3.1 Flash-Lite  & -11.5 & -13.7 & -4.5  & -5.1  & +1.9  & -5.5  & -6.1  & -4.0  & -8.0  & +1.0  & -6.0 \\
    DeepSeek V4 Pro        & -3.5  & +9.0  & -13.0 & -15.0 & -9.0  & -19.0 & -5.0  & +5.0  & +4.0  & +4.0  & -1.0 \\
    Qwen3.5 397B           & +7.3  & +5.7  & +10.0 & +6.7  & -9.0  & +2.0  & +3.7  & +5.0  & +15.0 & +11.0 & +5.0 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 | QP1 | QP2 | QP3 | QP4 | QP5 | QP6 | QP7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Claude 4.5 Haiku | -3.2 | -16.4 | -12.1 | -8.5 | -8.2 | -12.4 | -12.7 | -11.0 | -8.0 | -10.0 | -14.0 |
| GPT-5.4 Nano | +2.2 | -7.0 | -8.0 | +1.0 | -7.0 | -9.0 | -6.0 | -3.0 | -7.0 | -9.0 | 0.0 |
| Gemini-3.1 Flash-Lite | -11.5 | -13.7 | -4.5 | -5.1 | +1.9 | -5.5 | -6.1 | -4.0 | -8.0 | +1.0 | -6.0 |
| DeepSeek V4 Pro | -3.5 | +9.0 | -13.0 | -15.0 | -9.0 | -19.0 | -5.0 | +5.0 | +4.0 | +4.0 | -1.0 |
| Qwen3.5 397B | +7.3 | +5.7 | +10.0 | +6.7 | -9.0 | +2.0 | +3.7 | +5.0 | +15.0 | +11.0 | +5.0 |

Columns 1–4 are the quantitative rubrics; the remainder are the qualitative prompts.


## Final score

```latex
% --- SWE: score ------------------------------------------------------------
\begin{table}[h]
  \centering
  \footnotesize
  \setlength{\tabcolsep}{8pt}
  \renewcommand{\arraystretch}{1.05}
  \caption{\textbf{SWE-Bench Pro final score} (cumulative reward over $n{=}100$ instances) per (model, rubric) cell. The achievable range for $r_X$ is $[-100X, +100]$; for $r_0$ it is $[0, 100]$, since neither an incorrect submission nor an abstention carries a reward.}
  \label{tab:main-swe-score}
  \begin{tabular}{l|rrrr}
    \toprule
    \textbf{Model} & $r_{0}$ & $r_{1}$ & $r_{5}$ & $r_{10}$ \\
    \midrule
    Claude 4.5 Haiku       &  31.8 &  -62.8  & -362.6 & -708.5 \\
    GPT-5.4 Nano           &  37.2 &  -44.0  & -338.0 & -604.0 \\
    Gemini-3.1 Flash-Lite  &   7.5 &  -85.8  & -404.7 & -821.7 \\
    DeepSeek V4 Pro        &  37.5 &    0.0  & -328.7 & -692.6 \\
    Qwen3.5 397B           &  37.3 &  -28.6  & -260.0 & -590.3 \\
    \bottomrule
  \end{tabular}
\end{table}
```

**Markdown:**

| Model | **r_0** | r_1 | r_5 | r_10 |
|---|---:|---:|---:|---:|
| Claude 4.5 Haiku | 31.8 | -62.8 | -362.6 | -708.5 |
| GPT-5.4 Nano | 37.2 | -44.0 | -338.0 | -604.0 |
| Gemini-3.1 Flash-Lite | 7.5 | -85.8 | -404.7 | -821.7 |
| DeepSeek V4 Pro | 37.5 | 0.0 | -328.7 | -692.6 |
| Qwen3.5 397B | 37.3 | -28.6 | -260.0 | -590.3 |


---

## What the $r_0$ column shows

Every model abstains on **zero of ~100 instances** at $r_0$, and abstention
stays at 0–4% all the way out to $r_{10}$. On the agentic task the models never
reach for the abstain channel whether or not a wrong submission is penalised —
a cleaner version of the same result the math table shows, because here there is
no formatting confound: abstention is a tool call, not a string the grader has
to recognise.

Selective accuracy at $r_0$ is *higher* than at $r_1$ for three of five models
(Claude 31.8 vs 18.6, GPT-Nano 37.2 vs 28.0, Qwen 37.3 vs 35.7), i.e. removing
the penalty did not make them sloppier. Gemini is the outlier at 7.5%; its
patches applied cleanly and its test suites ran, so this reads as capability on
this benchmark rather than a format artifact.
