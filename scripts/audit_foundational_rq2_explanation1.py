"""No-model audit of prepared evidence, templates or completed explanation calls."""

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import digest, read_json, save
from scripts.run_foundational_rq2_explanation1 import PRIVATE, OUTPUT, aggregate, prepare_explanation
from src.rq2.calculator_agent import candidate_evidence
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus
from src.rq2.grounded_explanation import explanation_packet, explanation_request, run_explanation


def main():
    config, policy, schedule, cohorts, pins, baselines = prepare_explanation()
    summary = read_json(OUTPUT)
    if summary['test_opened'] is not False or summary['input_sha256'] != pins:
        raise ValueError('validation-only manifest changed')
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('pinned input changed')
    if read_json(PRIVATE / 'schedule.json') != schedule or digest(PRIVATE / 'schedule.json') != summary['schedule_sha256']:
        raise ValueError('saved schedule changed')
    if read_json(PRIVATE / 'template_runs.json') != baselines or digest(PRIVATE / 'template_runs.json') != summary['template_runs_sha256']:
        raise ValueError('template runs changed')
    for item in schedule:
        packet, factor = explanation_packet(item['shared'], policy)
        if packet['selected_problem_id'] != recommend_foundational_bplus(item['shared'], policy)['problem_id']:
            raise ValueError('fixed selection differs from original B+')
        remaining, steps = candidate_evidence(item['shared'], policy), []
        independent_factor = 'single_candidate' if len(remaining) == 1 else None
        for name, key in (('source_signal', lambda e: not e['weak_linked_source']),
                          ('success_gap', lambda e: e['train_success_gap']),
                          ('support', lambda e: -e['train_support']),
                          ('problem_id', lambda e: e['problem_id'])):
            count = len(remaining)
            best = min(key(e) for e in remaining)
            remaining = [e for e in remaining if key(e) == best]
            steps.append({'factor': name, 'before': count, 'after': len(remaining)})
            if independent_factor is None and len(remaining) == 1:
                independent_factor = name
        if steps != packet['selection_trace'] or independent_factor != factor:
            raise ValueError('decisive factor/trace mismatch')
        if not item['shared']['graph']['edges'] and (packet['graph_has_edges'] or packet['selected_numeric_evidence']['weak_linked_source']):
            raise ValueError('reference graph leaked into no-edge evidence')
        explanation_request(packet, config, item['enum_ids'])
    rows = []
    drift = summary['agent_status'] == 'completed_runtime_drift_not_validated'
    completed = summary['agent_status'] == 'completed_validation_not_test' or drift
    if drift and (summary['runtime_identity_unchanged'] is not False
                  or summary['observed_final_ollama_version'] == summary['ollama_version']):
        raise ValueError('runtime-drift archive missing its recorded mismatch')
    if completed:
        rows = read_json(PRIVATE / 'runs.json')
        if len(rows) != config['new_calls'] or summary['study_calls_completed'] != len(rows) or digest(PRIVATE / 'runs.json') != summary['private_runs_sha256']:
            raise ValueError('completed runs count/hash mismatch')
        for row, item in zip(rows, schedule):
            for field in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation'):
                if row[field] != item[field]:
                    raise ValueError('actual call schedule mismatch')
            packet, factor = explanation_packet(item['shared'], policy)
            request, _ = explanation_request(packet, config, item['enum_ids'])
            if row['request'] != request or row['packet'] != packet or row['fixed_problem_id'] != packet['selected_problem_id'] or row['expected_factor'] != factor:
                raise ValueError('actual explanation inputs or fixed selection mismatch')
            if row['raw_response'] is not None:
                replayed = run_explanation(item['shared'], policy, config, item['enum_ids'],
                                          lambda request, timeout: row['raw_response'])
                for field, value in replayed.items():
                    if field != 'latency_seconds' and row[field] != value:
                        raise ValueError('raw response/check/render replay mismatch: ' + field)
            elif row['error_stage'] != 'transport' or row['accepted'] or row['rendered_explanation'] is not None:
                raise ValueError('call lacks raw response without explicit transport failure')
            if row['draft_semantically_verified'] is not False:
                raise ValueError('unreviewed draft claimed verified')
        metrics = aggregate(rows, baselines, cohorts, ['curriculum_edges', 'no_edges'])
        if json.loads(json.dumps(metrics)) != summary['cohorts']:
            raise ValueError('public metrics differ from raw calls')
        probes = read_json(PRIVATE / 'preflight_calls.json')
        if len(probes) != 4:
            raise ValueError('four raw context probes required')
        for index, variant in enumerate(('curriculum_edges', 'no_edges')):
            requests = [explanation_request(explanation_packet(i['shared'], policy)[0], config, i['enum_ids']) for i in schedule if i['graph_variant'] == variant]
            request, bound = max(requests, key=lambda r: r[1])
            counts = []
            for scale, transcript in zip((1, 2), probes[2 * index:2 * index + 2]):
                expected = deepcopy(request)
                expected['options']['num_ctx'] *= scale
                if transcript['request'] != expected:
                    raise ValueError('context request mismatch')
                counts.append(checked_telemetry(transcript['response'], {**config['agent'], 'num_ctx': scale * config['agent']['num_ctx']}, bound))
            if counts[0] != counts[1] or counts[0] != summary['context_probe']['probes'][index]['prompt_eval_count']:
                raise ValueError('context counts mismatch')
    elif summary['agent_status'] not in ('prepared_no_llm', 'blocked_runtime_before_calls') or summary['study_calls_completed'] != 0:
        raise ValueError('study is neither prepared nor completed')
    audit = {'stage': 'explanation1_runtime_drift_archive_audit' if drift else ('explanation1_completed_audit' if completed else 'explanation1_prepared_audit'),
             'test_opened': False, 'model_calls': 0, 'planned_calls_verified': len(schedule),
             'real_agent_calls_verified': len(rows), 'accepted_calls_verified': sum(r['accepted'] for r in rows),
             'template_valid_count': sum(r['accepted'] for r in baselines),
             'fixed_bplus_choices_and_ranking_traces_verified': True, 'previous_studies_unchanged': True,
             'raw_draft_semantics_verified': False, 'rendering_is_controlled_not_free_text': True,
             'runtime_identity_verified': completed and not drift,
             'lock_c_authorized': False, 'summary_sha256': digest(OUTPUT), 'auditor_sha256': digest(Path(__file__))}
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_explanation1_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
