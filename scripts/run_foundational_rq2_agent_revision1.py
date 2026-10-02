"""Bounded paired Agent repair experiment; keep the legacy run untouched."""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import call_chat, digest, local_json, read_json, save
from src.rq2.agent_revision import revision_request, run_revision_call
from src.rq2.foundational_validation import checked_telemetry, compact_graph, shared_repetitions, summarize_operational

CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_agent_revision1.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/agent_revision1'
OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_agent_revision1_summary.json'


def prepare():
    revision = read_json(CONFIG)
    if revision['stage'] != 'validation_development_not_lock_c' or revision['test_access'] is not False:
        raise ValueError('VALIDATION development only')
    if revision['arms'] != ['schema_only', 'schema_and_objective']:
        raise ValueError('fixed two-arm design required')
    base_path = ROOT / revision['base_config']
    if digest(base_path) != revision['base_config_sha256']:
        raise ValueError('original config changed')
    base = read_json(base_path)
    if base['stage'] != 'validation_development_not_lock_c' or base['test_access'] is not False:
        raise ValueError('original VALIDATION config required')
    graph_path = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_curriculum_graph.json'
    graph = read_json(graph_path)
    config = {**base, 'reason_max_chars': revision['reason_max_chars'],
              'reference_graph': compact_graph(graph, 'curriculum_edges')}
    pins = {p.relative_to(ROOT).as_posix(): digest(p) for p in (
        CONFIG, base_path, graph_path, Path(__file__), ROOT / 'src/rq2/agent_revision.py')}
    cohorts, schedule = {}, []
    for cohort_index, cohort in enumerate(('representative', 'challenge')):
        legacy_path = ROOT / f'artifacts/tables/foundationalassist_v4_rq2_{"validation" if cohort_index == 0 else "challenge"}_summary.json'
        legacy = read_json(legacy_path)
        if legacy['agent_status'] != 'validation_run_completed_not_test' or legacy['test_opened'] is not False:
            raise ValueError('completed legacy VALIDATION run required')
        for relative, expected in legacy['input_sha256'].items():
            if digest(ROOT / relative) != expected:
                raise ValueError('original study inputs changed')
            pins[relative] = expected
        private = ROOT / 'data/processed/foundationalassist_v4/rq2_validation'
        if cohort_index:
            private /= 'challenge'
        cases_path = private / 'scenarios.json'
        if digest(cases_path) != legacy['scenarios_sha256']:
            raise ValueError('original scenarios changed')
        cases = read_json(cases_path)
        rng = np.random.default_rng(np.random.SeedSequence([revision['subset_seed'], cohort_index]))
        chosen_indices = sorted(rng.choice(len(cases), size=revision['cases_per_cohort'], replace=False).tolist())
        chosen = {cases[i]['scenario_id'] for i in chosen_indices}
        source_rows = []
        for filename in ('deterministic_runs.json', 'agent_runs.json'):
            path = private / filename
            pins[path.relative_to(ROOT).as_posix()] = digest(path)
            for row in read_json(path):
                if row['scenario_id'] in chosen:
                    source_rows.append({**row, 'policy': 'Agent_legacy' if row['policy'] == 'Agent' else row['policy']})
        pins[cases_path.relative_to(ROOT).as_posix()] = digest(cases_path)
        pins[legacy_path.relative_to(ROOT).as_posix()] = digest(legacy_path)
        indices = {case['scenario_id']: i for i, case in enumerate(cases)}
        for case, rep, variant, order, _, shared in shared_repetitions(cases, graph, base):
            if case['scenario_id'] not in chosen:
                continue
            seed = np.random.SeedSequence([revision['enum_seed'], cohort_index, indices[case['scenario_id']], rep])
            enum_rng, arm_rng = [np.random.default_rng(s) for s in seed.spawn(2)]
            ids = sorted(c['problem_id'] for c in shared['candidates'])
            enum_ids = [ids[int(i)] for i in enum_rng.permutation(len(ids))]
            for arm_index in arm_rng.permutation(len(revision['arms'])):
                schedule.append({'cohort': cohort, 'scenario_id': case['scenario_id'],
                                 'student_id': case['student_id'], 'repetition': rep,
                                 'graph_variant': variant, 'permutation': order,
                                 'arm': revision['arms'][int(arm_index)], 'enum_ids': enum_ids,
                                 'shared': shared})
        cohorts[cohort] = {'n_students': len(chosen), 'legacy_records': source_rows,
                           'legacy_probe': legacy['context_probe']}
    if len(schedule) != revision['new_calls']:
        raise ValueError('bounded call count mismatch')
    return revision, config, schedule, cohorts, pins


