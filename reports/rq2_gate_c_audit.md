# RQ2 Gate C / Configuration Lock C — independent pre-TEST audit draft

Status: **not ready to declare Gate C passed**. This is a validation-only audit of the plan (§§24–35), current development configs, rubric draft, and aggregate artifacts. No RQ2 TEST data or outputs were opened. The research team must settle the items below and record a dated, machine-readable Lock C before any TEST scenario is generated or evaluated.

## Evidence available now

- Fifty fixed-seed VALIDATION scenarios represent 50 distinct students, one BKT prefix snapshot each. The TRAIN-fitted BKT checkpoint supplies latent mastery estimates; this is not observed knowledge.
- The graph covers 20 TRAIN-selected skills and five edges, all labeled `prototype_assumption`. The TRAIN candidate pool uses minimum support five, and each validation scenario has eight candidates across eight distinct skills. Candidate difficulty is a TRAIN success-rate proxy.
- `gemma3:1b` with Ollama was feasible locally. In one development pass, 49/50 responses met the schema, 48/50 selected a listed candidate, and two failed. B+ and Agent agreed once. These figures are **development diagnostics**, not final comparative evidence or learning-gain estimates.
- The rubric is a draft. There are currently no recorded independent rater scores or confirmed raters.

## Decisions and evidence required for Lock C

| Item | Required frozen record before TEST |
|---|---|
| State and graph | BKT checkpoint digest; post-response prefix update semantics; graph file digest, 20 skill IDs, five edge assumptions, and provenance. Either obtain curriculum review/source support or keep the explicit prototype limitation in every claim. Do not silently present assumed edges as validated prerequisites. |
| Candidate generator and B+ | Source-code/config hashes; TRAIN-only pool definition and minimum support five; eight-candidate selection and deterministic tie-break; input equality check for state, graph, and candidate list. Record candidate diversity criteria independently of the final metric. |
| Scenario protocol | TEST student pool distinct from TRAIN and VALIDATION; one snapshot per student; eligibility, cutoff sampling, seed, number of TEST scenarios, and shortage rule chosen *before* inspecting TEST. Record exactly which data fields can be read to construct states. No future response labels may affect a snapshot/candidate set. |
| Agent runtime | Exact Ollama and model versions/digest/quantization, local-only endpoint, temperature, context size, explicit seed policy, prompt and schema bytes/hashes, timeout, no-repair or fixed repair rule, and maximum attempts. Save environment/hardware metadata and the source commit. |
| Repeats and failures | Number of runs per scenario, execution order, timeout/error handling, invalid JSON/out-of-set counting, and aggregation. Retain all attempted calls in the denominator; do not discard failed runs. If no repair is used, first-pass and final validity are identical by definition. |
| Outcomes | Name one primary **operational** endpoint if no rater panel is available, then freeze all secondary metrics and uncertainty method. Valid-candidate rate, schema-valid rate, timeout/error rate and latency describe Agent reliability; B+ validity is guaranteed by policy, so a direct validity contrast does not establish recommendation quality. Agreement with B+ is descriptive only. |
| Human rubric | If two raters can be recruited, freeze the blind, paired sampling of 20–30 TEST scenarios, the three selection-only 0–2 criteria, rater instructions, tie/disagreement handling, and inter-rater agreement statistic. Do not add Agent rationale to a B+ comparison unless both systems supply comparable rationales; score Agent rationale separately. If raters are unavailable, explicitly drop pedagogical-quality superiority claims and report only operational behavior. |
| Reproducibility/privacy | Pin hashes of Lock B, TRAIN/VALIDATION input, BKT checkpoint, graph, candidate pool, prompt/schema and RQ2 code. Keep student IDs, scenario-level selections, raw responses and per-run logs in ignored local paths. Publish only aggregate metrics and non-identifying graph assumptions. |

## Recommended repeated-run analysis

Predeclare, for example, 50 TEST scenarios from 50 distinct TEST students × three Agent runs. Report the denominator as **50 students/scenarios and 150 attempted runs**, never 150 independent observations. For schema validity, candidate validity and failures, show run-level counts/rates plus each scenario's three-run proportion, then summarize across students. For selection consistency, count the fraction of scenarios where all three selections are the same valid candidate; treat invalid/error outcomes as a separate category and also report consistency conditional on all runs valid. For latency, report median and tail (for example p95) across attempted calls and show cold-start handling. If confidence intervals or B+ comparisons are added, resample students/scenarios as paired clusters and keep the three runs together; never bootstrap individual runs as independent data.

## Scientific interpretation limits

Unreviewed prerequisite edges are permitted by the plan as labeled prototype assumptions, but they limit claims about real curriculum structure. The low Agent–B+ agreement on VALIDATION does not rank either policy. Without an independent blind quality assessment or observed learning outcome, the study can establish feasibility, protocol adherence, validity, consistency and latency, but **cannot conclude that Agent recommendations are pedagogically better or improve learning**. Even with rubric scores, the evidence concerns judged recommendation quality under this prototype graph, not causal learning gains.

Gate C should be marked passed only after validation development is closed, every row above is frozen in Lock C, the pre-TEST checklist and integrated tests pass, and a separate reviewer verifies no RQ2 TEST access occurred during development. The current draft does not authorize opening TEST.
