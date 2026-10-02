"""Aggregate fixed-prefix VALIDATION coverage; never choose by policy output."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, load_pinned_inputs, save
from src.rq2.candidates import generate_candidates
from src.rq2.foundational_validation import compact_graph, relevant_weak_sources
from src.rq2.state import bkt_mastery_snapshot


def main():
    config, validation, model, audit, pool, pins = load_pinned_inputs()
    pins[Path(__file__).relative_to(ROOT).as_posix()] = digest(Path(__file__))
    graph = compact_graph(audit, 'curriculum_edges')
    pool = [c for c in pool if c['support'] >= config['minimum_train_support']]
    supported = {c['skill_id'] for c in pool}
    frozen = model.global_parameters_snapshot()
    rows = []
    # These are explicit diagnostic cutoffs, not seeds/thresholds to optimize.
    for cutoff in (5, 10, 20, 50):
        counts = {'prefix_length': cutoff, 'n_students': 0,
                  'students_with_supported_weak_link': 0,
                  'students_with_supported_weak_link_both_skills_observed': 0,
                  'students_with_candidate_source_target_signal': 0}
        edge_counts = {f"{e['source']}->{e['target']}": 0 for e in audit['standard_edges']}
        for _, history in validation.groupby('user_id', sort=True):
            prefix = history.sort_values('order_id', kind='stable').iloc[:cutoff]
            if len(prefix) != cutoff:
                continue
            state = bkt_mastery_snapshot(model, prefix, skill_universe=graph['skills'])
            state['skills'] = {s: state['skills'][s] for s in graph['skills']}
            observed = set(prefix.skill_id.astype(str))
            weak_links = [e for e in graph['edges']
                          if e['prerequisite'] in supported and e['target'] in supported
                          and state['skills'][e['prerequisite']] < config['bplus']['source_weak_threshold']
                          and state['skills'][e['target']] < config['bplus']['target_weak_threshold']]
            candidates = generate_candidates(state, graph, pool, config['candidates_per_scenario'])
            relevant = relevant_weak_sources({'state': state, 'graph': graph, 'candidates': candidates}, config['bplus'])
            counts['n_students'] += 1
            counts['students_with_supported_weak_link'] += int(bool(weak_links))
            counts['students_with_supported_weak_link_both_skills_observed'] += int(any(
                e['prerequisite'] in observed and e['target'] in observed for e in weak_links))
            counts['students_with_candidate_source_target_signal'] += int(any(
                c['skill_id'] in relevant for c in candidates))
            weak_standard_pairs = {(graph['skill_to_standard'][e['prerequisite']], graph['skill_to_standard'][e['target']]) for e in weak_links}
            for a, b in weak_standard_pairs:
                edge_counts[f'{a}->{b}'] += 1
        counts['supported_weak_link_student_counts_by_standard_edge'] = edge_counts
        rows.append(counts)
        print(json.dumps({k: v for k, v in counts.items() if k != 'supported_weak_link_student_counts_by_standard_edge'}), flush=True)
    if model.global_parameters_snapshot() != frozen:
        raise RuntimeError('fitted BKT parameters changed')
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_coverage_audit.json', {
        'stage': 'validation_coverage_diagnostic_not_policy_comparison', 'test_opened': False,
        'thresholds_changed': False, 'policy_outputs_used_for_selection': False,
        'input_sha256': pins, 'diagnostics': rows,
        'note': 'Weak latent priors for unobserved skills are not observed learner deficits; report both-observed coverage separately.'})


if __name__ == '__main__':
    main()
