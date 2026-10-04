"""Prepare independent selection; real inference requires explicit --run-agent."""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import call_chat, digest, local_json, read_json, save
from scripts.run_foundational_rq2_agent_revision1 import prepare
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus, relevant_weak_sources
from src.rq2.runtime_journal import RuntimeIntegrityError, RuntimeJournal
from src.rq2.selection_agent_v2 import run_selection, selection_request

CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_selection_v2.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/selection_v2'
OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_selection_v2_preparation.json'


def prepare_selection():
    config = read_json(CONFIG)
    if config['stage'] != 'validation_development_not_lock_c' or config['test_access'] is not False:
        raise ValueError('VALIDATION selection development only')
    if config['planned_probe_calls'] != 4:
        raise ValueError('fixed four-probe context protocol required')
    _, old_config, original, cohorts, pins = prepare()
    schedule = [{**r, 'arm': 'independent_selection_v2'} for r in original if r['arm'] == 'schema_and_objective']
    for cohort in cohorts:
        folder = ROOT / 'data/processed/foundationalassist_v4/rq2_validation'
        if cohort == 'challenge':
            folder /= 'challenge'
        indices = {case['scenario_id']: index for index, case in enumerate(read_json(folder / 'scenarios.json'))}
        for row in schedule:
            if row['cohort'] == cohort:
                row['random_seed_index'] = indices[row['scenario_id']]
    if len(schedule) != config['new_calls_planned']:
        raise ValueError('fixed bounded schedule required')
    for row in schedule:
        selection_request(row['shared'], config, row['enum_ids'])
    for path in (CONFIG, Path(__file__), ROOT / 'src/rq2/runtime_journal.py',
                 ROOT / 'src/rq2/selection_agent_v2.py', ROOT / 'reports/rq2_selection_protocol_v2.md'):
        pins[path.relative_to(ROOT).as_posix()] = digest(path)
    return config, old_config, schedule, cohorts, pins


def mastery_metrics(shared, selected_id):
    candidates = shared['candidates']
    counts = Counter(c['skill_id'] for c in candidates)
    values = {skill: shared['state']['skills'][skill] for skill in counts}
    k, m = len(values), len(candidates)
    ranks = {skill: (sum(v < value for v in values.values()) +
                     (sum(v == value for v in values.values()) - 1) / 2) / (k - 1)
             for skill, value in values.items()} if k > 1 else {}
    lowest = min(values.values())
    selected = next((c for c in candidates if c['problem_id'] == selected_id), None)
    return {
        'selected_skill_id': selected['skill_id'] if selected else None,
        'selected_mastery_rank_normalized': ranks.get(selected['skill_id']) if selected else None,
        'selected_lowest_mastery_skill': values[selected['skill_id']] == lowest if selected else None,
        'random_expected_mastery_rank': sum(counts[s] * ranks[s] for s in counts) / m if k > 1 else None,
        'random_probability_lowest_mastery_skill': sum(counts[s] for s in counts if values[s] == lowest) / m,
        'random_probability_id_stable': 1 / m ** 2,
        'random_probability_skill_stable': sum((n / m) ** 3 for n in counts.values()),
        'random_expected_position_probability': 1 / m}


def enrich_selection(row, item, old_config):
    row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
    row.update(agrees_with_bplus=False, reference_soft_remediation=False, selected_mastery=None,
               selected_train_success_rate=None, selected_support=None)
    row.update(mastery_metrics(item['shared'], row['selected_problem_id'] if row['candidate_valid'] else None))
    if row['candidate_valid']:
        candidate = next(c for c in item['shared']['candidates'] if c['problem_id'] == row['selected_problem_id'])
        reference = {**item['shared'], 'graph': old_config['reference_graph']}
        row.update(agrees_with_bplus=candidate['problem_id'] == recommend_foundational_bplus(item['shared'], old_config['bplus'])['problem_id'],
                   reference_soft_remediation=candidate['skill_id'] in relevant_weak_sources(reference, old_config['bplus']),
                   selected_mastery=item['shared']['state']['skills'][candidate['skill_id']],
                   selected_train_success_rate=candidate['difficulty'], selected_support=candidate['support'])
    return row


