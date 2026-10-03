"""Exact-request replication after a runtime drift; frozen first study stays intact.

Execution contract copied from explanation1; strengthened runtime observations only.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import call_chat, digest, local_json, read_json, save
from scripts.run_foundational_rq2_explanation1 import prepare_explanation as parent_prepare, aggregate
from src.rq2.foundational_validation import checked_telemetry
from src.rq2.grounded_explanation import explanation_packet, explanation_request, run_explanation

CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_explanation1_replication.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/explanation1_replication'
OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_explanation1_replication_summary.json'
PARENT_OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_explanation1_summary.json'
PARENT_PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/explanation1'


def prepare_replication():
    trial = read_json(CONFIG)
    if trial['stage'] != 'validation_development_not_lock_c' or trial['test_access'] is not False:
        raise ValueError('VALIDATION replication only')
    parent = read_json(PARENT_OUTPUT)
    if parent['agent_status'] != 'completed_runtime_drift_not_validated':
        raise ValueError('preserved runtime-drift archive required')
    for relative, expected in parent['input_sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('parent study input changed')
    if digest(PARENT_PRIVATE / 'runs.json') != parent['private_runs_sha256']:
        raise ValueError('parent calls changed')
    config, policy, schedule, cohorts, pins, baselines = parent_prepare()
    config = {**config, 'version': trial['version'], 'expected_ollama_version': trial['expected_ollama_version']}
    if len(schedule) != trial['new_calls'] or schedule != read_json(PARENT_PRIVATE / 'schedule.json'):
        raise ValueError('replication schedule changed')
    prior_rows = read_json(PARENT_PRIVATE / 'runs.json')
    for item, row in zip(schedule, prior_rows):
        request, _ = explanation_request(explanation_packet(item['shared'], policy)[0], config, item['enum_ids'])
        if request != row['request']:
            raise ValueError('replication may not tune the failed study request')
    for path in (CONFIG, Path(__file__), PARENT_OUTPUT, PARENT_PRIVATE / 'runs.json',
                 ROOT / 'artifacts/tables/foundationalassist_v4_rq2_explanation1_audit.json'):
        pins[path.relative_to(ROOT).as_posix()] = digest(path)
    return config, policy, schedule, cohorts, pins, baselines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-agent', action='store_true')
    args = parser.parse_args()
    if (PRIVATE / 'runs.json').exists() or (PRIVATE / 'runs.partial.json').exists():
        raise ValueError('explanation calls exist; never overwrite or silently repeat')
    config, policy, schedule, cohorts, pins, baselines = prepare_replication()
    save(PRIVATE / 'schedule.json', schedule)
    save(PRIVATE / 'template_runs.json', baselines)
    variants = ['curriculum_edges', 'no_edges']
    summary = {'stage': config['stage'], 'test_opened': False, 'agent_status': 'prepared_no_llm',
               'version': config['version'], 'model': config['model'], 'model_digest': config['model_digest'],
               'claims': config['claims'], 'input_sha256': pins, 'study_calls_completed': 0,
               'new_calls_planned': len(schedule), 'schedule_sha256': digest(PRIVATE / 'schedule.json'),
               'template_runs_sha256': digest(PRIVATE / 'template_runs.json'),
               'template_checks_before_llm': {'calls': len(baselines), 'valid': sum(r['accepted'] for r in baselines)}}
    save(OUTPUT, summary)
    if not args.run_agent:
        print(json.dumps({'status': summary['agent_status'], 'planned_calls': len(schedule), 'valid_templates': len(baselines), 'model_calls': 0}))
        return
    try:
        version = local_json('version')['version']
        if version != config['expected_ollama_version']:
            raise ValueError('replication requires the declared runtime version')
        def verify_runtime():
            if local_json('version')['version'] != version or not any(m['name'] == config['model'] and m['digest'] == config['model_digest'] for m in local_json('tags')['models']):
                raise ValueError('pinned model/runtime required')
        verify_runtime()
        info = local_json('show', {'model': config['model']})['model_info']
        limits = [v for k, v in info.items() if k.endswith('.context_length')]
        if not limits or min(limits) < 2 * config['agent']['num_ctx']:
            raise ValueError('context comparison unsupported')
    except (OSError, ValueError, KeyError, TypeError) as error:
        summary.update(agent_status='blocked_runtime_before_calls', runtime_error_type=type(error).__name__, runtime_error_message=str(error))
        save(OUTPUT, summary)
        raise
    summary.update(agent_status='preflight', ollama_version=version)
    save(OUTPUT, summary)
    transcripts, probes = [], []
    for variant in variants:
        requests = [explanation_request(explanation_packet(r['shared'], policy)[0], config, r['enum_ids']) for r in schedule if r['graph_variant'] == variant]
        request, bound = max(requests, key=lambda r: r[1])
        counts = []
        for factor in (1, 2):
            probe = deepcopy(request)
            probe['options']['num_ctx'] *= factor
            try:
                response = call_chat(probe, timeout=config['agent']['timeout_seconds'])
                transcripts.append({'request': probe, 'response': response})
            except (OSError, ValueError, KeyError, TypeError) as error:
                transcripts.append({'request': probe, 'error_type': type(error).__name__, 'message': str(error)})
                raise
            finally:
                save(PRIVATE / 'preflight_calls.json', transcripts)
            verify_runtime()
            counts.append(checked_telemetry(response, {**config['agent'], 'num_ctx': factor * config['agent']['num_ctx']}, bound))
        if counts[0] != counts[1]:
            raise ValueError('explanation context counts differ')
        probes.append({'graph_variant': variant, 'prompt_eval_count': counts[0], 'double_context_prompt_eval_count': counts[1], 'byte_guard': bound})
    summary.update(agent_status='in_progress', context_probe={'probes': probes, 'probe_calls_not_study': 4})
    save(OUTPUT, summary)
    rows = []
    for item in schedule:
        verify_runtime()
        row = run_explanation(item['shared'], policy, config, item['enum_ids'], call_chat)
        row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
        row['observed_runtime_version_before_call'] = version
        row['observed_runtime_version_after_call'] = local_json('version')['version']
        rows.append(row)
        save(PRIVATE / 'runs.partial.json', rows)
        verify_runtime()
        if len(rows) % 12 == 0:
            print(json.dumps({'completed': len(rows), 'total': len(schedule), 'test_opened': False}), flush=True)
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('input or previous study changed')
    verify_runtime()
    save(PRIVATE / 'runs.json', rows)
    summary.update(agent_status='completed_validation_not_test',
                   cohorts=aggregate(rows, baselines, cohorts, variants),
                   private_runs_sha256=digest(PRIVATE / 'runs.json'), previous_studies_unchanged=True,
                   runtime_identity_unchanged=True, raw_drafts_semantically_verified=False, study_calls_completed=len(rows))
    save(OUTPUT, summary)
    print(json.dumps({'status': summary['agent_status'], 'new_calls': len(rows)}))


if __name__ == '__main__':
    main()
