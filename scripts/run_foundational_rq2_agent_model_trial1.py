"""One resource-bounded model comparison on the frozen revision1 schedule."""

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import call_chat, digest, local_json, read_json, save
from scripts.run_foundational_rq2_agent_revision1 import prepare
from src.rq2.agent_revision import revision_request, run_revision_call
from src.rq2.foundational_validation import checked_telemetry, summarize_operational

CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_agent_model_trial1.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_model_trial1'
OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_model_trial1_summary.json'


def main():
    if (PRIVATE / 'runs.json').exists():
        raise ValueError('completed model trial exists; never overwrite')
    trial = read_json(CONFIG)
    if trial['stage'] != 'validation_development_not_lock_c' or trial['test_access'] is not False:
        raise ValueError('VALIDATION development only')
    _, config, original_schedule, cohorts, pins = prepare()
    original_summary = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_revision1_summary.json'
    if read_json(original_summary)['agent_status'] != 'completed_validation_not_test':
        raise ValueError('completed revision1 comparison required')
    config['agent'] = {**config['agent'], 'model': trial['model']}
    schedule = [r for r in original_schedule if r['arm'] == 'schema_and_objective']
    if len(schedule) != trial['new_calls']:
        raise ValueError('fixed model-trial call count mismatch')
    revision_runs = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_revision1/runs.json'
    for path in (CONFIG, Path(__file__), original_summary, revision_runs):
        pins[path.relative_to(ROOT).as_posix()] = digest(path)
    models = local_json('tags')['models']
    version = local_json('version')['version']
    if not any(m['name'] == trial['model'] and m['digest'] == trial['model_digest'] for m in models):
        raise ValueError('pinned model must already be installed')
    show = local_json('show', {'model': trial['model']})
    limits = [v for k, v in show.get('model_info', {}).items() if k.endswith('.context_length')]
    if not limits or min(limits) < 2 * config['agent']['num_ctx']:
        raise ValueError('model context cannot support the feasibility comparison')
    save(PRIVATE / 'schedule.json', schedule)
    summary = {'stage': trial['stage'], 'test_opened': False, 'agent_status': 'preflight',
               'version': trial['version'], 'model': trial['model'], 'model_digest': trial['model_digest'],
               'ollama_version': version, 'input_sha256': pins, 'new_calls_planned': len(schedule),
               'claims': trial['claims'], 'schedule_sha256': digest(PRIVATE / 'schedule.json')}
    save(OUTPUT, summary)
    probes, transcripts = [], []
    for variant in config['graph_variants']:
        requests = [revision_request(r['shared'], config, r['arm'], r['enum_ids']) for r in schedule if r['graph_variant'] == variant]
        request, bound = max(requests, key=lambda pair: pair[1])
        counts = []
        for factor in (1, 2):
            probe_request = deepcopy(request)
            probe_request['options']['num_ctx'] *= factor
            response = call_chat(probe_request, timeout=config['agent']['timeout_seconds'])
            transcripts.append({'request': probe_request, 'response': response})
            save(PRIVATE / 'preflight_calls.json', transcripts)
            runtime = {**config['agent'], 'num_ctx': factor * config['agent']['num_ctx']}
            counts.append(checked_telemetry(response, runtime, bound))
        if counts[0] != counts[1]:
            raise ValueError('model-trial context token counts differ')
        probes.append({'graph_variant': variant, 'prompt_eval_count': counts[0],
                       'double_context_prompt_eval_count': counts[1], 'byte_guard': bound})
    summary.update(agent_status='in_progress', context_verified=True,
                   context_probe={'probes': probes, 'probe_calls_not_study': 4})
    save(OUTPUT, summary)
    records = []
    for item in schedule:
        row = run_revision_call(item['shared'], config, item['arm'], item['enum_ids'], call_chat)
        row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
        row['policy'] = 'Agent_model_trial1'
        records.append(row)
        save(PRIVATE / 'runs.partial.json', records)
        if len(records) % 12 == 0:
            print(json.dumps({'completed': len(records), 'total': len(schedule), 'test_opened': False}), flush=True)
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('trial input or previous study changed')
    models = local_json('tags')['models']
    if local_json('version')['version'] != version or not any(m['name'] == trial['model'] and m['digest'] == trial['model_digest'] for m in models):
        raise ValueError('runtime/model changed during trial')
    save(PRIVATE / 'runs.json', records)
    before = read_json(revision_runs)
    comparisons = {}
    for cohort, source in cohorts.items():
        rows = [r for r in before + records if r['cohort'] == cohort]
        comparisons[cohort] = {'n_students': source['n_students'],
                               'policies': summarize_operational(source['legacy_records'] + rows)['policies']}
    summary.update(agent_status='completed_validation_not_test', cohorts=comparisons,
                   private_runs_sha256=digest(PRIVATE / 'runs.json'),
                   previous_studies_unchanged=True, runtime_identity_unchanged=True)
    save(OUTPUT, summary)
    print(json.dumps({'status': summary['agent_status'], 'new_calls': len(records)}))


if __name__ == '__main__':
    main()