def baseline_rows(schedule, old_config, cohorts):
    rows = {policy: [] for policy in ('B+', 'random', 'always_first')}
    legacy = {(cohort, r['scenario_id'], r['repetition'], r['graph_variant'], r['policy']): r['selected_problem_id']
              for cohort, source in cohorts.items() for r in source['legacy_records'] if r['policy'] in rows}
    for item in schedule:
        ids = [c['problem_id'] for c in item['shared']['candidates']]
        for policy in rows:
            start = time.perf_counter()
            if policy == 'B+':
                selected = recommend_foundational_bplus(item['shared'], old_config['bplus'])['problem_id']
            elif policy == 'random':
                seed = np.random.SeedSequence([old_config['seed'], item['random_seed_index'], item['repetition']])
                rng = np.random.default_rng(seed.spawn(2)[1])
                ordered_ids = sorted(ids)
                selected = ordered_ids[int(rng.integers(len(ordered_ids)))]
            else:
                selected = ids[0]
            latency = time.perf_counter() - start
            key = (item['cohort'], item['scenario_id'], item['repetition'], item['graph_variant'], policy)
            if selected != legacy[key]:
                raise ValueError('baseline replay differs from frozen reference')
            row = {'policy': policy, 'candidate_valid': True, 'selected_problem_id': selected,
                   'selected_position': ids.index(selected), 'selected_enum_position': item['enum_ids'].index(selected),
                   'latency_seconds': latency, 'latency_scope': 'local_policy_computation_only', 'error_stage': None}
            rows[policy].append(enrich_selection(row, item, old_config))
    return rows


def call_accounting(path):
    """Count logical attempts/transport calls/responses, never JSONL line count."""
    events = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
    scopes = {e['call_index']: e['scope'] for e in events if e['event'] == 'call_scope'}
    result = {}
    for scope in ('probe', 'study'):
        result[scope] = {name: sum(e['event'] == event and scopes.get(e['call_index']) == scope for e in events)
                         for name, event in (('attempts_started', 'request_started'),
                                             ('transport_calls', 'transport_started'), ('responses_received', 'response_received'))}
    started = [e['call_index'] for e in events if e['event'] == 'request_started']
    if started != list(range(1, len(started) + 1)) or set(started) != set(scopes):
        raise ValueError('journal call scopes/index mismatch')
    for index in started:
        if scopes[index] not in ('probe', 'study'):
            raise ValueError('unknown journal scope')
        transports = sum(e['call_index'] == index and e['event'] == 'transport_started' for e in events)
        responses = sum(e['call_index'] == index and e['event'] == 'response_received' for e in events)
        if not 0 <= responses <= transports <= 1:
            raise ValueError('duplicate or unmatched journal transport/response')
    for scope in result.values():
        if not 0 <= scope['responses_received'] <= scope['transport_calls'] <= scope['attempts_started']:
            raise ValueError('journal call accounting mismatch')
    return result


