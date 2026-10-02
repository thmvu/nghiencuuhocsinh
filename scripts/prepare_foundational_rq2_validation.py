"""Prepare v4 VALIDATION inputs; optional local context probe and Agent run."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.rq2.candidates import build_foundational_metadata_pool
from src.rq2.curriculum_graph import build_foundational_curriculum_graph
from src.rq2.foundational_validation import (
    build_foundational_cases, build_observed_link_challenge, case_coverage, checked_telemetry, make_agent_request,
    run_agent, run_deterministic, shared_repetitions, summarize_operational,
)

PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation'
CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_validation.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def load_pinned_inputs():
    config = read_json(CONFIG)
    if config['stage'] != 'validation_development_not_lock_c' or config['test_access'] is not False:
        raise ValueError('TEST remains closed')
    lock_path = ROOT / 'configs/foundationalassist_v4_rq1_final.json'
    lock = read_json(lock_path)
    cleaning_path = ROOT / 'configs/foundationalassist_v4_preprocessing.json'
    cleaning = read_json(cleaning_path)
    if lock['stage'] != 'RQ1_FINAL_TEST_V4':
        raise ValueError('v4 RQ1 lock required')
    relative_model = lock['models']['BKT']
    if relative_model != 'artifacts/models/foundationalassist_v4/BKT.joblib':
        raise ValueError('v4 BKT checkpoint required')
    provenance = {}
    for relative in (relative_model, 'data/processed/foundationalassist_v4/train.parquet',
                     'data/processed/foundationalassist_v4/validation.parquet',
                     'data/processed/foundationalassist_v4/student_split.json',
                     'src/models/bkt.py'):
        expected = lock['pinned_sha256'].get(relative, cleaning['pinned_sha256'].get(relative))
        observed = digest(ROOT / relative)
        if not expected or observed != expected:
            raise ValueError(f'v4 pinned input changed: {relative}')
        provenance[relative] = observed
    train, validation = [pd.read_parquet(ROOT / f'data/processed/foundationalassist_v4/{split}.parquet')
                         for split in ('train', 'validation')]
    assignments = read_json(ROOT / 'data/processed/foundationalassist_v4/student_split.json')['assignments']
    for frame, split in ((train, 'train'), (validation, 'validation')):
        if not frame.split.eq(split).all() or not frame.user_id.astype(str).map(assignments).eq(split).all():
            raise ValueError('partition disagrees with saved student assignments')
    if set(train.user_id) & set(validation.user_id):
        raise ValueError('student overlap')
    graph_path = ROOT / 'configs/foundationalassist_v4_rq2_curriculum_graph.json'
    inventory_path = ROOT / 'configs/foundationalassist_v4_rq2_metadata_candidates.json'
    graph_config, inventory = read_json(graph_path), read_json(inventory_path)
    if graph_config['pilot_skill_ids_by_node_code'] != inventory['pilot_skill_ids_by_node_code'] or graph_config['dataset_revision'] != cleaning['dataset_revision'] or inventory['dataset_revision'] != cleaning['dataset_revision']:
        raise ValueError('scope/revision mismatch')
    graph = build_foundational_curriculum_graph(train, graph_config)
    review_path = ROOT / 'data/processed/foundationalassist_v4/rq2_content_review.json'
    conflict_ids = {str(r['problem_id']) for r in read_json(review_path) if 'metadata_conflict' in r['reasons']}
    pool = build_foundational_metadata_pool(train, skill_ids=set(graph['skills']), excluded_problem_ids=conflict_ids)
    for path in (CONFIG, graph_path, inventory_path, review_path, lock_path, cleaning_path,
                 Path(__file__).resolve(), ROOT / 'src/rq2/foundational_validation.py',
                 ROOT / 'src/rq2/state.py', ROOT / 'src/rq2/scenarios.py',
                 ROOT / 'src/rq2/candidates.py', ROOT / 'src/rq2/agent.py',
                 ROOT / 'src/rq2/curriculum_graph.py'):
        provenance[path.relative_to(ROOT).as_posix()] = digest(path)
    return config, validation, joblib.load(ROOT / relative_model), graph, pool, provenance


def local_json(endpoint, payload=None, timeout=5):
    url = 'http://127.0.0.1:11434/api/' + endpoint
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode('utf-8')
    request = Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def call_chat(request, *, timeout):
    return local_json('chat', request, timeout)


def probe_context(cases, graph, config):
    """Measure actual runtime token counts and compare same input at 2 contexts.

    This is a feasibility probe, excluded from recommendation study metrics.
    A context-count mismatch prevents all subsequent study calls.
    """
    runtime = config['agent']
    version = local_json('version')['version']
    models = local_json('tags')['models']
    matches = [m for m in models if m['name'] == runtime['model']]
    if len(matches) != 1:
        raise ValueError('configured local model must already be installed')
    model_digest = matches[0]['digest']
    show = local_json('show', {'model': runtime['model']})
    limits = [v for k, v in show.get('model_info', {}).items() if k.endswith('.context_length')]
    if not limits or min(limits) < 2 * runtime['num_ctx']:
        raise ValueError('model must support both context probe sizes')
    probes = []
    for variant in config['graph_variants']:
        requests = [(make_agent_request(shared, runtime), shared)
                    for _, _, v, _, _, shared in shared_repetitions(cases, graph, config) if v == variant]
        (request, bound), shared = max(requests, key=lambda item: item[0][1])
        response = call_chat(request, timeout=runtime['timeout_seconds'])
        count = checked_telemetry(response, runtime, bound)
        larger_runtime = {**runtime, 'num_ctx': runtime['num_ctx'] * 2}
        larger_request = deepcopy(request)
        larger_request['options']['num_ctx'] = larger_runtime['num_ctx']
        larger = call_chat(larger_request, timeout=runtime['timeout_seconds'])
        larger_count = checked_telemetry(larger, larger_runtime, bound)
        if count != larger_count:
            raise ValueError('prompt token count differs across context sizes; possible truncation')
        probes.append({'variant': variant, 'prompt_eval_count': count,
                       'double_context_prompt_eval_count': larger_count,
                       'conservative_byte_guard_with_reserve': bound,
                       'configured_context': runtime['num_ctx'], 'output_reserve': runtime['num_predict'],
                       'same_prompt_token_count': True})
    return {'stage': 'local_context_feasibility_not_rq2_results', 'verified': True,
            'model': runtime['model'], 'model_digest': model_digest,
            'ollama_version': version, 'probes': probes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe-context', action='store_true')
    parser.add_argument('--run-agent', action='store_true')
    parser.add_argument('--cohort', choices=('representative', 'challenge'), default='representative')
    args = parser.parse_args()
    config, validation, model, graph, pool, pins = load_pinned_inputs()
    frozen = model.global_parameters_snapshot()
    builder = build_foundational_cases if args.cohort == 'representative' else build_observed_link_challenge
    cases, supported_pool = builder(validation, model, graph, pool, config)
    private = PRIVATE if args.cohort == 'representative' else PRIVATE / 'challenge'
    if frozen != model.global_parameters_snapshot():
        raise RuntimeError('BKT fitted parameters changed')
    deterministic = run_deterministic(cases, graph, config)
    save(private / 'scenarios.json', cases)
    save(private / 'deterministic_runs.json', deterministic)
    surfaced = sorted({c['problem_id'] for case in cases for c in case['candidates']})
    save(private / 'surfaced_candidate_ids.json', surfaced)
    summary = summarize_operational(deterministic)
    summary['graph_activation_coverage'] = case_coverage(cases, graph, config)
    summary.update({'config_sha256': digest(CONFIG), 'input_sha256': pins,
                    'n_scenarios': len(cases), 'supported_pool_pairs': len(supported_pool),
                    'n_surfaced_candidate_ids': len(surfaced),
                    'scenarios_sha256': digest(private / 'scenarios.json'),
                    'cohort': args.cohort,
                    'cohort_design': config['supplementary_challenge'] if args.cohort == 'challenge' else 'original 50-student random-prefix pilot',
                    'context_verified': False, 'agent_status': 'not_run'})
    output = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_validation_summary.json'
    if args.cohort == 'challenge':
        output = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_challenge_summary.json'
    save(output, summary)
    if args.probe_context or args.run_agent:
        try:
            probe = probe_context(cases, graph, config)
        except (OSError, ValueError, KeyError, TypeError) as error:
            summary['agent_status'] = 'blocked_context_preflight'
            summary['context_probe_error_type'] = type(error).__name__
            save(output, summary)
            print(json.dumps({'agent_status': summary['agent_status'], 'error_type': type(error).__name__,
                              'message': 'Local runtime/context verification unavailable; no Agent study calls made.'}))
            return 2
        save(private / 'context_probe.json', probe)
        summary['context_verified'] = True
        summary['context_probe'] = probe
        summary['agent_status'] = 'context_verified_agent_not_run'
        if args.run_agent:
            # Require model/runtime identity to remain stable after feasibility.
            current = local_json('tags')['models']
            if not any(m['name'] == probe['model'] and m['digest'] == probe['model_digest'] for m in current) or local_json('version')['version'] != probe['ollama_version']:
                raise ValueError('runtime/model changed after preflight')
            summary['agent_status'] = 'validation_run_in_progress'
            save(output, summary)
            total = len(cases) * config['permutations_per_scenario'] * len(config['graph_variants'])
            def checkpoint(records):
                save(private / 'agent_runs.partial.json', records)
                if len(records) % 10 == 0 or len(records) == total:
                    print(json.dumps({'cohort': args.cohort, 'completed_calls': len(records),
                                      'total_calls': total, 'test_opened': False}), flush=True)
            agent_runs = run_agent(cases, graph, config, call_chat, checkpoint=checkpoint)
            save(private / 'agent_runs.json', agent_runs)
            summary['policies'].update(summarize_operational(agent_runs)['policies'])
            summary['agent_status'] = 'validation_run_completed_not_test'
        save(output, summary)
    print(json.dumps({'n_scenarios': summary['n_scenarios'], 'supported_pool_pairs': len(supported_pool),
                      'n_surfaced_candidate_ids': len(surfaced), 'agent_status': summary['agent_status'],
                      'test_opened': False, 'policies': summary['policies']}, indent=2))


if __name__ == '__main__':
    sys.exit(main() or 0)
