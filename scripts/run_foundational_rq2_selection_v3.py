"""Two committed gates: diagnostic contract, then the final development batch."""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import load_pinned_inputs, read_json, save, digest, local_json, call_chat
from scripts.prepare_foundational_rq2_selection_v2 import prepare_selection, enrich_selection, aggregate
from src.rq2.foundational_validation import build_foundational_cases, build_observed_link_challenge, shared_repetitions, compact_graph, recommend_foundational_bplus, checked_telemetry, case_coverage
from src.rq2.runtime_journal import RuntimeJournal, RuntimeIntegrityError
from src.rq2.selection_agent_v3 import selection_request, run_selection, choose_contract, flag_rates, stop_decision

PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/selection_v3'
DIAGNOSTIC_CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_selection_v3_diagnostic.json'
FINAL_CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_selection_v3.json'
TABLES = ROOT / 'artifacts/tables'


def output(phase):
    return TABLES / f'foundationalassist_v4_rq2_selection_v3_{phase}.json'


def code_pins(config_path):
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in (
        config_path, DIAGNOSTIC_CONFIG, Path(__file__), ROOT / 'src/rq2/selection_agent_v3.py',
        ROOT / 'src/rq2/runtime_journal.py', ROOT / 'src/rq2/selection_agent_v2.py',
        ROOT / 'scripts/prepare_foundational_rq2_selection_v2.py', ROOT / 'reports/rq2_selection_protocol_v3.md')}


def verify_pins(pins):
    for relative, expected in pins.items():
        if digest(ROOT / relative) != expected:
            raise ValueError('study input changed: ' + relative)


def committed(pins):
    """Require reviewable committed bytes before any real model call."""
    for relative, expected in pins.items():
        if relative.startswith(('data/', 'artifacts/models/')):
            continue
        blob = subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT)
        attr = subprocess.check_output(['git', 'check-attr', '-z', 'eol', '--', relative], cwd=ROOT).decode().split('\0')[2]
        if attr == 'crlf':
            blob = blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        if digest_bytes(blob) != expected:
            raise ValueError('commit inputs before inference: ' + relative)
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()


def digest_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def diagnostic_inputs(config):
    _, old, schedule, _, pins = prepare_selection()
    cases = [r for r in schedule if r['repetition'] == 0 and r['graph_variant'] == 'curriculum_edges']
    if len(cases) != 24:
        raise ValueError('fixed 24 legacy requests required')
    diagnostic = []
    for index, case in enumerate(cases):
        caps = config['diagnostic_caps'] if index % 2 == 0 else list(reversed(config['diagnostic_caps']))
        for cap in caps:
            item = {**case, 'cap': cap, 'scope': f'contract_{cap}'}
            selection_request(item['shared'], {**config, 'reason_max_chars': cap}, item['enum_ids'])
            diagnostic.append(item)
    return old, diagnostic, {**pins, **code_pins(DIAGNOSTIC_CONFIG)}