def aggregate(rows, schedule, cohorts):
    result = {}
    for cohort in cohorts:
        result[cohort] = {}
        for variant in ('curriculum_edges', 'no_edges'):
            group = [r for r in rows if r['cohort'] == cohort and r['graph_variant'] == variant]
            valid = [r for r in group if r['candidate_valid']]
            planned = [r for r in schedule if r['cohort'] == cohort and r['graph_variant'] == variant]
            students = {}
            for row in group:
                students.setdefault(row['student_id'], []).append(row)
            complete = [rs for rs in students.values() if len(rs) == 3 and all(r['candidate_valid'] for r in rs)]
            id_stable = sum(len({r['selected_problem_id'] for r in rs}) == 1 for rs in complete)
            skill_stable = sum(len({r['selected_skill_id'] for r in rs}) == 1 for rs in complete)
            ranked = [r for r in valid if r['selected_mastery_rank_normalized'] is not None]
            references = [mastery_metrics(r['shared'], None) for r in planned]
            expected_ranks = [r['random_expected_mastery_rank'] for r in references if r['random_expected_mastery_rank'] is not None]
            result[cohort][variant] = {
                'planned_calls': len(planned), 'completed_calls': len(group), 'valid_selections': len(valid),
                'valid_selection_fraction_all_planned_calls': len(valid) / len(planned),
                'planned_students': len({r['student_id'] for r in planned}),
                'complete_valid_triplets': len(complete),
                'id_stable_students': id_stable,
                'id_stable_fraction_complete_triplets': id_stable / len(complete) if complete else None,
                'skill_stable_students': skill_stable,
                'skill_stable_fraction_complete_triplets': skill_stable / len(complete) if complete else None,
                'variable_students_among_complete_valid_triplets': len(complete) - id_stable,
                'incomplete_valid_triplets': len({r['student_id'] for r in planned}) - len(complete),
                'display_position_counts_valid': dict(Counter(r['selected_position'] for r in valid)),
                'enum_position_counts_valid': dict(Counter(r['selected_enum_position'] for r in valid)),
                'first_display_position_fraction_valid': sum(r['selected_position'] == 0 for r in valid) / len(valid) if valid else None,
                'first_enum_position_fraction_valid': sum(r['selected_enum_position'] == 0 for r in valid) / len(valid) if valid else None,
                'agreement_with_bplus_count_supplementary': sum(r['agrees_with_bplus'] for r in valid),
                'reference_soft_remediation_count_descriptive': sum(r['reference_soft_remediation'] for r in valid),
                'selected_mastery_mean_descriptive': statistics.mean(r['selected_mastery'] for r in valid) if valid else None,
                'selected_train_success_rate_mean_descriptive': statistics.mean(r['selected_train_success_rate'] for r in valid) if valid else None,
                'selected_support_mean_descriptive': statistics.mean(r['selected_support'] for r in valid) if valid else None,
                'mastery_rank_mean_valid_defined': statistics.mean(r['selected_mastery_rank_normalized'] for r in ranked) if ranked else None,
                'mastery_rank_defined_valid_calls': len(ranked),
                'mastery_rank_excluded_single_skill_valid_calls': len(valid) - len(ranked),
                'mastery_rank_coverage_all_planned_calls': len(ranked) / len(planned),
                'lowest_mastery_skill_count_valid': sum(r['selected_lowest_mastery_skill'] for r in valid),
                'lowest_mastery_skill_fraction_valid': sum(r['selected_lowest_mastery_skill'] for r in valid) / len(valid) if valid else None,
                'random_analytic_reference': {
                    'id_stable_probability_mean': statistics.mean(r['random_probability_id_stable'] for r in references),
                    'skill_stable_probability_mean': statistics.mean(r['random_probability_skill_stable'] for r in references),
                    'mastery_rank_mean_defined': statistics.mean(expected_ranks) if expected_ranks else None,
                    'rank_defined_planned_calls': len(expected_ranks),
                    'lowest_mastery_skill_probability_mean': statistics.mean(r['random_probability_lowest_mastery_skill'] for r in references),
                    'each_position_probability_mean': statistics.mean(r['random_expected_position_probability'] for r in references)},
                'latency_seconds_mean_all_calls': statistics.mean(r['latency_seconds'] for r in group) if group else None,
                'latency_scope': group[0].get('latency_scope', 'agent_request_transport_and_validation_including_runtime_checks') if group else None,
                'error_stage_counts': dict(Counter(r['error_stage'] for r in group if r['error_stage']))}
        paired = {}
        for row in rows:
            if row['cohort'] == cohort:
                paired.setdefault((row['student_id'], row['repetition']), {})[row['graph_variant']] = row
        complete_pairs = [pair for pair in paired.values()
                          if set(pair) == {'curriculum_edges', 'no_edges'}
                          and all(r['candidate_valid'] for r in pair.values())]
        planned_pairs = len({(r['student_id'], r['repetition']) for r in schedule if r['cohort'] == cohort})
        result[cohort]['paired_graph_sensitivity_descriptive'] = {
            'planned_pairs': planned_pairs, 'valid_pairs': len(complete_pairs),
            'incomplete_valid_pairs': planned_pairs - len(complete_pairs),
            'changed_choice_count': sum(pair['curriculum_edges']['selected_problem_id'] !=
                                        pair['no_edges']['selected_problem_id'] for pair in complete_pairs)}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-agent', action='store_true')
    args = parser.parse_args()
    if any((PRIVATE / name).exists() for name in ('runs.json', 'runs.partial.json', 'calls.jsonl')):
        raise ValueError('selection calls already exist; no overwrite or silent retry')
    config, old_config, schedule, cohorts, pins = prepare_selection()
    baselines = baseline_rows(schedule, old_config, cohorts)
    save(PRIVATE / 'schedule.json', schedule)
    save(PRIVATE / 'baseline_reference.json', {c: [r for r in source['legacy_records'] if r['policy'] != 'Agent_legacy'] for c, source in cohorts.items()})
    save(PRIVATE / 'baseline_runs.json', baselines)
    summary = {'stage': config['stage'], 'test_opened': False, 'agent_status': 'prepared_no_llm',
               'version': config['version'], 'input_sha256': pins, 'new_calls_planned': len(schedule),
               'model_calls_completed': 0, 'study_rows_recorded': 0, 'claims': config['claims'],
               'schedule_sha256': digest(PRIVATE / 'schedule.json'),
               'baseline_reference_sha256': digest(PRIVATE / 'baseline_reference.json'),
               'baseline_runs_sha256': digest(PRIVATE / 'baseline_runs.json'),
               'baseline_metrics': {policy: aggregate(rows, schedule, cohorts) for policy, rows in baselines.items()},
               'planned_probe_calls': 4, 'planned_study_calls': len(schedule),
               'call_accounting': {scope: {'attempts_started': 0, 'transport_calls': 0, 'responses_received': 0} for scope in ('probe', 'study')},
               'cohort_planned_students': {c: s['n_students'] for c, s in cohorts.items()},
               'agreement_is_gold_label': False, 'reason_semantically_verified': False}
    save(OUTPUT, summary)
    if not args.run_agent:
        print(json.dumps({'status': summary['agent_status'], 'planned_calls': len(schedule), 'model_calls': 0, 'test_opened': False}))
        return
    expected = {'ollama_version': config['expected_ollama_version'], 'model': config['agent']['model'], 'model_digest': config['model_digest']}
    def identity():
        version = local_json('version')['version']
        matches = [m for m in local_json('tags')['models'] if m['name'] == expected['model']]
        return {'ollama_version': version, 'model': expected['model'],
                'model_digest': matches[0]['digest'] if len(matches) == 1 else None}
    journal = RuntimeJournal(PRIVATE / 'calls.jsonl')
    scope = 'probe'
    def transport(request, *, timeout):
        journal.append(journal.call_index, 'transport_started')
        return call_chat(request, timeout=timeout)
    def invoke(request, *, timeout):
        journal.append(journal.call_index + 1, 'call_scope', scope=scope)
        return journal.chat(request, timeout=timeout, call=transport, read_identity=identity, expected=expected)
    probes = []
    rows = []
    try:
        for variant in ('curriculum_edges', 'no_edges'):
            requests = [selection_request(r['shared'], config, r['enum_ids']) for r in schedule if r['graph_variant'] == variant]
            request, bound = max(requests, key=lambda r: r[1])
            counts = []
            for scale in (1, 2):
                probe = deepcopy(request)
                probe['options']['num_ctx'] *= scale
                response = invoke(probe, timeout=config['agent']['timeout_seconds'])
                counts.append(checked_telemetry(response, {**config['agent'], 'num_ctx': scale * config['agent']['num_ctx']}, bound))
            if counts[0] != counts[1]:
                raise ValueError('context counts differ; do not truncate')
            probes.append({'graph_variant': variant, 'prompt_eval_count': counts[0], 'double_context_prompt_eval_count': counts[1]})
        summary.update(agent_status='in_progress', context_probes=probes, probe_calls_not_study=4)
        save(OUTPUT, summary)
        scope = 'study'
        for item in schedule:
            row = run_selection(item['shared'], config, item['enum_ids'], invoke)
            enrich_selection(row, item, old_config)
            row['journal_call_index'] = journal.call_index
            rows.append(row)
            save(PRIVATE / 'runs.partial.json', rows)
            if row['error_stage'] == 'runtime_integrity':
                raise RuntimeIntegrityError(row['error_message'])
            if len(rows) % 12 == 0:
                print(json.dumps({'completed': len(rows), 'total': len(schedule)}), flush=True)
        for relative, expected_hash in pins.items():
            if digest(ROOT / relative) != expected_hash:
                raise ValueError('study input changed')
        journal.observe(journal.call_index, 'end_gate', identity, expected)
        accounting = call_accounting(journal.path)
        if accounting['probe']['attempts_started'] != 4 or accounting['study']['attempts_started'] != len(schedule):
            raise ValueError('planned versus actual journal attempts differ')
    except (OSError, ValueError, KeyError, TypeError) as error:
        summary.update(agent_status='blocked_integrity_or_preflight', study_rows_recorded=len(rows),
                       completed_journal_attempts=journal.call_index, error_type=type(error).__name__, error_message=str(error))
        summary['call_accounting'] = call_accounting(journal.path)
        summary['model_calls_completed'] = summary['call_accounting']['study']['responses_received']
        save(OUTPUT, summary)
        raise
    save(PRIVATE / 'runs.json', rows)
    summary.update(agent_status='completed_validation_not_test', model_calls_completed=accounting['study']['responses_received'],
                   study_rows_recorded=len(rows),
                   cohorts=aggregate(rows, schedule, cohorts), private_runs_sha256=digest(PRIVATE / 'runs.json'),
                   journal_sha256=digest(PRIVATE / 'calls.jsonl'), runtime_identity_unchanged=True)
    summary['call_accounting'] = accounting
    save(OUTPUT, summary)


if __name__ == '__main__':
    main()
