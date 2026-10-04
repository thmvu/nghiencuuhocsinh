"""Read-only reconstruction of completed selection v2; no inference calls."""

from copy import deepcopy
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_selection_v2 import (
    OUTPUT, PRIVATE, aggregate, baseline_rows, call_accounting, prepare_selection,
    enrich_selection, selection_request, run_selection, checked_telemetry, digest, read_json, save)


def json_value(value):
    # JSON object position keys are strings; match the persisted representation.
    return json.loads(json.dumps(value, allow_nan=False))


def main():
    summary = read_json(OUTPUT)
    if summary['agent_status'] != 'completed_validation_not_test' or summary['test_opened'] is not False:
        raise ValueError('completed VALIDATION batch required')
    config, old, schedule, cohorts, pins = prepare_selection()
    if pins != summary['input_sha256'] or schedule != read_json(PRIVATE / 'schedule.json'):
        raise ValueError('input pins or schedule changed')
    for filename, field in (('schedule.json', 'schedule_sha256'), ('baseline_reference.json', 'baseline_reference_sha256'),
                            ('baseline_runs.json', 'baseline_runs_sha256'), ('runs.json', 'private_runs_sha256'),
                            ('calls.jsonl', 'journal_sha256')):
        if digest(PRIVATE / filename) != summary[field]:
            raise ValueError('private artifact hash changed: ' + filename)
    rows = read_json(PRIVATE / 'runs.json')
    if len(rows) != len(schedule) or rows != read_json(PRIVATE / 'runs.partial.json'):
        raise ValueError('study rows incomplete or partial/final mismatch')
    baselines = read_json(PRIVATE / 'baseline_runs.json')
    replayed = baseline_rows(schedule, old, cohorts)
    for policy, recorded in baselines.items():
        expected = replayed[policy]
        if [{k: v for k, v in r.items() if k != 'latency_seconds'} for r in recorded] != [
                {k: v for k, v in r.items() if k != 'latency_seconds'} for r in expected]:
            raise ValueError('baseline replay mismatch')
        if json_value(aggregate(recorded, schedule, cohorts)) != summary['baseline_metrics'][policy]:
            raise ValueError('baseline metrics mismatch')
    events = [json.loads(line) for line in (PRIVATE / 'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    accounting = call_accounting(PRIVATE / 'calls.jsonl')
    if accounting != summary['call_accounting'] or accounting['probe']['transport_calls'] != 4 or accounting['study']['transport_calls'] != len(schedule):
        raise ValueError('call accounting mismatch')
    expected_identity = {'ollama_version': config['expected_ollama_version'], 'model': config['agent']['model'], 'model_digest': config['model_digest']}
    observations = [e for e in events if e['event'] == 'runtime_observed']
    if any(e['identity'] != expected_identity for e in observations) or len(observations) != 2 * (4 + len(schedule)) + 1:
        raise ValueError('runtime observations incomplete or changed')
    if observations[-1]['phase'] != 'end_gate':
        raise ValueError('missing final runtime gate')
    def event(index, kind):
        found = [e for e in events if e['call_index'] == index and e['event'] == kind]
        if len(found) != 1:
            raise ValueError('missing or repeated journal event: ' + kind)
        return found[0]
    for variant_index, variant in enumerate(('curriculum_edges', 'no_edges')):
        request, bound = max((selection_request(i['shared'], config, i['enum_ids']) for i in schedule if i['graph_variant'] == variant), key=lambda pair: pair[1])
        counts = []
        for scale in (1, 2):
            index = 2 * variant_index + scale
            expected_request = deepcopy(request)
            expected_request['options']['num_ctx'] *= scale
            if event(index, 'call_scope')['scope'] != 'probe' or event(index, 'request_started')['request'] != expected_request:
                raise ValueError('context probe request mismatch')
            response = event(index, 'response_received')['raw_response']
            counts.append(checked_telemetry(response, {**config['agent'], 'num_ctx': scale * config['agent']['num_ctx']}, bound))
        probe = summary['context_probes'][variant_index]
        if counts != [probe['prompt_eval_count'], probe['double_context_prompt_eval_count']] or counts[0] != counts[1]:
            raise ValueError('context probe token mismatch')
    for index, (item, recorded) in enumerate(zip(schedule, rows), start=5):
        request, _ = selection_request(item['shared'], config, item['enum_ids'])
        if event(index, 'call_scope')['scope'] != 'study' or event(index, 'request_started')['request'] != request or recorded['journal_call_index'] != index:
            raise ValueError('study request/index mismatch')
        if recorded['request'] != request or not math.isfinite(recorded['latency_seconds']) or recorded['latency_seconds'] < 0:
            raise ValueError('recorded request or latency invalid')
        call_events = [e for e in events if e['call_index'] == index and e.get('phase') != 'end_gate']
        phases = [e['phase'] for e in call_events if e['event'] == 'runtime_observed']
        expected_phase = 'after_transport_failure' if recorded['raw_response'] is None else 'after_call'
        if phases != ['before_call', expected_phase]:
            raise ValueError('per-call runtime observation mismatch')
        if recorded['raw_response'] is None:
            failure = event(index, 'transport_failed')
            if recorded['candidate_valid'] or recorded['error_stage'] != 'transport' or recorded['error_type'] != failure['error_type'] or recorded['error_message'] != failure['error_message']:
                raise ValueError('transport failure mismatch')
            expected = deepcopy(recorded)
        else:
            response = event(index, 'response_received')['raw_response']
            if response != recorded['raw_response']:
                raise ValueError('raw response mismatch')
            if next(i for i, e in enumerate(call_events) if e['event'] == 'response_received') >= next(
                    i for i, e in enumerate(call_events) if e.get('phase') == 'after_call'):
                raise ValueError('response was not logged before post-call runtime check')
            expected = run_selection(item['shared'], config, item['enum_ids'], lambda request, timeout: response)
        enrich_selection(expected, item, old)
        expected['journal_call_index'] = index
        if {k: v for k, v in expected.items() if k != 'latency_seconds'} != {k: v for k, v in recorded.items() if k != 'latency_seconds'}:
            raise ValueError('reconstructed study result mismatch')
    if json_value(aggregate(rows, schedule, cohorts)) != summary['cohorts'] or summary['model_calls_completed'] != accounting['study']['responses_received']:
        raise ValueError('study metrics mismatch')
    result = {'stage': 'selection_v2_completed_validation_audit', 'test_opened': False, 'new_model_calls': 0,
              'study_calls_verified': len(rows), 'valid_selections_verified': sum(r['candidate_valid'] for r in rows),
              'call_accounting_verified': accounting, 'inputs_requests_responses_metrics_verified': True,
              'baseline_replay_verified': True, 'runtime_identity_verified': True,
              'reason_semantically_verified': False, 'lock_c_authorized': False,
              'summary_sha256': digest(OUTPUT), 'auditor_sha256': digest(Path(__file__))}
    save(ROOT / 'artifacts/tables/foundationalassist_v4_rq2_selection_v2_audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