def study_inputs(config):
    base, validation, model, graph, pool, pins = load_pinned_inputs()
    frozen = model.global_parameters_snapshot()
    excluded = set()
    for path in sorted((ROOT / 'data/processed/foundationalassist_v4/rq2_validation').rglob('scenarios.json')):
        if path.is_relative_to(PRIVATE):
            continue
        excluded.update(str(case['student_id']) for case in read_json(path))
        pins[path.relative_to(ROOT).as_posix()] = digest(path)
    available = validation[~validation.user_id.astype(str).isin(excluded)]
    design = {**base, 'seed': config['selection_seed'], 'validation_scenarios': 40}
    cases, _ = build_foundational_cases(available, model, graph, pool, design)
    if set(str(c['student_id']) for c in cases) & excluded:
        raise ValueError('new students overlap previous scenarios')
    # Exact old challenge criterion, checked before any new policy output.
    try:
        challenge, _ = build_observed_link_challenge(available, model, graph, pool, base)
    except ValueError as error:
        if str(error) != 'no observed supported weak links at the fixed prefix':
            raise
        challenge = []
    if challenge:
        raise ValueError('new challenge available: declare its size/schedule before running')
    if model.global_parameters_snapshot() != frozen:
        raise ValueError('BKT fitted parameters changed')
    schedule, baselines = [], {p: [] for p in ('B+', 'random', 'always_first')}
    indices = {c['scenario_id']: i for i, c in enumerate(cases)}
    old = {**design, 'reference_graph': compact_graph(graph, 'curriculum_edges')}
    for case, rep, variant, order, random_id, shared in shared_repetitions(cases, graph, design):
        index = indices[case['scenario_id']]
        enum_rng = np.random.default_rng(np.random.SeedSequence([config['enum_seed'], 0, index, rep]).spawn(2)[0])
        ids = sorted(c['problem_id'] for c in shared['candidates'])
        enum_ids = [ids[int(i)] for i in enum_rng.permutation(len(ids))]
        item = {'cohort': 'representative', 'scenario_id': case['scenario_id'], 'student_id': case['student_id'],
                'repetition': rep, 'graph_variant': variant, 'permutation': order, 'enum_ids': enum_ids,
                'shared': shared, 'scope': 'study'}
        selection_request(shared, config, enum_ids)
        schedule.append(item)
        for policy in baselines:
            start = time.perf_counter()
            if policy == 'B+':
                selected = recommend_foundational_bplus(shared, design['bplus'])['problem_id']
            elif policy == 'random':
                rng = np.random.default_rng(np.random.SeedSequence([design['seed'], index, rep]).spawn(2)[1])
                selected = ids[int(rng.integers(len(ids)))]
                if selected != random_id:
                    raise ValueError('random replay mismatch')
            else:
                selected = shared['candidates'][0]['problem_id']
            latency = time.perf_counter() - start
            display = [c['problem_id'] for c in shared['candidates']]
            row = {'candidate_valid': True, 'selected_problem_id': selected, 'selected_position': display.index(selected),
                   'selected_enum_position': enum_ids.index(selected), 'latency_seconds': latency,
                   'latency_scope': 'local_policy_computation_only', 'error_stage': None}
            baselines[policy].append(enrich_selection(row, item, old))
    rng = np.random.default_rng(config['repeat_seed'])
    selected_repeats = []
    for variant in ('curriculum_edges', 'no_edges'):
        indices = [i for i, item in enumerate(schedule) if item['graph_variant'] == variant]
        selected_repeats.extend(sorted(int(i) for i in rng.choice(indices, size=6, replace=False)))
    repeat_schedule = [{**schedule[index], 'scope': 'repeat', 'original_study_index': index, 'repeat_index': rep}
                       for index in selected_repeats for rep in range(3)]
    pins.update(code_pins(FINAL_CONFIG))
    pins[output('diagnostic').relative_to(ROOT).as_posix()] = digest(output('diagnostic'))
    info = {'new_students': len(cases), 'excluded_previous_students': len(excluded),
            'new_challenge_eligible': len(challenge), 'graph_activation_coverage': case_coverage(cases, graph, design)}
    return old, cases, schedule, repeat_schedule, baselines, pins, info


def accounting(path):
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    scopes = {e['call_index']: e['scope'] for e in events if e['event'] == 'call_scope'}
    started = [e['call_index'] for e in events if e['event'] == 'request_started']
    if started != list(range(1, len(started) + 1)) or set(started) != set(scopes):
        raise ValueError('journal index/scope mismatch')
    result = {}
    for index in started:
        group = result.setdefault(scopes[index], {'attempts': 0, 'transport': 0, 'responses': 0})
        transport = sum(e['call_index'] == index and e['event'] == 'transport_started' for e in events)
        responses = sum(e['call_index'] == index and e['event'] == 'response_received' for e in events)
        if not 0 <= responses <= transport <= 1:
            raise ValueError('journal transport/response mismatch')
        group['attempts'] += 1
        group['transport'] += transport
        group['responses'] += responses
    return result


def inference(config, directory):
    expected = {'ollama_version': config['expected_ollama_version'], 'model': config['agent']['model'], 'model_digest': config['model_digest']}
    def identity():
        tags = [m for m in local_json('tags')['models'] if m['name'] == expected['model']]
        return {'ollama_version': local_json('version')['version'], 'model': expected['model'],
                'model_digest': tags[0]['digest'] if len(tags) == 1 else None}
    if identity() != expected:
        raise RuntimeIntegrityError('runtime/model mismatch before journal creation')
    journal = RuntimeJournal(directory / 'calls.jsonl')
    def call(request, *, timeout, scope):
        journal.append(journal.call_index + 1, 'call_scope', scope=scope)
        def transport(request, *, timeout):
            journal.append(journal.call_index, 'transport_started')
            return call_chat(request, timeout=timeout)
        return journal.chat(request, timeout=timeout, call=transport, read_identity=identity, expected=expected)
    return journal, call, identity, expected


