"""Verify saved revision requests, raw responses and public aggregates."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, read_json, save
from scripts.run_foundational_rq2_agent_revision1 import OUTPUT, PRIVATE, aggregate, prepare
from src.rq2.agent import Recommendation
from src.rq2.agent_revision import revision_request
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus, relevant_weak_sources


def main():
    summary = read_json(OUTPUT)
    if summary['agent_status'] != 'completed_validation_not_test' or summary['test_opened'] is not False:
        raise ValueError('completed VALIDATION revision required')
    _, config, schedule, cohorts, pins = prepare()
    if pins != summary['input_sha256'] or read_json(PRIVATE / 'schedule.json') != schedule:
        raise ValueError('revision inputs/schedule changed')
    if digest(PRIVATE / 'schedule.json') != summary['schedule_sha256'] or digest(PRIVATE / 'runs.json') != summary['private_runs_sha256']:
        raise ValueError('private run artifacts changed')
    records = read_json(PRIVATE / 'runs.json')
    if len(records) != len(schedule):
        raise ValueError('revision call count mismatch')
    for row, planned in zip(records, schedule):
        for key in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation', 'enum_ids'):
            if row[key] != planned[key]:
                raise ValueError('record differs from planned call')
        if row['policy'] != 'Agent_' + planned['arm']:
            raise ValueError('arm label mismatch')
        shared = planned['shared']
        request, bound = revision_request(shared, config, planned['arm'], planned['enum_ids'])
        if row['request'] != request:
            raise ValueError('recorded request differs from planned schema/prompt/input')
        if row['candidate_valid']:
            checked_telemetry(row['raw_response'], config['agent'], bound)
            selected = Recommendation.model_validate_json(row['raw_response']['message']['content'])
            if not selected.reason.strip() or len(selected.reason) > config['reason_max_chars']:
                raise ValueError('accepted reason violates revision contract')
            if selected.problem_id != row['selected_problem_id'] or selected.problem_id not in row['enum_ids']:
                raise ValueError('accepted selection not in actual response/enum')
            candidates = shared['candidates']
            position = next(i for i, c in enumerate(candidates) if c['problem_id'] == selected.problem_id)
            if position != row['selected_position'] or row['enum_ids'].index(selected.problem_id) != row['selected_enum_position']:
                raise ValueError('display or enum position mismatch')
            expected = recommend_foundational_bplus(shared, config['bplus'])['problem_id']
            if row['agrees_with_bplus'] != (selected.problem_id == expected):
                raise ValueError('agreement flag mismatch')
            relevant = relevant_weak_sources({**shared, 'graph': config['reference_graph']}, config['bplus'])
            if row['soft_source_remediation_selected'] != (candidates[position]['skill_id'] in relevant):
                raise ValueError('reference graph metric mismatch')
        elif row['error_stage'] is None or row['error_message'] is None or row['selected_problem_id'] is not None:
            raise ValueError('failed call diagnostics missing or fallback used')
    if json.loads(json.dumps(aggregate(records, cohorts))) != summary['cohorts']:
        raise ValueError('public metrics do not match saved calls')
    audit = {'stage': 'revision1_post_run_validation_audit', 'test_opened': False,
             'model_calls': 0, 'new_calls_verified': len(records),
             'valid_calls': sum(r['candidate_valid'] for r in records),
             'original_inputs_unchanged': True, 'requests_and_raw_responses_verified': True,
             'metrics_recomputed': True, 'display_and_enum_positions_verified': True,
             'summary_sha256': digest(OUTPUT), 'auditor_sha256': digest(Path(__file__))}
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_revision1_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
