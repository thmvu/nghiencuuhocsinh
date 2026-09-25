# Independent review — BKT and XGBoost

Scope: locked RQ1 development models, train/validation runner, and independent synthetic regression tests. References: consolidated v3 plan and `configs/protocol_a.json`. Review date: 2026-09-25. This reviewer did not fit research-data models, access test outcomes, or authorize final testing.

## Adversarial checks

`tests/test_rq1_models_independent.py` checks hand-derived BKT prediction, Bayes posterior and learning transition; separate skill/student state; current/future target mutation invariance; sequence boundaries in pooled likelihood; unseen-skill fallback; heldout fit rejection; actual parameter mutation detection; and checkpoint/batch alignment. A separate 4,160-observation likelihood check compares the BKT objective with a 70-digit Decimal reference across long, alternating success/failure runs. XGBoost checks the exact six numeric feature columns plus train-only skill one-hot blocks, zero blocks for unseen skills, rejection of heldout fit rows, excluded current targets and IDs, sequential/batch agreement, and full adapter serialization.

## Source review

The runners open only train and validation partitions, check input and configuration hashes against preprocessing evidence, and reject student overlap. BKT evaluation uses the shared sequential evaluator over all interactions, with an explicit common-mask check. The XGBoost adapter uses the locked six numeric features in the declared order, adds a train-derived skill one-hot block, and sets the locked objective, tree method, single-thread setting, seed, and fixed tree parameters. Its runner checks the declared grid order and eight-fit maximum, evaluates candidates on the same validation rows, and selects minimum Brier; exact ties preserve the first declared candidate. Model checkpoints are read back and their predictions compared. No reviewed runner path opens the test partition.

## Verification

`./.venv/Scripts/python.exe -m unittest tests.test_rq1_models_independent -v`: 13 passed. `./.venv/Scripts/python.exe -m unittest discover -s tests -v`: 65 passed. These are synthetic checks only; no research-data model was fitted or scored in this review. No blocking finding in the reviewed scope.
