# RQ2 development design (validation only)

RQ2 compares a deterministic policy (B+) with a local LLM policy under identical inputs: one BKT latent-mastery snapshot, the same prerequisite graph, and the same candidate problems. In the metadata-only design, this is an operational selection/ranking comparison, not a measure of pedagogical quality or learning gain.

## Data boundary

- Reuse the TRAIN-fitted BKT checkpoint from RQ1. It estimates latent mastery, not observed ground-truth knowledge or probability of answering correctly.
- Build the graph and candidate problem pool from TRAIN only. Attach a skill label for readability only where the label maps to a TRAIN row. Record edge class (`cross_standard_curriculum_sequence` or `within_cluster_sibling`) separately from evidence basis; do not create a directed edge among sibling substandards by default. Any active edge is a curriculum-order constraint for this prototype, not a demonstrated causal mastery prerequisite, and remains subject to human review.
- Generate one fixed-seed snapshot per sampled VALIDATION student. Construct the BKT state by replaying only interactions through the snapshot cutoff. Keep student IDs and scenario-level outputs in ignored local data paths.
- Do not inspect RQ2 TEST scenarios or adjust any RQ2 policy using TEST before Lock C and Gate C.

## Shared scenario contract

Each scenario carries `scenario_id`, a local `student_id`, `cutoff_order_id`, and `state` with `state_type = BKT_p_mastery`, per-skill probabilities, and history length. An input assembler supplies that state, one graph version, and one metadata-only candidate list (`problem_id`, `skill_id`, TRAIN success-rate difficulty proxy, support) to both B+ and Agent. The candidate inventory is built from TRAIN and excludes metadata-conflict problems; it does not use `rq2_text_eligible`, because neither policy needs question text to select an ID. Recommendation output must select a `problem_id` from the candidate list; the Agent also returns a short reason grounded only in the supplied metadata and graph.

Candidate problems should be minimally valid and varied in target skill, mastery and TRAIN success rate. The candidate generator must not preselect the answer or make every candidate equivalent. B+ v4 draft orders by weak source linked directly to a weak target represented in the candidates, proximity to the fixed TRAIN success-rate target of 0.7, larger support, then stable problem ID. This is soft ranking, not a hard readiness gate. The ordering is developed on VALIDATION and frozen before any RQ2 TEST evaluation.

### Baselines and order-bias check

Evaluate two simple baselines on the same candidate set: (1) uniform random selection over valid candidate problem IDs, independent of their display positions; and (2) always choose the first candidate in the presented list. For each validation repetition, create a seeded permutation of the candidate list and give that same presented order to B+, Agent, and both baselines. Log the seed/order with the scenario outputs, preserve candidate-set membership, and use different permutations across repetitions. The first-item baseline therefore changes its selected ID with presentation order, while the random baseline samples uniformly by ID. Report Agent/B+ choice frequencies by presented position and whether their choices remain stable as an item moves; this directly checks position sensitivity. Freeze permutation generation and repetition count before Lock C, and do not use RQ2 TEST to tune them.

These baselines measure operational behavior only. Agreement with B+, valid candidate selection, constraint compliance, reproducibility, latency, and position sensitivity can be reported from metadata-only inputs. They do not establish that a recommended problem is educationally appropriate, that its content matches the stated skill, or that a learner benefits.

### Content attribution and license

The ASSISTments Illustrative Mathematics Copyright Notice states CC BY-NC-SA 4.0 for IM curricular content distributed on ASSISTments and notes that some problems were modified or split for platform use. This notice does not establish that every FoundationalASSIST problem is IM content. The current content-review metadata has no per-problem source/attribution field, so do not apply the IM license to the entire dataset or publicly redistribute problem text until item-level provenance and applicable terms are established. Prefer paraphrase in reports and preserve attribution/ShareAlike obligations for content confirmed to fall under that notice.

The metadata-only bank is a separate operational inventory, not evidence of pedagogical item quality. The Agent sees only `problem_id`, skill, TRAIN success-rate difficulty proxy, support, state and graph, so it is selecting from a ranking function over these supplied signals. Keep text eligibility fail-closed for any display, demo, or human content-quality scoring. Numeric IDs and train success-rate proxies alone are insufficient for blinded pedagogical judgment.

Content review is staged and limited to actual use: first generate and inspect VALIDATION scenarios and their candidate lists; then form the deduplicated union of problem IDs that actually appear in those lists. Only those surfaced items need content review for a content-based display or human pedagogical assessment. Do not ask a volunteer to review the entire 2,233-item automatic-screen-pass set. Use the same reviewer for the provisional graph and surfaced problem content, if available. Metadata-only development may proceed without content review as long as item text is not shown and results are not described as pedagogical quality. No reviewer has been identified yet.

## Development sequence

Coverage update 2026-10-02: retain the original 50-student random-prefix pilot. Add a separately reported exploratory challenge cohort after the fixed-prefix audit, using all students with an observed, TRAIN-supported weak source–target link at prefix 50. Sample a standard edge uniformly, then an eligible ID pair and one problem per endpoint; fill six remaining candidate slots using the original generator. State, membership and permutation remain identical across graph variants. This is a conditional ablation on graph-constructed candidates, not end-to-end removal of graph information or a representative cohort. Do not merge cohort outcomes or count overlapping students as independent. Score soft remediation against the same full reference graph in both variants; these labels represent author assumptions, not educational correctness. See `reports/foundationalassist_v4_rq2_coverage.md` for all prefix diagnostics and limitations. No TEST is used.

Update 2026-10-02: the user authorized continuing this educational project independently with author-proposed curriculum assumptions. The v4 draft graph config and `reports/foundationalassist_v4_rq2_graph_decisions.md` record nine standard-edge hypotheses and sources. Human review is not a blocker for metadata-only development; graph status remains explicitly not expert-validated. AI critique is not human review. Add a VALIDATION sensitivity comparison with edges removed while holding nodes, states, candidate membership and permutations fixed. This is not pedagogical validation. Freeze retained graph variants before TEST; content eligibility and Lock C keep their separate requirements.

1. Verify BKT replay, graph acyclicity, train-only provenance, candidate diversity, deterministic B+ behavior, and identical inputs for both policies with synthetic tests.
2. Create validation scenarios, assess candidate coverage/diversity without publishing student identifiers, and save the deduplicated set of candidate problem IDs actually surfaced.
3. Validate the random-by-ID and always-first baselines under shared, seeded candidate-order permutations; report position sensitivity separately from ranking/constraint metrics.
4. If content-based review is planned, have the graph reviewer inspect only the surfaced VALIDATION candidate items and record per-item decisions; do not expose TEST scenarios.
5. Check whether a local Ollama runtime is available; if not, prepare the prompt/schema and record the hardware limitation without substituting an external model or treating a mock Agent as RQ2 results.
6. Only after validation development, lock graph, B+, candidate generator, order randomization, baselines, prompt/model/runtime and evaluation rubric in Configuration Lock C. Evaluate TEST scenarios after Gate C, preserving repeated-run clustering by student.
