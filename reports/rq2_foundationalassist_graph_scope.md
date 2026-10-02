# RQ2 FoundationalASSIST graph scope — draft for review

Status updated 2026-10-02: **metadata-only TRAIN inventory and author-proposed curriculum graph prepared for VALIDATION development**. Concrete provisional edges and sources are in `reports/foundationalassist_v4_rq2_graph_decisions.md` and `configs/foundationalassist_v4_rq2_curriculum_graph.json`. No expert validation, text eligibility approval, Lock C or RQ2 TEST is implied.

## Proposed pilot skill universe

Select a coherent, manageable set of 15 CCSS standard codes (18 FoundationalASSIST skill IDs). Counts are single-skill TRAIN interactions, aggregated by standard code where several dataset IDs map to one standard. This is an eligible target universe, not the final scenario candidate set. Metadata-only candidates need TRAIN provenance and nonconflicting metadata; content review is additionally required when displaying or rating problem text.

| Standard code | FoundationalASSIST skill ID(s) | Single-skill TRAIN interactions |
|---|---:|---:|
| 6.NS.A.1 | 135 | 47,537 |
| 6.RP.A.3a | 129 | 22,467 |
| 6.RP.A.3b | 130 | 64,697 |
| 6.RP.A.3c | 131, 132, 133 | 54,623 |
| 6.RP.A.3d | 134 | 12,333 |
| 7.RP.A.1 | 193 | 9,662 |
| 7.RP.A.2a | 194 | 42,031 |
| 7.RP.A.2b | 195 | 9,459 |
| 7.RP.A.2c | 196 | 31,860 |
| 7.RP.A.3 | 198 | 82,296 |
| 6.EE.B.5 | 164 | 15,997 |
| 6.EE.B.6 | 165 | 11,777 |
| 6.EE.B.7 | 166 | 24,846 |
| 7.EE.B.4a | 217, 1136 | 54,869 |
| 8.EE.C.7b | 259 | 23,592 |

The set emphasizes fraction division, ratios/rates, proportional relationships, and equations. The metadata-only inventory contains 1,063 problem-skill pairs from TRAIN across these 15 standards/18 skill IDs, after excluding the one conflicting-metadata problem. It includes candidates regardless of `rq2_text_eligible`; the inventory contains no problem body, choices, answer text, or student identifiers. Its item-level counts are in the ignored local file `data/processed/foundationalassist_v4/rq2_metadata_candidate_bank_summary.json`.

This is an inventory, not the final scenario candidate set. Later validation development may apply a prespecified support floor and diversity rules using TRAIN/VALIDATION only. Generate VALIDATION scenarios first, then review only unique problem IDs that actually surface in those candidate lists when content display or human content assessment is planned. Do not review the full 2,233-item automatic-screen-pass set as a prerequisite to metadata-only evaluation. Restrict displayed or human-rated problem content to items that pass `rq2_text_eligible`; do not relax content criteria to retain all 15 standards.

## Edge annotation rules

- `cross_standard_curriculum_sequence`: a proposed ordering between distinct standards/domains/grades, with a specific curriculum source and reviewer decision recorded. Grade order alone is not evidence of a mastery prerequisite.
- `within_cluster_sibling`: standards such as `6.RP.A.3a`–`6.RP.A.3d` or pilot standards `7.RP.A.2a`–`7.RP.A.2c` are represented as sibling components by default. Do not connect them as a→b→c unless the reviewer identifies a specific sourced rationale.
- An edge used by the policy is a curriculum-order constraint for this exploratory system. It is not a causal claim that students must master the source skill before learning the target skill.
- Preserve source URL/title, exact standard identifiers, rationale in original wording (paraphrased in our notes), reviewer role/date, and accept/reject/uncertain decision per edge.

Concrete author-proposed edges are now recorded separately in `reports/foundationalassist_v4_rq2_graph_decisions.md`; the broad families below remain historical review prompts. The official [Common Core Mathematics Standards](https://corestandards.org/wp-content/uploads/2023/09/ADA-Compliant-Math-Standards.pdf) identify standard content and organization, not empirically validated mastery prerequisites.

### Reviewer response prompts (not active graph edges)

Please mark each proposed family as **accept as curriculum-order constraint / reject / uncertain / split into narrower pairs**, and add a short rationale or curriculum source. These are prompts for review only; none is currently encoded as an edge.

| Candidate family to discuss | Edge type | Reviewer decision / rationale / source |
|---|---|---|
| `6.NS.A.1` → one or more of `6.RP.A.3a–d` | cross-standard curriculum sequence | |
| one or more of `6.RP.A.3a–d` → `7.RP.A.1`, `7.RP.A.2a–c`, or `7.RP.A.3` | cross-standard curriculum sequence | |
| ratio/proportional-reasoning standards in grades 6–7 → equation standards `6.EE.B.5–7` or `7.EE.B.4a` | cross-domain curriculum sequence | |
| `7.EE.B.4a` → `8.EE.C.7b` | cross-grade curriculum sequence | |
| `6.RP.A.3a–d` and `7.RP.A.2a–c` internally | within-cluster sibling | Should these remain parallel, or is any narrower order supported? |

For the broad families above, please name the specific source and target codes if only some links are appropriate. Grade/domain ordering is not, by itself, evidence of a prerequisite in the mastery/causal sense.

## License and per-problem provenance

The [ASSISTments Illustrative Mathematics Copyright Notice](https://www.assistments.org/copyright-notice/illustrative-mathematics-copyright-notice) states that IM curricular content distributed on ASSISTments is under CC BY-NC-SA 4.0 and says some items were altered or split for platform use. It does not say all FoundationalASSIST content is from IM. The current `rq2_content_review.json` has 3,368 problem records; its metadata variants have no source/attribution field, none of the records has a reviewer or source recorded, and all remain `rq2_text_eligible=False` (2,233 pass the automatic screen only). Therefore the license/source must be resolved per item or from a reliable dataset provenance source before publicly displaying or redistributing problem text. Do not infer item-level IM provenance from a CCSS-formatted `node_code` alone.

For a metadata-only comparison, the Agent sees IDs, skill labels, TRAIN difficulty proxies, support, state and graph. This can test operational selection/ranking, valid-candidate choice, graph-constraint compliance, agreement with B+, latency/stability, and position bias; it cannot establish pedagogical quality, content-skill fit, or learning benefit. Include uniform random-by-problem-ID and always-first-in-presented-order baselines. Shuffle the presented candidate order with logged, seeded permutations shared by all policies and baselines on each repetition, keeping membership fixed. Use the same reviewer for graph and the unique VALIDATION candidate items surfaced if one becomes available; the reviewer has not yet been identified.

## Human review status

User direction on 2026-10-02 permits author-proposed graph assumptions for independent metadata-only development. Keep every edge provisional, and distinguish AI critique from human curriculum review. No expert validation has occurred. Human review is still required before claiming expert approval or pedagogical content quality. This note does not authorize sending any message to a lecturer or another chat.
