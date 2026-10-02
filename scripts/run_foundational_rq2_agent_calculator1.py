"""One predeclared calculator intervention on the frozen VALIDATION schedule."""

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import call_chat, digest, local_json, read_json, save
from scripts.run_foundational_rq2_agent_revision1 import prepare
from src.rq2.calculator_agent import candidate_evidence, calculator_request, recommend_calculator_bplus, run_calculator_call
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus, summarize_operational

CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_agent_calculator1.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_calculator1'
OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_calculator1_summary.json'
PREVIOUS_PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_model_trial1'
PREVIOUS_OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_model_trial1_summary.json'


def prepare_calculator():
    trial = read_json(CONFIG)
    if trial['stage'] != 'validation_development_not_lock_c' or trial['test_access'] is not False:
        raise ValueError('VALIDATION development only')
    previous = read_json(PREVIOUS_OUTPUT)
    if previous['agent_status'] != 'completed_validation_not_test' or previous['test_opened'] is not False:
        raise ValueError('completed previous VALIDATION comparison required')
    for relative, expected in previous['input_sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('previous study input changed')
    if digest(PREVIOUS_PRIVATE / 'runs.json') != previous['private_runs_sha256']:
        raise ValueError('previous calls changed')
    if trial['model'] != previous['model'] or trial['model_digest'] != previous['model_digest']:
        raise ValueError('calculator trial must keep previous model')
    _, config, original, cohorts, pins = prepare()
    config['agent'] = {**config['agent'], 'model': trial['model']}
    schedule = [r for r in original if r['arm'] == 'schema_and_objective']
    if schedule != read_json(PREVIOUS_PRIVATE / 'schedule.json') or len(schedule) != trial['new_calls']:
        raise ValueError('same previous schedule and bounded count required')
    for item in schedule:
        evidence = candidate_evidence(item['shared'], config['bplus'])
        if recommend_calculator_bplus(item['shared'], config['bplus'], evidence) != recommend_foundational_bplus(item['shared'], config['bplus']):
            raise ValueError('shared calculator changed B+ ordering')
        calculator_request(item['shared'], config, item['enum_ids'])
    pins.update(previous['input_sha256'])
    for path in (CONFIG, Path(__file__), ROOT / 'src/rq2/calculator_agent.py', PREVIOUS_OUTPUT,
                 PREVIOUS_PRIVATE / 'schedule.json', PREVIOUS_PRIVATE / 'runs.json'):
        pins[path.relative_to(ROOT).as_posix()] = digest(path)
    return trial, config, schedule, cohorts, pins


def comparisons(records, cohorts):
    before = read_json(ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_revision1/runs.json')
    model_before = read_json(PREVIOUS_PRIVATE / 'runs.json')
    return {cohort: {'n_students': source['n_students'],
                    'policies': summarize_operational(source['legacy_records'] + [r for r in before + model_before + records if r['cohort'] == cohort])['policies']}
            for cohort, source in cohorts.items()}


def main():
    if (PRIVATE / 'runs.json').exists() or (PRIVATE / 'runs.partial.json').exists():
        raise ValueError('calculator calls already exist; never overwrite or silently repeat')
    trial, config, schedule, cohorts, pins = prepare_calculator()
    version = local_json('version')['version']
    def verify_identity():
        if local_json('version')['version'] != version or not any(m['name'] == trial['model'] and m['digest'] == trial['model_digest'] for m in local_json('tags')['models']):
            raise ValueError('pinned runtime/model identity required')
    verify_identity()
    show = local_json('show', {'model': trial['model']})
    limits = [v for k, v in show.get('model_info', {}).items() if k.endswith('.context_length')]
    if not limits or min(limits) < 2 * config['agent']['num_ctx']:
        raise ValueError('model cannot support context comparison')
    save(PRIVATE / 'schedule.json', schedule)
    summary = {'stage': trial['stage'], 'test_opened': False, 'agent_status': 'preflight',
               'version': trial['version'], 'model': trial['model'], 'model_digest': trial['model_digest'],
               'ollama_version': version, 'input_sha256': pins, 'new_calls_planned': len(schedule),
               'claims': trial['claims'], 'schedule_sha256': digest(PRIVATE / 'schedule.json'),
               'shared_evidence_bplus_parity_checked': len(schedule)}
    save(OUTPUT, summary)
    probes, transcripts = [], []
    for variant in config['graph_variants']:
        requests = [calculator_request(r['shared'], config, r['enum_ids']) for r in schedule if r['graph_variant'] == variant]
        request, bound = max(requests, key=lambda pair: pair[1])
        counts = []
        for factor in (1, 2):
            probe_request = deepcopy(request)
            probe_request['options']['num_ctx'] *= factor
            try:
                response = call_chat(probe_request, timeout=config['agent']['timeout_seconds'])
                transcripts.append({'request': probe_request, 'response': response})
            except (OSError, ValueError, KeyError, TypeError) as error:
                transcripts.append({'request': probe_request, 'error_type': type(error).__name__, 'message': str(error)})
                raise
            finally:
                save(PRIVATE / 'preflight_calls.json', transcripts)
            counts.append(checked_telemetry(response, {**config['agent'], 'num_ctx': factor * config['agent']['num_ctx']}, bound))
        if counts[0] != counts[1]:
            raise ValueError('calculator context token counts differ')
        probes.append({'graph_variant': variant, 'prompt_eval_count': counts[0],
                       'double_context_prompt_eval_count': counts[1], 'byte_guard': bound})
    summary.update(agent_status='in_progress', context_probe={'probes': probes, 'probe_calls_not_study': 4})
    save(OUTPUT, summary)
    records = []
    for item in schedule:
        row = run_calculator_call(item['shared'], config, item['enum_ids'], call_chat)
        row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
        records.append(row)
        save(PRIVATE / 'runs.partial.json', records)
        if len(records) % 12 == 0:
            print(json.dumps({'completed': len(records), 'total': len(schedule), 'test_opened': False}), flush=True)
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('calculator or previous study inputs changed')
    verify_identity()
    save(PRIVATE / 'runs.json', records)
    summary.update(agent_status='completed_validation_not_test', cohorts=comparisons(records, cohorts),
                   private_runs_sha256=digest(PRIVATE / 'runs.json'),
                   previous_studies_unchanged=True, runtime_identity_unchanged=True)
    save(OUTPUT, summary)
    print(json.dumps({'status': summary['agent_status'], 'new_calls': len(records)}))


if __name__ == '__main__':
    main()
