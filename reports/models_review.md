# Independent review — baseline/PFA milestone

Reviewed against `NCKH_Knowledge_Tracing_AI_Agent_Plan_v3_Consolidated.md`, saved EDA, and `configs/protocol_a.json` on 2026-09-23. Scope: Global baseline, Problem baseline, skill-specific PFA, metrics, train/validation runner, and results notebook. This reviewer used synthetic data only; no research-data model fits or test metrics were performed.

## Independent checks

`tests/test_models_independent.py` challenges batch/sequential equivalence, current-target independence, rejection of explicitly held-out fit rows, hand-calculated smoothed baseline probabilities, unseen-skill zero-block behavior, actual fitted-weight mutation detection, checkpoint serialization, replacement of fitted problem tables, scored-row exclusion, undefined one-class AUC, and finite clipped log loss.

## Findings

1. **Checkpoint serialization blocker:** the initial Problem baseline stored a `MappingProxyType` table; independent `joblib.dump` raised `TypeError: cannot pickle 'mappingproxy' object`. This would stop checkpoint persistence after fitting. Sent to implementation owner with a reproducing regression test.
2. **Frozen-parameter guard gap:** replacing that table during `update` changed predictions without changing its cached snapshot digest. The independent adversarial adapter reproduced the missing exception. Sent to owner with a regression test.

Both findings are resolved. Explicit serialization saves a plain dictionary and restores an immutable table. The snapshot uses its cached digest only for the original immutable table object, and hashes current contents if the table has been replaced. Regression tests now pass.

## Final verification

Command: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.

Independent rerun against integrated source: **41 tests passed**, including **9 independent model/metric tests**, in 0.724 seconds of unittest execution; command exit code 0. No remaining blocking finding in this review scope. All model fits performed by these tests use small synthetic fixtures. The reviewer did not run the research-data experiment or access test outcomes.

## Protocol review

The runner explicitly opens train and validation partitions, validates their hashes and configuration hash against preprocessing evidence, and checks student disjointness and the warm-up mask. It evaluates all candidates on the same validation rows, selects minimum Brier with first-declared exact tie handling, and uses the four locked C values. The PFA design uses separate skill intercept, success, and failure blocks and a global intercept, with train-only vocabulary; unseen skills contribute zero skill blocks. Evaluation does not refit models. Candidate nonconvergence is handled with a dedicated exception and no additional candidate budget. The notebook reads saved results without triggering fitting. No path in the reviewed runner/notebook opens the test partition.

Limits: fit APIs accept data without a split column, so callers remain responsible for provenance in that case. The research runner supplies and verifies split-labelled artifacts. Batch scoring relies on the already checked shifted features; sequential equivalence is independently tested on synthetic trajectories and checked by the runner on a small validation sample. This review does not claim final RQ1 results or authorize Gate B.