def rubric_packet(rows, config):
    rng, packet = np.random.default_rng(config['rubric_seed']), []
    for variant in ('curriculum_edges', 'no_edges'):
        eligible = [i for i, r in enumerate(rows) if r['candidate_valid'] and r['graph_variant'] == variant]
        chosen = rng.choice(eligible, size=min(20, len(eligible)), replace=False)
        for index in chosen:
            row = rows[int(index)]
            packet.append({'study_index': int(index), 'student_id': row['student_id'], 'graph_variant': variant,
                           'input': row['request']['messages'][1]['content'], 'choice': row['selected_problem_id'],
                           'reason': row['reason'], 'scores': None, 'reviewer': None})
    return [packet[int(i)] for i in rng.permutation(len(packet))]


def execute(phase, config, old, schedule, pins, repeats=None, baselines=None, info=None):
    directory = PRIVATE / phase
    if (directory / 'calls.jsonl').exists():
        raise ValueError('journal exists; no overwrite/retry')
    lock_commit = committed(pins)
    save(directory / 'schedule.json', schedule)
    summary = {'stage': 'validation_development_not_lock_c', 'phase': phase, 'status': 'in_progress',
               'test_opened': False, 'lock_commit_before_calls': lock_commit, 'input_sha256': pins,
               'schedule_sha256': digest(directory / 'schedule.json'), 'rubric_status': 'not_evaluated',
               'reason_semantically_verified': False, 'lock_c_authorized': False}
    if phase == 'study':
        save(directory / 'repeat_schedule.json', repeats)
        save(directory / 'baseline_runs.json', baselines)
        summary.update(cohort=info, repeat_schedule_sha256=digest(directory / 'repeat_schedule.json'),
                       baseline_runs_sha256=digest(directory / 'baseline_runs.json'),
                       baselines={p: aggregate(rs, schedule, {'representative': {}}) for p, rs in baselines.items()})
    save(output(phase), summary)
    journal, call, identity, expected = inference(config, directory)
    rows, repeated, probes = [], [], []
    try:
        if phase == 'study':
            for variant in ('curriculum_edges', 'no_edges'):
                request, bound = max((selection_request(i['shared'], config, i['enum_ids']) for i in schedule if i['graph_variant'] == variant), key=lambda pair: pair[1])
                counts = []
                for scale in (1, 2):
                    probe = deepcopy(request)
                    probe['options']['num_ctx'] *= scale
                    response = call(probe, timeout=config['agent']['timeout_seconds'], scope='probe')
                    counts.append(checked_telemetry(response, {**config['agent'], 'num_ctx': config['agent']['num_ctx'] * scale}, bound))
                if counts[0] != counts[1]:
                    raise ValueError('context probe counts differ')
                probes.append({'variant': variant, 'prompt_eval_count': counts[0], 'double_context_prompt_eval_count': counts[1]})
        for index, item in enumerate(schedule):
            item_config = {**config, 'reason_max_chars': item.get('cap', config['reason_max_chars'])}
            row = run_selection(item['shared'], item_config, item['enum_ids'], lambda request, timeout: call(request, timeout=timeout, scope=item['scope']))
            if phase == 'study':
                enrich_selection(row, item, old)
            else:
                row['cap'] = item['cap']
            row['journal_call_index'] = journal.call_index
            rows.append(row)
            save(directory / 'runs.partial.json', rows)
            if row['error_stage'] == 'runtime_integrity':
                raise RuntimeIntegrityError(row['error_message'])
            if len(rows) % 12 == 0:
                print(json.dumps({'phase': phase, 'completed': len(rows), 'total': len(schedule)}), flush=True)
        for item in repeats or []:
            row = run_selection(item['shared'], config, item['enum_ids'], lambda request, timeout: call(request, timeout=timeout, scope='repeat'))
            if row['request'] != rows[item['original_study_index']]['request']:
                raise ValueError('repeat request differs from original')
            row.update(original_study_index=item['original_study_index'], repeat_index=item['repeat_index'], journal_call_index=journal.call_index)
            repeated.append(row)
            save(directory / 'repeat_runs.partial.json', repeated)
            if row['error_stage'] == 'runtime_integrity':
                raise RuntimeIntegrityError(row['error_message'])
        verify_pins(pins)
        journal.observe(journal.call_index, 'end_gate', identity, expected)
    except (OSError, ValueError, KeyError, TypeError) as error:
        summary.update(status='blocked_integrity_or_preflight', error_type=type(error).__name__, error_message=str(error),
                       call_accounting=accounting(journal.path), completed_rows=len(rows), completed_repeats=len(repeated))
        save(output(phase), summary)
        raise
    save(directory / 'runs.json', rows)
    summary.update(status='completed_validation_not_test', runs_sha256=digest(directory / 'runs.json'),
                   journal_sha256=digest(journal.path), call_accounting=accounting(journal.path),
                   context_probes=probes, runtime_identity_verified=True)
    if phase == 'diagnostic':
        summary['contract_decision'] = choose_contract(rows)
    else:
        save(directory / 'repeat_runs.json', repeated)
        packet = rubric_packet(rows, config)
        save(directory / 'rubric_packet.json', packet)
        metric = aggregate(rows, schedule, {'representative': {}})
        stable_repeats = 0
        for index in sorted({r['original_study_index'] for r in repeated}):
            group = [rows[index]] + [r for r in repeated if r['original_study_index'] == index]
            stable_repeats += all(r['candidate_valid'] for r in group) and len({r['selected_problem_id'] for r in group}) == 1
        summary.update(metrics=metric, rationale_flags=flag_rates(rows, 240), stop_decision=stop_decision(rows, metric, packet),
                       identical_request_reference={'planned_requests': 12, 'valid_id_stable_four_calls': stable_repeats},
                       repeat_runs_sha256=digest(directory / 'repeat_runs.json'), rubric_packet_sha256=digest(directory / 'rubric_packet.json'),
                       repeat_output_flags=flag_rates(repeated, 36), rubric_sample_size=len(packet))
    save(output(phase), summary)
    print(json.dumps({'phase': phase, 'status': summary['status'], 'call_accounting': summary['call_accounting']}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare-diagnostic', 'run-diagnostic', 'prepare-study', 'run-study'))
    args = parser.parse_args()
    config = read_json(DIAGNOSTIC_CONFIG)
    if config['stage'] != 'validation_development_not_lock_c' or config['test_access'] is not False:
        raise ValueError('VALIDATION development only')
    if args.action.endswith('diagnostic'):
        old, schedule, pins = diagnostic_inputs(config)
        if args.action == 'run-diagnostic':
            execute('diagnostic', config, old, schedule, pins)
        else:
            save(PRIVATE / 'diagnostic/schedule.json', schedule)
            print(json.dumps({'diagnostic_calls': len(schedule), 'new_model_calls': 0}))
        return
    diagnostic = read_json(output('diagnostic'))
    if diagnostic['status'] != 'completed_validation_not_test':
        raise ValueError('complete diagnostic required')
    verify_pins(diagnostic['input_sha256'])
    final = {**config, 'phase': 'study', 'reason_max_chars': diagnostic['contract_decision']['selected_cap'],
             'diagnostic_summary_sha256': digest(output('diagnostic'))}
    if args.action == 'prepare-study':
        if FINAL_CONFIG.exists():
            raise ValueError('final config already exists; no silent rewrite')
        with FINAL_CONFIG.open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(final, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    elif read_json(FINAL_CONFIG) != final:
        raise ValueError('final config disagrees with contract decision')
    old, cases, schedule, repeats, baselines, pins, info = study_inputs(final)
    if args.action == 'prepare-study':
        save(PRIVATE / 'study/scenarios.json', cases)
        save(PRIVATE / 'study/schedule.json', schedule)
        save(PRIVATE / 'study/repeat_schedule.json', repeats)
        save(output('preparation'), {'stage': 'validation_development_not_lock_c', 'test_opened': False,
             'input_sha256': pins, 'cohort': info, 'planned_calls': {'probe': 4, 'study': len(schedule), 'repeat': len(repeats)},
             'scenario_sha256': digest(PRIVATE / 'study/scenarios.json'), 'new_model_calls': 0})
        print(json.dumps({'prepared': info, 'planned_calls': 280, 'new_model_calls': 0}))
    else:
        prepared = read_json(output('preparation'))
        if prepared['input_sha256'] != pins or read_json(PRIVATE / 'study/schedule.json') != schedule:
            raise ValueError('prepared study input mismatch')
        execute('study', final, old, schedule, pins, repeats, baselines, info)


if __name__ == '__main__':
    main()
