"""Reconstruct v3 diagnostic/study outputs from frozen requests and responses."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_foundational_rq2_selection_v3 import (
    PRIVATE, DIAGNOSTIC_CONFIG, FINAL_CONFIG, output, read_json, digest, save, verify_pins,
    diagnostic_inputs, study_inputs, accounting, selection_request, run_selection,
    enrich_selection, aggregate, choose_contract, flag_rates, rubric_packet, stop_decision, checked_telemetry)


def persisted(value):
    return json.loads(json.dumps(value, allow_nan=False))


def without_latency(row):
    return {k: v for k, v in row.items() if k != 'latency_seconds'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('diagnostic', 'study'))
    phase = parser.parse_args().phase
    summary = read_json(output(phase))
    if summary['status'] != 'completed_validation_not_test' or summary['test_opened'] is not False:
        raise ValueError('completed VALIDATION batch required')
    verify_pins(summary['input_sha256'])
    directory = PRIVATE / phase
    config = read_json(DIAGNOSTIC_CONFIG if phase == 'diagnostic' else FINAL_CONFIG)
    if phase == 'diagnostic':
        old, schedule, pins = diagnostic_inputs(config)
        repeats = []
    else:
        old, cases, schedule, repeats, regenerated_baselines, pins, info = study_inputs(config)
        if info != summary['cohort']:
            raise ValueError('cohort/coverage changed')
        prepared = read_json(output('preparation'))
        if digest(directory / 'scenarios.json') != prepared['scenario_sha256'] or read_json(directory / 'scenarios.json') != cases:
            raise ValueError('scenario hash/reconstruction mismatch')
        for filename, key in [('repeat_schedule.json', 'repeat_schedule_sha256'), ('baseline_runs.json', 'baseline_runs_sha256'),
                              ('repeat_runs.json', 'repeat_runs_sha256'), ('rubric_packet.json', 'rubric_packet_sha256')]:
            if digest(directory / filename) != summary[key]:
                raise ValueError('study artifact changed: ' + filename)
        if read_json(directory / 'repeat_schedule.json') != repeats:
            raise ValueError('repeat schedule changed')
        baselines = read_json(directory / 'baseline_runs.json')
        for policy, records in baselines.items():
            if [without_latency(r) for r in records] != [without_latency(r) for r in regenerated_baselines[policy]]:
                raise ValueError('baseline replay differs')
            if persisted(aggregate(records, schedule, {'representative': {}})) != summary['baselines'][policy]:
                raise ValueError('baseline metrics differ')
    if pins != summary['input_sha256'] or schedule != read_json(directory / 'schedule.json'):
        raise ValueError('source pins or schedule changed')
    for filename, key in [('schedule.json', 'schedule_sha256'), ('runs.json', 'runs_sha256'), ('calls.jsonl', 'journal_sha256')]:
        if digest(directory / filename) != summary[key]:
            raise ValueError('artifact hash changed: ' + filename)
    rows = read_json(directory / 'runs.json')
    if len(rows) != len(schedule) or read_json(directory / 'runs.partial.json') != rows:
        raise ValueError('incomplete study records')
    events = [json.loads(line) for line in (directory / 'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    counts = accounting(directory / 'calls.jsonl')
    expected_counts = {'contract_360': 24, 'contract_600': 24} if phase == 'diagnostic' else {'probe': 4, 'study': 240, 'repeat': 36}
    if counts != summary['call_accounting'] or any(counts[k]['attempts'] != n or counts[k]['transport'] != n for k, n in expected_counts.items()):
        raise ValueError('call accounting mismatch')
    identity = {'ollama_version': config['expected_ollama_version'], 'model': config['agent']['model'], 'model_digest': config['model_digest']}
    observations = [e for e in events if e['event'] == 'runtime_observed']
    if len(observations) != 2 * sum(expected_counts.values()) + 1 or any(e['identity'] != identity for e in observations) or observations[-1]['phase'] != 'end_gate':
        raise ValueError('runtime observations changed/incomplete')
    def event(index, kind):
        group = [e for e in events if e['call_index'] == index and e['event'] == kind]
        if len(group) != 1:
            raise ValueError('missing/repeated event: ' + kind)
        return group[0]
    if phase == 'study':
        for variant_index, variant in enumerate(('curriculum_edges', 'no_edges')):
            request, bound = max((selection_request(i['shared'], config, i['enum_ids']) for i in schedule if i['graph_variant'] == variant), key=lambda pair: pair[1])
            token_counts = []
            for scale in (1, 2):
                index = 2 * variant_index + scale
                expected = deepcopy(request)
                expected['options']['num_ctx'] *= scale
                if event(index, 'request_started')['request'] != expected:
                    raise ValueError('probe request differs')
                token_counts.append(checked_telemetry(event(index, 'response_received')['raw_response'],
                                                     {**config['agent'], 'num_ctx': config['agent']['num_ctx'] * scale}, bound))
            probe = summary['context_probes'][variant_index]
            if token_counts != [probe['prompt_eval_count'], probe['double_context_prompt_eval_count']] or token_counts[0] != token_counts[1]:
                raise ValueError('probe tokens differ')
    repeated = read_json(directory / 'repeat_runs.json') if phase == 'study' else []
    if len(repeated) != len(repeats):
        raise ValueError('incomplete repeat records')
    if phase == 'study' and read_json(directory / 'repeat_runs.partial.json') != repeated:
        raise ValueError('repeat partial/final mismatch')
    items = schedule + repeats
    records = rows + repeated
    offset = 1 if phase == 'diagnostic' else 5
    for index, (item, recorded) in enumerate(zip(items, records), start=offset):
        cfg = {**config, 'reason_max_chars': item.get('cap', config['reason_max_chars'])}
        request, _ = selection_request(item['shared'], cfg, item['enum_ids'])
        if event(index, 'request_started')['request'] != request or event(index, 'call_scope')['scope'] != item['scope'] or recorded['request'] != request:
            raise ValueError('request/scope mismatch')
        if recorded['raw_response'] is None:
            failure = event(index, 'transport_failed')
            if recorded['error_stage'] != 'transport' or recorded['candidate_valid'] or recorded['error_message'] != failure['error_message']:
                raise ValueError('transport error mismatch')
            expected = deepcopy(recorded)
        else:
            response = event(index, 'response_received')['raw_response']
            if response != recorded['raw_response']:
                raise ValueError('raw response differs')
            expected = run_selection(item['shared'], cfg, item['enum_ids'], lambda request, timeout: response)
        if phase == 'diagnostic':
            expected['cap'] = item['cap']
        elif item['scope'] == 'study':
            enrich_selection(expected, item, old)
        else:
            expected.update(original_study_index=item['original_study_index'], repeat_index=item['repeat_index'])
            if request != rows[item['original_study_index']]['request']:
                raise ValueError('identical-request repeat differs')
        expected['journal_call_index'] = index
        if without_latency(expected) != without_latency(recorded):
            raise ValueError('reconstructed result differs')
    if phase == 'diagnostic':
        if choose_contract(rows) != summary['contract_decision']:
            raise ValueError('contract decision differs')
    else:
        packet = read_json(directory / 'rubric_packet.json')
        metric = aggregate(rows, schedule, {'representative': {}})
        if rubric_packet(rows, config) != packet or persisted(metric) != summary['metrics'] or flag_rates(rows, 240) != summary['rationale_flags']:
            raise ValueError('rubric sample, metrics or flags differ')
        if stop_decision(rows, metric, packet) != summary['stop_decision']:
            raise ValueError('stop decision differs')
        stable = sum(all(r['candidate_valid'] for r in ([rows[i]] + [r for r in repeated if r['original_study_index'] == i]))
                     and len({r['selected_problem_id'] for r in ([rows[i]] + [r for r in repeated if r['original_study_index'] == i])}) == 1
                     for i in sorted({r['original_study_index'] for r in repeated}))
        if stable != summary['identical_request_reference']['valid_id_stable_four_calls']:
            raise ValueError('repeat stability differs')
    result = {'phase': phase, 'test_opened': False, 'new_model_calls': 0, 'call_accounting_verified': counts,
              'requests_responses_hashes_metrics_verified': True, 'runtime_identity_verified': True,
              'stop_or_contract_decision_verified': True, 'reason_semantically_verified': False, 'lock_c_authorized': False,
              'summary_sha256': digest(output(phase)), 'auditor_sha256': digest(Path(__file__))}
    save(output(phase + '_audit'), result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
