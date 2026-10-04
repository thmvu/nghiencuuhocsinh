"""Prepare independent selection; real inference requires explicit --run-agent."""

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys

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
    _, old_config, original, cohorts, pins = prepare()
    schedule = [{**r, 'arm': 'independent_selection_v2'} for r in original if r['arm'] == 'schema_and_objective']
    if len(schedule) != config['new_calls_planned']:
        raise ValueError('fixed bounded schedule required')
    for row in schedule:
        selection_request(row['shared'], config, row['enum_ids'])
    for path in (CONFIG, Path(__file__), ROOT / 'src/rq2/runtime_journal.py',
                 ROOT / 'src/rq2/selection_agent_v2.py', ROOT / 'reports/rq2_selection_protocol_v2.md'):
        pins[path.relative_to(ROOT).as_posix()] = digest(path)
    return config, old_config, schedule, cohorts, pins


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
            result[cohort][variant] = {
                'planned_calls': len(planned), 'completed_calls': len(group), 'valid_selections': len(valid),
                'valid_selection_fraction_all_planned_calls': len(valid) / len(planned),
                'planned_students': len({r['student_id'] for r in planned}),
                'complete_valid_triplets': len(complete),
                'variable_students_among_complete_valid_triplets': sum(len({r['selected_problem_id'] for r in rs}) > 1 for rs in complete),
                'incomplete_valid_triplets': len({r['student_id'] for r in planned}) - len(complete),
                'display_position_counts_valid': dict(Counter(r['selected_position'] for r in valid)),
                'enum_position_counts_valid': dict(Counter(r['selected_enum_position'] for r in valid)),
                'agreement_with_bplus_count_supplementary': sum(r['agrees_with_bplus'] for r in valid),
                'reference_soft_remediation_count_descriptive': sum(r['reference_soft_remediation'] for r in valid),
                'selected_mastery_mean_descriptive': statistics.mean(r['selected_mastery'] for r in valid) if valid else None,
                'selected_train_success_rate_mean_descriptive': statistics.mean(r['selected_train_success_rate'] for r in valid) if valid else None,
                'selected_support_mean_descriptive': statistics.mean(r['selected_support'] for r in valid) if valid else None,
                'latency_seconds_mean_all_calls': statistics.mean(r['latency_seconds'] for r in group) if group else None,
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
    save(PRIVATE / 'schedule.json', schedule)
    save(PRIVATE / 'baseline_reference.json', {c: [r for r in source['legacy_records'] if r['policy'] != 'Agent_legacy'] for c, source in cohorts.items()})
    summary = {'stage': config['stage'], 'test_opened': False, 'agent_status': 'prepared_no_llm',
               'version': config['version'], 'input_sha256': pins, 'new_calls_planned': len(schedule),
               'model_calls_completed': 0, 'claims': config['claims'],
               'schedule_sha256': digest(PRIVATE / 'schedule.json'),
               'baseline_reference_sha256': digest(PRIVATE / 'baseline_reference.json'),
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
    def invoke(request, *, timeout):
        return journal.chat(request, timeout=timeout, call=call_chat, read_identity=identity, expected=expected)
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
        for item in schedule:
            row = run_selection(item['shared'], config, item['enum_ids'], invoke)
            row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
            row.update(journal_call_index=journal.call_index, agrees_with_bplus=False,
                       reference_soft_remediation=False, selected_mastery=None,
                       selected_train_success_rate=None, selected_support=None)
            if row['candidate_valid']:
                candidate = next(c for c in item['shared']['candidates'] if c['problem_id'] == row['selected_problem_id'])
                reference = {**item['shared'], 'graph': old_config['reference_graph']}
                row.update(agrees_with_bplus=candidate['problem_id'] == recommend_foundational_bplus(item['shared'], old_config['bplus'])['problem_id'],
                           reference_soft_remediation=candidate['skill_id'] in relevant_weak_sources(reference, old_config['bplus']),
                           selected_mastery=item['shared']['state']['skills'][candidate['skill_id']],
                           selected_train_success_rate=candidate['difficulty'], selected_support=candidate['support'])
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
    except (OSError, ValueError, KeyError, TypeError) as error:
        summary.update(agent_status='blocked_integrity_or_preflight', model_calls_completed=len(rows),
                       completed_journal_attempts=journal.call_index, error_type=type(error).__name__, error_message=str(error))
        save(OUTPUT, summary)
        raise
    save(PRIVATE / 'runs.json', rows)
    summary.update(agent_status='completed_validation_not_test', model_calls_completed=len(rows),
                   cohorts=aggregate(rows, schedule, cohorts), private_runs_sha256=digest(PRIVATE / 'runs.json'),
                   journal_sha256=digest(PRIVATE / 'calls.jsonl'), runtime_identity_unchanged=True)
    save(OUTPUT, summary)


if __name__ == '__main__':
    main()