def context_probe(schedule, config, cohorts):
    runtime = config['agent']
    models = local_json('tags')['models']
    version = local_json('version')['version']
    match = [m for m in models if m['name'] == runtime['model']]
    if len(match) != 1:
        raise ValueError('configured installed model required')
    if any(c['legacy_probe']['model_digest'] != match[0]['digest'] or c['legacy_probe']['ollama_version'] != version for c in cohorts.values()):
        raise ValueError('same runtime/model as original study required')
    probes = []
    transcripts = []
    def invoke(request):
        try:
            response = call_chat(request, timeout=runtime['timeout_seconds'])
            transcripts.append({'request': request, 'response': response})
            return response
        except (OSError, ValueError, KeyError, TypeError) as error:
            transcripts.append({'request': request, 'error_type': type(error).__name__, 'message': str(error)})
            raise
        finally:
            save(PRIVATE / 'preflight_calls.partial.json', transcripts)
    for arm in ('schema_only', 'schema_and_objective'):
        for variant in config['graph_variants']:
            requests = [revision_request(r['shared'], config, arm, r['enum_ids']) for r in schedule if r['arm'] == arm and r['graph_variant'] == variant]
            request, bound = max(requests, key=lambda pair: pair[1])
            first = invoke(request)
            count = checked_telemetry(first, runtime, bound)
            larger = deepcopy(request)
            larger['options']['num_ctx'] *= 2
            count2 = checked_telemetry(invoke(larger),
                                       {**runtime, 'num_ctx': 2 * runtime['num_ctx']}, bound)
            if count != count2:
                raise ValueError('context probe token counts differ')
            probes.append({'arm': arm, 'graph_variant': variant, 'prompt_eval_count': count,
                           'double_context_prompt_eval_count': count2, 'byte_guard': bound})
    return {'verified': True, 'model_digest': match[0]['digest'], 'ollama_version': version,
            'probe_calls_not_study': 8, 'probes': probes}


def aggregate(records, cohorts):
    result = {}
    for cohort, source in cohorts.items():
        rows = [r for r in records if r['cohort'] == cohort]
        policies = summarize_operational(source['legacy_records'] + rows)['policies']
        for name in ('Agent_schema_only', 'Agent_schema_and_objective'):
            for variant, metric in policies[name]['variants'].items():
                group = [r for r in rows if r['policy'] == name and r['graph_variant'] == variant]
                valid = [r for r in group if r['candidate_valid']]
                metric['first_display_position_rate_among_valid_calls'] = sum(r['selected_position'] == 0 for r in valid) / len(valid) if valid else None
                metric['enum_position_counts_valid'] = dict(sorted(Counter(r['selected_enum_position'] for r in valid).items()))
                metric['first_enum_position_rate_among_valid_calls'] = sum(r['selected_enum_position'] == 0 for r in valid) / len(valid) if valid else None
                metric['error_stage_counts'] = dict(Counter(r['error_stage'] for r in group if r['error_stage']))
        result[cohort] = {'n_students': source['n_students'], 'policies': policies}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-agent', action='store_true')
    args = parser.parse_args()
    if (PRIVATE / 'runs.json').exists():
        raise ValueError('completed revision run exists; never overwrite it')
    revision, config, schedule, cohorts, pins = prepare()
    summary = {'stage': revision['stage'], 'test_opened': False, 'agent_status': 'prepared',
               'version': revision['version'], 'input_sha256': pins, 'new_calls_planned': len(schedule),
               'claims': revision['metrics_before_run']['claims']}
    save(PRIVATE / 'schedule.json', schedule)
    summary['schedule_sha256'] = digest(PRIVATE / 'schedule.json')
    save(OUTPUT, summary)
    if not args.run_agent:
        print(json.dumps({'status': 'prepared', 'new_calls': len(schedule)}))
        return
    try:
        probe = context_probe(schedule, config, cohorts)
    except (OSError, ValueError, KeyError, TypeError) as error:
        save(PRIVATE / 'preflight_failure.json', {'type': type(error).__name__, 'message': str(error)})
        summary['agent_status'] = 'blocked_context_preflight'
        save(OUTPUT, summary)
        raise
    save(PRIVATE / 'context_probe.json', probe)
    summary.update(agent_status='in_progress', context_probe=probe)
    save(OUTPUT, summary)
    records = []
    for item in schedule:
        row = run_revision_call(item['shared'], config, item['arm'], item['enum_ids'], call_chat)
        row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
        records.append(row)
        save(PRIVATE / 'runs.partial.json', records)
        if len(records) % 12 == 0 or len(records) == len(schedule):
            print(json.dumps({'completed': len(records), 'total': len(schedule), 'test_opened': False}), flush=True)
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('input or archived study changed during revision')
    models = local_json('tags')['models']
    if local_json('version')['version'] != probe['ollama_version'] or not any(m['name'] == config['agent']['model'] and m['digest'] == probe['model_digest'] for m in models):
        raise ValueError('runtime/model changed during revision')
    save(PRIVATE / 'runs.json', records)
    summary.update(agent_status='completed_validation_not_test', cohorts=aggregate(records, cohorts),
                   private_runs_sha256=digest(PRIVATE / 'runs.json'),
                   original_inputs_unchanged=True, runtime_identity_unchanged=True)
    save(OUTPUT, summary)
    print(json.dumps({'status': summary['agent_status'], 'new_calls': len(records)}))


if __name__ == '__main__':
    main()
