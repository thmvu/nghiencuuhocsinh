# Configuration Lock A — RQ1 protocol v1

Date: 2026-09-23. Machine-readable authority: `configs/protocol_a.json`.
This document locks the development protocol before fitting; it does not declare Gate A passed, authorize TEST access, or report model results. No model has been trained by this step. Root integration must verify every Gate A condition.

Decisions use TRAIN support only: 168,431 interactions, 2,802 students, 105 skills, minimum skill support 3, median 630, and 22 skills below 100 interactions (820 interactions combined). The 492 train students with at most five interactions remain in training. Train support tables and `reports/eda_summary.md` are the evidence; validation/test outcome distributions were not used to select these choices.

| Item | Locked choice and reason |
|---|---|
| Dataset | Corrected collapsed schema; preserve original raw file. Raw SHA-256 `162ef8d2d28bcbfea6591a282994062bd8d5eaa00636544292a0d268dca6e5da`. Official distribution checksum remains unverified, as recorded by EDA. |
| Split | Reuse `data/processed/student_split.json`, SHA-256 `7b7a5e10f9c8b6dcd8ef4efa3965c3ef738ff32d23907e91e0f2050622afd27d`; seed 42, student-disjoint 70/15/15 with floor train/validation and remainder test. Never regenerate during modeling. |
| Cleaning | Drop missing skills and underscore-encoded multi-skill rows; retain single-skill rows, including repeated student/problem pairs. Reject duplicate student/order identities. Preserve source row identity and chronological student/order sorting. Do not filter sparse skills out of the target population. |
| Target | `correct`: first-attempt success without requested help; not mastery. |
| Warm-up | Five cleaned interactions per student, across skills. Predict and update during warm-up; score interaction six onward. Students of length <=5 have zero scored rows and are reported, but their training interactions remain. |
| Shared evaluation | All models use identical row identities, students and scoring masks. Reset state for each student. Predict before observing current label, then update only student state; fitted global parameters remain fixed. |
| Selection | Minimize interaction-weighted validation Brier; exact ties use the first declared candidate. Report ROC-AUC and log loss additionally; one-class AUC is undefined. Log-loss clipping epsilon is 1e-15. |
| History | Strictly prior interactions; success/failure counts start at zero, cold-start accuracy 0.5. No current hint, attempts or other response-derived features. |
| Problem difficulty | Five-fold GroupKFold by student without shuffle. TRAIN features use held-out-fold statistics; validation/test use full-TRAIN statistics. Alpha fixed at 10 for MVP. Both problem and global means come exclusively from the fit partition. Unseen problem falls back to that partition's global mean. |
| Baselines | Global train mean and smoothed train problem mean (alpha 10); unseen problem uses train global mean. Baseline fit itself needs no OOF; target-derived TRAIN features do. |
| PFA | Full skill-specific intercept/success/failure effects plus global intercept, L2 logistic regression. Sparse skills remain regularized rather than removed; unseen skill has zero skill blocks and uses learned global intercept. Four C candidates [0.01, 0.1, 1, 10], lbfgs, 2,000 iterations, tolerance 1e-6, seed 42; no search expansion. Nonconverged candidates invalid and logged. |
| BKT | No forgetting. Per-skill fit only at >=100 TRAIN interactions with both labels; otherwise use pooled parameters. Pooled likelihood keeps each student-skill sequence separate. Threshold is a stability choice justified by sparse TRAIN tail, not optimized against validation/test. Unseen skill starts independent state with pooled parameters. |
| BKT fitting | Bounded L-BFGS-B negative sequence log likelihood. L0 [0.001,0.999], T [0.001,0.5], G/S [0.001,0.3]. Three deterministic starts (L0,T,G,S): (0.2,0.1,0.2,0.1), (0.5,0.05,0.1,0.2), (0.8,0.2,0.25,0.05). Maxiter 500, maxfun 10,000, ftol 1e-9. Pick best converged TRAIN likelihood per fit group; maximum 106 groups/318 optimizer runs, one validation candidate. Failed skill fit uses pool; failed pool stops development. |
| XGBoost encoding | Train-only one-hot skill, unseen all zeros. Omit raw problem ID; never use any ID as numeric ordinal input. Include prior skill success/failure/accuracy, prior overall accuracy, history length, OOF problem difficulty, skill one-hot. |
| XGBoost search | Eight candidates in ordered Cartesian grid depth [2,4], learning rate [0.05,0.1], trees [100,300]. Binary logistic, hist, one CPU worker, seed 42; min child weight 5, row/column sampling 1, L2 1, L1/gamma 0. No early stopping or search extension. |
| Calibration | No fitted calibrator in MVP. Calibration curves assess probabilities only; they do not justify changing the pipeline after TEST access. |
| Final fitting | Keep train-fitted models; no train+validation refit. Validation selects declared candidates only. |

## Sequential evaluator contract

`src.evaluation.sequential.sequential_predict(df, model, warmup=5)` returns a DataFrame of **all** chronological rows with `user_id`, `order_id`, `problem_id`, `skill_id`, `source_row`, `correct`, `probability`, `history_length`, `is_scored`. Only rows with `is_scored=True` enter metrics. Original data is not mutated. Invalid identities, duplicate student/order or source rows, nonbinary labels and nonfinite/out-of-range probabilities fail explicitly.

The adapter supplies `reset(user_id)`, `predict(row) -> probability`, and `update(row)`. Predict receives a read-only mapping containing only identities, the explicit six allowed numeric features when available, and recomputed history length. Update receives that mapping plus `correct` after prediction. Arbitrary columns with a `prior_` prefix are not trusted. Feature values must come from the leakage-tested preprocessing pipeline; the whitelist cannot prove their provenance.

Adapters must keep global fitted parameters immutable. The optional `global_parameters_snapshot()` hook returns JSON-serializable parameters, checked before evaluation and after every reset/predict/update callback; mutation raises. Without that hook the immutability requirement remains an adapter contract, not an introspection guarantee. Future real model adapters need adapter-specific tests before use. Gate A uses synthetic stateful test adapters and does not fit real models.

## Remaining locks and gate evidence

Lock B must record selected C, fitted BKT checkpoint/parameters, selected XGBoost candidate, final artifact hashes, bootstrap iterations/seed/CI and pre-test checklist. Paired bootstrap must sample students, retaining their complete scored interaction clusters. Lock C remains separate for RQ2. TEST preprocessing, structural audits and causal per-student histories are allowed. Model scoring, tuning and test outcome inspection remain forbidden before Lock B and Gate B.

BKT will use a small custom bounded SciPy likelihood implementation instead of pyBKT. This keeps bounds, starts, sequence isolation and the fixed optimization budget explicit, but adds responsibility for validating likelihood, Bayesian update and numerical behavior against hand-derived sequences before fitting. Gate A does not require installing pyBKT and does not claim the future fitter is implemented.

The evaluator unit tests exercise pre-update predictions, student resets, warm-up/short students, deterministic sorting, unchanged inputs, forbidden-column filtering, probability/identity validation and global-parameter mutation detection. Root integration records the final complete suite and Gate A audit separately.
