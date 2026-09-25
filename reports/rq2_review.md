# RQ2 independent review — validation development

Scope: code and TRAIN/VALIDATION development only. No RQ2 TEST scenarios, labels, or Agent test outputs were inspected. This is an independent implementation review, not a final RQ2 result.

## Protocol checks

- BKT state is an estimated latent mastery snapshot from a single validation student's prefix. Fitted parameters remain unchanged; later responses do not affect a chosen snapshot. Independent regression covers this.
- Scenario sampling fixes a seed, selects distinct validation students, and records the cutoff. The serialized scenarios contain student identifiers, so artifacts must remain outside Git.
- The prototype graph has 20 TRAIN-selected skills and five explicitly marked assumption edges on the current TRAIN parquet. The edges need curriculum review; they are not empirically established prerequisites.
- The TRAIN candidate pool has 6,904 entries at the default minimum support of one; the configured minimum support of five retains 5,328. Problem IDs are unique on current TRAIN data. Candidate difficulty is the TRAIN success rate, a proxy rather than intrinsic item difficulty.
- B+ returns a copy of a chosen candidate and leaves the shared input list unchanged. Both systems must receive the same graph, state, and generated candidate list in the eventual harness.

## Findings and fixes requested

1. **Fixed during review:** skill IDs `1` and `'1'` previously collapsed to the same string key in a BKT state snapshot. The state builder now rejects ambiguous IDs; the independent regression passes.
2. **Fixed during review:** graph and candidate-pool builders accepted frames explicitly marked `split='validation'`. This could put validation outcomes into metadata used during scenario construction. They now reject non-TRAIN rows whenever a split column exists; the independent regression passes.

3. **Fixed during review:** the Agent validation runner initially accepted any stored B+ problem in the candidate list, even when deterministic B+ would choose a different one. It now recomputes B+ from the exact shared state, graph, and candidates before calling the Agent. Five independent adversarial tests pass after these fixes.

The tests additionally verify that future validation outcomes cannot change an already sampled scenario and that B+ leaves the shared candidate list intact.

## Hardware preflight

Initial read-only check found no `ollama` executable on PATH. System RAM is approximately 15.3 GiB on an ASUS TUF Gaming A15. The prior hardware report records an NVIDIA RTX 3050 Laptop GPU; WMI did not expose reliable VRAM. A subsequent local Ollama setup and five-scenario synthetic pilot were completed by the implementation team: `gemma3:1b` returned 5/5 schema-valid and 5/5 candidate-valid responses. This is a feasibility check, not an RQ2 outcome.

## Validation Agent run review

The one-pass local Agent artifact records 50 validation scenarios from 50 distinct students, 49 schema-valid outputs, 48 candidate-valid outputs, and one agreement with B+. The two failures are one schema validation error and one otherwise schema-valid selection outside the candidate set. The summary explicitly says `rq2_validation_development_not_final_test` and `test_opened=false`. It includes only aggregate counts and latency; the per-scenario records and student IDs are in `data/processed/rq2_validation_scenarios/`, which `git check-ignore` confirms is excluded from Git.

The result is exploratory validation development. Agreement with B+ is a descriptive disagreement metric, not evidence that either choice improves learning. The summary now reports schema-valid rate 0.98, candidate-valid rate 0.96, error rate 0.04 and zero timeouts, each over 50 scenarios. The current output contains no human rationale rubric. Before Lock C, record any prompt changes made in response to the two failures.

## Remaining before Gate C

Finish validation analysis, lock model/prompt/schema/timeout/retry/rubric/candidate/B+ protocol, then prepare the separate TEST scenarios. Do not count repeated Agent runs as independent students.
