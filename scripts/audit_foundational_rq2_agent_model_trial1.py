"""Read-only model-trial audit, including exact model-only request changes."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, read_json, save
from scripts.run_foundational_rq2_agent_revision1 import prepare
from scripts.run_foundational_rq2_agent_model_trial1 import CONFIG, OUTPUT, PRIVATE
from src.rq2.agent import Recommendation
from src.rq2.agent_revision import revision_request
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus, relevant_weak_sources, summarize_operational


def main():
    trial, summary = read_json(CONFIG), read_json(OUTPUT)
    if summary['test_opened'] is not False or summary['agent_status'] != 'completed_validation_not_test':
        raise ValueError('completed VALIDATION trial required')
    for relative, expected in summary['input_sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('trial or previous study inputs changed')
    _, config, schedule, cohorts, _ = prepare()
    config['agent'] = {**config['agent'], 'model': trial['model']}
    schedule = [r for r in schedule if r['arm'] == 'schema_and_objective']
    if schedule != read_json(PRIVATE / 'schedule.json') or digest(PRIVATE / 'schedule.json') != summary['schedule_sha256']:
        raise ValueError('trial schedule mismatch')
    rows = read_json(PRIVATE / 'runs.json')
    before = read_json(ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_revision1/runs.json')
    key = lambda r: tuple(r[k] for k in ('cohort', 'scenario_id', 'repetition', 'graph_variant'))
    original = {key(r): r for r in before if r['policy'] == 'Agent_schema_and_objective'}
    if len(rows) != trial['new_calls'] or digest(PRIVATE / 'runs.json') != summary['private_runs_sha256']:
        raise ValueError('trial call count/hash mismatch')
    for row, planned in zip(rows, schedule):
        for field in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation', 'enum_ids'):
            if row[field] != planned[field]:
                raise ValueError('record differs from fixed schedule')
        expected = deepcopy(original[key(row)]['request'])
        expected['model'] = trial['model']
        request, bound = revision_request(planned['shared'], config, planned['arm'], planned['enum_ids'])
        if row['request'] != expected or request != expected:
            raise ValueError('request changed more than the model')
        if row['candidate_valid']:
            checked_telemetry(row['raw_response'], config['agent'], bound)
            selected = Recommendation.model_validate_json(row['raw_response']['message']['content'])
            if (selected.problem_id != row['selected_problem_id'] or selected.problem_id not in row['enum_ids']
                    or not selected.reason.strip() or len(selected.reason) > config['reason_max_chars']):
                raise ValueError('accepted output violates revision contract')
            candidates = planned['shared']['candidates']
            position = next(i for i, c in enumerate(candidates) if c['problem_id'] == selected.problem_id)
            if position != row['selected_position'] or row['enum_ids'].index(selected.problem_id) != row['selected_enum_position']:
                raise ValueError('choice position mismatch')
            bplus = recommend_foundational_bplus(planned['shared'], config['bplus'])['problem_id']
            relevant = relevant_weak_sources({**planned['shared'], 'graph': config['reference_graph']}, config['bplus'])
            if row['agrees_with_bplus'] != (selected.problem_id == bplus) or row['soft_source_remediation_selected'] != (candidates[position]['skill_id'] in relevant):
                raise ValueError('recorded metric labels mismatch')
        elif row['error_stage'] is None or row['error_message'] is None or row['selected_problem_id'] is not None:
            raise ValueError('failed call missing diagnostic or used a fallback')
    metrics, positions = {}, {}
    for cohort, source in cohorts.items():
        group = [r for r in before + rows if r['cohort'] == cohort]
        metrics[cohort] = {'n_students': source['n_students'], 'policies': summarize_operational(source['legacy_records'] + group)['policies']}
        positions[cohort] = {v: dict(sorted(Counter(r['selected_enum_position'] for r in rows if r['cohort'] == cohort and r['graph_variant'] == v and r['candidate_valid']).items())) for v in config['graph_variants']}
    if json.loads(json.dumps(metrics)) != summary['cohorts']:
        raise ValueError('public metrics differ from private calls')
    audit = {'stage': 'model_trial1_post_run_validation_audit', 'test_opened': False,
             'model_calls': 0, 'new_calls_verified': len(rows), 'valid_calls': sum(r['candidate_valid'] for r in rows),
             'requests_changed_model_only': True, 'original_studies_unchanged': True,
             'raw_responses_and_metrics_verified': True, 'enum_position_counts_valid': positions,
             'summary_sha256': digest(OUTPUT), 'auditor_sha256': digest(Path(__file__))}
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_model_trial1_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
