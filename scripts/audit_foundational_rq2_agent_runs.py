"""Read-only audit of completed local VALIDATION calls; no model invocation."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, local_json, read_json, save
from src.rq2.foundational_validation import (
    recommend_foundational_bplus, relevant_weak_sources, shared_repetitions,
    summarize_operational,
)


def audit_cohort(cohort, config, graph):
    private = ROOT / 'data/processed/foundationalassist_v4/rq2_validation'
    suffix = 'validation' if cohort == 'representative' else 'challenge'
    if cohort == 'challenge':
        private /= 'challenge'
    public = ROOT / f'artifacts/tables/foundationalassist_v4_rq2_{suffix}_summary.json'
    summary = read_json(public)
    if (summary['agent_status'] != 'validation_run_completed_not_test'
            or summary['test_opened'] is not False or summary['context_verified'] is not True):
        raise ValueError('completed VALIDATION run with verified context required')
    for relative, expected in summary['input_sha256'].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError('pinned run input changed')
    if summary['config_sha256'] != digest(ROOT / 'configs/foundationalassist_v4_rq2_validation.json'):
        raise ValueError('run config changed')
    if summary['scenarios_sha256'] != digest(private / 'scenarios.json'):
        raise ValueError('saved scenarios changed')
    cases = read_json(private / 'scenarios.json')
    deterministic = read_json(private / 'deterministic_runs.json')
    agent = read_json(private / 'agent_runs.json')
    if len({case['student_id'] for case in cases}) != len(cases):
        raise ValueError('one scenario per student required')
    expected = {}
    for case, repetition, variant, order, _, shared in shared_repetitions(cases, graph, config):
        expected[(case['scenario_id'], repetition, variant)] = (case, order, shared)
    if len(agent) != len(expected) or len(deterministic) != 3 * len(expected):
        raise ValueError('call count mismatch')
    seen = set()
    for row in deterministic + agent:
        key = (row['scenario_id'], row['repetition'], row['graph_variant'])
        call_key = key + (row['policy'],)
        if call_key in seen or key not in expected:
            raise ValueError('duplicate or unknown call')
        seen.add(call_key)
        case, order, shared = expected[key]
        if row['student_id'] != case['student_id'] or row['permutation'] != order:
            raise ValueError('call inputs disagree with saved scenario/permutation')
        if row['candidate_valid']:
            by_id = {c['problem_id']: c for c in shared['candidates']}
            chosen = row['selected_problem_id']
            if not row['schema_valid'] or chosen not in by_id:
                raise ValueError('valid flag disagrees with schema/candidate membership')
            position = next(i for i, c in enumerate(shared['candidates']) if c['problem_id'] == chosen)
            if row['selected_position'] != position:
                raise ValueError('recorded candidate position mismatch')
            bplus = recommend_foundational_bplus(shared, config['bplus'])['problem_id']
            if row['agrees_with_bplus'] != (chosen == bplus):
                raise ValueError('B+ agreement mismatch')
            reference = {**shared, 'graph': graph}
            relevant = relevant_weak_sources(reference, config['bplus'])
            if row['soft_source_remediation_selected'] != (by_id[chosen]['skill_id'] in relevant):
                raise ValueError('common reference graph metric mismatch')
        elif row['selected_problem_id'] is not None:
            raise ValueError('invalid output must not be accepted as a selection')
    policies = summarize_operational(deterministic + agent)['policies']
    # JSON converts integer position-counter keys to strings on disk.
    if json.loads(json.dumps(policies)) != summary['policies']:
        raise ValueError('public metrics disagree with private saved calls')
    probe = summary['context_probe']
    if probe['verified'] is not True or not all(p['same_prompt_token_count'] for p in probe['probes']):
        raise ValueError('context preflight missing')
    result = {
        'cohort': cohort, 'n_students': len(cases), 'agent_calls': len(agent),
        'candidate_valid_calls': sum(r['candidate_valid'] for r in agent),
        'schema_valid_calls': sum(r['schema_valid'] for r in agent),
        'calls_failing_after_schema_validation': sum(r['schema_valid'] and not r['candidate_valid'] for r in agent),
        'accepted_selection_membership_and_positions_verified': True,
        'summary_recomputed_from_private_calls': True, 'pinned_inputs_unchanged': True,
        'summary_sha256': digest(public), 'private_calls_sha256': digest(private / 'agent_runs.json'),
        'model_digest': probe['model_digest'], 'ollama_version': probe['ollama_version'],
    }
    return result, {c['student_id'] for c in cases}


def main():
    config = read_json(ROOT / 'configs/foundationalassist_v4_rq2_validation.json')
    graph = read_json(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_curriculum_graph.json')
    # Reference labels need only this projection; never call an Agent here.
    from src.rq2.foundational_validation import compact_graph
    graph = compact_graph(graph, 'curriculum_edges')
    results, students = [], []
    for cohort in ('representative', 'challenge'):
        result, cohort_students = audit_cohort(cohort, config, graph)
        results.append(result)
        students.append(cohort_students)
    models = local_json('tags')['models']
    version = local_json('version')['version']
    for result in results:
        if (version != result['ollama_version'] or not any(
                m['name'] == config['agent']['model'] and m['digest'] == result['model_digest'] for m in models)):
            raise ValueError('runtime/model identity differs from feasibility probe')
    audit = {'stage': 'post_run_validation_audit_not_test', 'test_opened': False,
             'model_invocations': 0, 'runtime_identity_matches_both_runs': True,
             'cohorts': results, 'overlapping_students_between_cohorts': len(students[0] & students[1]),
             'auditor_sha256': digest(Path(__file__)),
             'limitation': 'Raw response/reason not retained by this runner; generic ValueError logs cannot distinguish every refusal cause. No pooling of cohort estimates.'}
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
