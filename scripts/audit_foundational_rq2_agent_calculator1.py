"""Audit calculator-only intervention, raw outputs, B+ parity and metrics."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, read_json, save
from scripts.run_foundational_rq2_agent_calculator1 import OUTPUT, PRIVATE, PREVIOUS_PRIVATE, comparisons, prepare_calculator
from src.rq2.agent import Recommendation
from src.rq2.calculator_agent import calculator_request, recommend_calculator_bplus
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus, relevant_weak_sources


def main():
    trial, config, schedule, cohorts, _ = prepare_calculator()
    summary = read_json(OUTPUT)
    if summary['test_opened'] is not False or summary['agent_status'] != 'completed_validation_not_test':
        raise ValueError('completed VALIDATION calculator trial required')
    for relative, expected in summary['input_sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('calculator or previous study inputs changed')
    if schedule != read_json(PRIVATE / 'schedule.json') or digest(PRIVATE / 'schedule.json') != summary['schedule_sha256']:
        raise ValueError('calculator schedule mismatch')
    rows = read_json(PRIVATE / 'runs.json')
    if len(rows) != trial['new_calls'] or digest(PRIVATE / 'runs.json') != summary['private_runs_sha256']:
        raise ValueError('calculator call count/hash mismatch')
    key = lambda r: tuple(r[k] for k in ('cohort', 'scenario_id', 'repetition', 'graph_variant'))
    previous = {key(r): r for r in read_json(PREVIOUS_PRIVATE / 'runs.json')}
    for row, planned in zip(rows, schedule):
        for field in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation', 'enum_ids'):
            if row[field] != planned[field]:
                raise ValueError('record differs from fixed schedule')
        if row['policy'] != 'Agent_calculator1':
            raise ValueError('unexpected calculator policy label')
        request, bound = calculator_request(planned['shared'], config, planned['enum_ids'])
        if row['request'] != request:
            raise ValueError('actual request differs from planned calculator request')
        prior_request = previous[key(row)]['request']
        restored = deepcopy(request)
        payload = json.loads(restored['messages'][1]['content'])
        evidence = payload.pop('calculator_evidence')
        if payload != json.loads(prior_request['messages'][1]['content']):
            raise ValueError('state, graph or candidates changed')
        if not request['messages'][0]['content'].startswith(prior_request['messages'][0]['content']):
            raise ValueError('old objective changed')
        restored['messages'] = deepcopy(prior_request['messages'])
        if restored != prior_request:
            raise ValueError('runtime, enum or schema changed beyond declared intervention')
        shared = planned['shared']
        mastery, represented = shared['state']['skills'], {c['skill_id'] for c in shared['candidates']}
        policy = config['bplus']
        # Independent reconstruction from this variant's graph; never reference_graph.
        weak = {e['prerequisite'] for e in shared['graph']['edges']
                if e['target'] in represented and mastery[e['target']] < policy['target_weak_threshold']
                and mastery[e['prerequisite']] < policy['source_weak_threshold']}
        expected_evidence = [{'problem_id': c['problem_id'], 'weak_linked_source': c['skill_id'] in weak,
                              'train_success_gap': abs(c['difficulty'] - policy['target_train_success_rate']),
                              'train_support': c['support']} for c in shared['candidates']]
        if evidence != expected_evidence:
            raise ValueError('wrong calculator evidence or candidate order')
        bplus = recommend_foundational_bplus(shared, policy)
        if recommend_calculator_bplus(shared, policy, evidence) != bplus:
            raise ValueError('calculator B+ differs from frozen B+')
        if row['candidate_valid']:
            checked_telemetry(row['raw_response'], config['agent'], bound)
            selected = Recommendation.model_validate_json(row['raw_response']['message']['content'])
            if (row['schema_valid'] is not True or selected.problem_id != row['selected_problem_id']
                    or selected.problem_id not in row['enum_ids'] or not selected.reason.strip()
                    or len(selected.reason) > config['reason_max_chars'] or row['error_stage'] is not None):
                raise ValueError('accepted output violates calculator contract')
            candidates = shared['candidates']
            position = next(i for i, c in enumerate(candidates) if c['problem_id'] == selected.problem_id)
            if position != row['selected_position'] or row['enum_ids'].index(selected.problem_id) != row['selected_enum_position']:
                raise ValueError('display/enum position mismatch')
            relevant = relevant_weak_sources({**shared, 'graph': config['reference_graph']}, policy)
            if row['agrees_with_bplus'] != (selected.problem_id == bplus['problem_id']) or row['soft_source_remediation_selected'] != (candidates[position]['skill_id'] in relevant):
                raise ValueError('recorded metric labels mismatch')
        elif row['error_stage'] is None or row['error_message'] is None or row['selected_problem_id'] is not None:
            raise ValueError('invalid call missing diagnostic or used fallback')
    metrics = comparisons(rows, cohorts)
    if json.loads(json.dumps(metrics)) != summary['cohorts']:
        raise ValueError('public metrics differ from raw calls')
    positions, diagnostic = {}, {}
    for cohort in cohorts:
        positions[cohort], diagnostic[cohort] = {}, {}
        for variant in config['graph_variants']:
            group = [r for r in rows if r['cohort'] == cohort and r['graph_variant'] == variant]
            valid = [r for r in group if r['candidate_valid']]
            positions[cohort][variant] = {
                'first_display_count': sum(r['selected_position'] == 0 for r in valid),
                'valid_calls': len(valid),
                'enum_position_counts': dict(sorted(Counter(r['selected_enum_position'] for r in valid).items())),
                'error_stage_counts': dict(Counter(r['error_stage'] for r in group if r['error_stage']))}
            # Extract exact denominators from records for the predeclared diagnostic.
            per_student = {}
            for row in group:
                per_student.setdefault(row['student_id'], []).append(row)
            complete = [rs for rs in per_student.values() if len(rs) == 3 and all(r['candidate_valid'] for r in rs)]
            variable = sum(len({r['selected_problem_id'] for r in rs}) > 1 for rs in complete)
            agreement = sum(r['agrees_with_bplus'] for r in group) / len(group)
            variability = variable / len(complete) if complete else None
            diagnostic[cohort][variant] = {
                'agreement_count': sum(r['agrees_with_bplus'] for r in group), 'calls': len(group),
                'variable_students': variable, 'complete_students': len(complete),
                'passed': len(valid) == len(group) and agreement >= .95 and variability is not None and variability <= .10}
    probes = read_json(PRIVATE / 'preflight_calls.json')
    if len(probes) != 4:
        raise ValueError('four preserved context probes required')
    for index, variant in enumerate(config['graph_variants']):
        requests = [calculator_request(r['shared'], config, r['enum_ids']) for r in schedule if r['graph_variant'] == variant]
        request, bound = max(requests, key=lambda pair: pair[1])
        counts = []
        for factor, transcript in zip((1, 2), probes[2 * index:2 * index + 2]):
            expected = deepcopy(request)
            expected['options']['num_ctx'] *= factor
            if transcript['request'] != expected:
                raise ValueError('context probe request mismatch')
            counts.append(checked_telemetry(transcript['response'], {**config['agent'], 'num_ctx': factor * config['agent']['num_ctx']}, bound))
        if counts[0] != counts[1] or counts[0] != summary['context_probe']['probes'][index]['prompt_eval_count']:
            raise ValueError('context telemetry mismatch')
    audit = {'stage': 'calculator1_post_run_validation_audit', 'test_opened': False,
             'model_calls': 0, 'new_calls_verified': len(rows), 'valid_calls': sum(r['candidate_valid'] for r in rows),
             'requests_changed_evidence_and_instruction_only': True, 'bplus_parity_verified': len(rows),
             'no_edge_evidence_uses_only_supplied_graph': True, 'candidate_display_and_enum_orders_unchanged': True,
             'original_studies_unchanged': True, 'raw_responses_and_metrics_verified': True,
             'context_probes_verified': 4, 'positions': positions, 'predeclared_diagnostic': diagnostic,
             'lock_c_authorized': False, 'summary_sha256': digest(OUTPUT), 'auditor_sha256': digest(Path(__file__))}
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_calculator1_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
