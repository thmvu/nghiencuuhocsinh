# RQ2 development design (validation only)

RQ2 compares a deterministic policy (B+) with a local LLM policy under identical inputs: one BKT latent-mastery snapshot, the same prerequisite graph, and the same candidate problems. It is an exploratory recommendation-quality comparison, not an estimate of learning gain.

## Data boundary

- Reuse the TRAIN-fitted BKT checkpoint from RQ1. It estimates latent mastery, not observed ground-truth knowledge or probability of answering correctly.
- Build the graph and candidate problem pool from TRAIN only. Attach a skill label for readability only where the label maps to a TRAIN row. Prerequisite edges without an external curriculum source are explicitly marked prototype assumptions.
- Generate one fixed-seed snapshot per sampled VALIDATION student. Construct the BKT state by replaying only interactions through the snapshot cutoff. Keep student IDs and scenario-level outputs in ignored local data paths.
- Do not inspect RQ2 TEST scenarios or adjust any RQ2 policy using TEST before Lock C and Gate C.

## Shared scenario contract

Each scenario carries `scenario_id`, a local `student_id`, `cutoff_order_id`, and `state` with `state_type = BKT_p_mastery`, per-skill probabilities, and history length. An input assembler supplies that state, one graph version, and one candidate list to both B+ and Agent. Recommendation output must select a `problem_id` from the candidate list; the Agent also returns a short reason.

Candidate problems should be minimally valid and varied in target skill, prerequisite readiness, difficulty fit and remediation/progression. The candidate generator must not preselect the answer or make every candidate equivalent. B+ uses a frozen ordering: prerequisite-relevant weak skill, difficulty fit, remediation/progression, support count, then stable problem ID. This ordering is developed on VALIDATION and frozen before any RQ2 TEST evaluation.

## Development sequence

1. Verify BKT replay, graph acyclicity, train-only provenance, candidate diversity, deterministic B+ behavior, and identical inputs for both policies with synthetic tests.
2. Create validation scenarios and assess candidate coverage/diversity without publishing student identifiers.
3. Check whether a local Ollama runtime is available; if not, prepare the prompt/schema and record the hardware limitation without substituting an external model or treating a mock Agent as RQ2 results.
4. Only after validation development, lock graph, B+, candidate generator, prompt/model/runtime and evaluation rubric in Configuration Lock C. Evaluate TEST scenarios after Gate C, preserving repeated-run clustering by student.
