"""Bounded VALIDATION explanation experiment with a deterministic template baseline."""

from copy import deepcopy
import argparse
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_foundational_rq2_validation import call_chat, digest, local_json, read_json, save
from scripts.run_foundational_rq2_agent_calculator1 import prepare_calculator, OUTPUT as CALCULATOR_OUTPUT, PRIVATE as CALCULATOR_PRIVATE
from src.rq2.foundational_validation import checked_telemetry
from src.rq2.grounded_explanation import assess_explanation, explanation_packet, explanation_request, render_verified, run_explanation, template_explanation

CONFIG = ROOT / 'configs/foundationalassist_v4_rq2_explanation1.json'
PRIVATE = ROOT / 'data/processed/foundationalassist_v4/rq2_validation/explanation1'
OUTPUT = ROOT / 'artifacts/tables/foundationalassist_v4_rq2_explanation1_summary.json'


def prepare_explanation():
    config = read_json(CONFIG)
    if config['stage'] != 'validation_development_not_lock_c' or config['test_access'] is not False:
        raise ValueError('VALIDATION explanation development only')
    _, old_config, schedule, cohorts, pins = prepare_calculator()
    completed = read_json(CALCULATOR_OUTPUT)
    if completed['agent_status'] != 'completed_validation_not_test' or completed['test_opened'] is not False:
        raise ValueError('completed previous calculator study required')
    for relative, expected in completed['input_sha256'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('previous calculator inputs changed')
    if digest(CALCULATOR_PRIVATE / 'runs.json') != completed['private_runs_sha256']:
        raise ValueError('previous calculator calls changed')
    if config['model'] != completed['model'] or config['model_digest'] != completed['model_digest']:
        raise ValueError('keep installed previous model')
    if len(schedule) != config['new_calls']:
        raise ValueError('fixed explanation call count required')
    pins.update(completed['input_sha256'])
    for p in (CONFIG, Path(__file__), ROOT / 'src/rq2/grounded_explanation.py',
              ROOT / 'reports/rq2_grounded_explanation_design.md', CALCULATOR_OUTPUT, CALCULATOR_PRIVATE / 'runs.json'):
        pins[p.relative_to(ROOT).as_posix()] = digest(p)
    baselines = []
    for item in schedule:
        packet, factor = explanation_packet(item['shared'], old_config['bplus'])
        template = template_explanation(packet, factor)
        parsed, checks = assess_explanation(json.dumps(template), packet, factor, config['draft_max_chars'])
        text = render_verified(parsed, packet, checks)
        explanation_request(packet, config, item['enum_ids'])
        baselines.append({**{k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant')},
                          'fixed_problem_id': packet['selected_problem_id'], 'expected_factor': factor,
                          'accepted': all(checks.values()), 'rendered_explanation': text})
    return config, old_config['bplus'], schedule, cohorts, pins, baselines


def aggregate(rows, baselines, cohorts, variants):
    from collections import Counter
    fields = ('schema_valid', 'fixed_id_consistent', 'decisive_factor_correct', 'citations_valid', 'citation_coverage', 'accepted')
    result = {}
    for cohort, source in cohorts.items():
        result[cohort] = {'n_students': source['n_students'], 'variants': {}}
        for variant in variants:
            group = [r for r in rows if r['cohort'] == cohort and r['graph_variant'] == variant]
            template = [r for r in baselines if r['cohort'] == cohort and r['graph_variant'] == variant]
            students = {}
            for row in group:
                students.setdefault(row['student_id'], []).append(row)
            metric = {'n_calls': len(group), 'n_students': len(students),
                      **{key + '_count': sum(r[key] for r in group) for key in fields},
                      'error_stage_counts': dict(Counter(r['error_stage'] for r in group if r['error_stage'])),
                      'template_valid_count': sum(r['accepted'] for r in template),
                      'bplus_selection_changed_students': sum(len({r['fixed_problem_id'] for r in rs}) > 1 for rs in students.values()),
                      'complete_three_repetition_students': sum(len(rs) == 3 for rs in students.values()),
                      'all_three_explanations_accepted_students': sum(len(rs) == 3 and all(r['accepted'] for r in rs) for rs in students.values()),
                      'expected_factor_counts': dict(Counter(r['expected_factor'] for r in group)),
                      'latency_seconds_mean': statistics.mean(r['latency_seconds'] for r in group)}
            for key in ('prompt_eval_count', 'eval_count'):
                values = [r[key] for r in group if type(r[key]) is int]
                metric[key + '_max'] = max(values) if values else None
            result[cohort]['variants'][variant] = metric
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-agent', action='store_true')
    args = parser.parse_args()
    if (PRIVATE / 'runs.json').exists() or (PRIVATE / 'runs.partial.json').exists():
        raise ValueError('explanation calls exist; never overwrite or silently repeat')
    config, policy, schedule, cohorts, pins, baselines = prepare_explanation()
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
            counts.append(checked_telemetry(response, {**config['agent'], 'num_ctx': factor * config['agent']['num_ctx']}, bound))
        if counts[0] != counts[1]:
            raise ValueError('explanation context counts differ')
        probes.append({'graph_variant': variant, 'prompt_eval_count': counts[0], 'double_context_prompt_eval_count': counts[1], 'byte_guard': bound})
    summary.update(agent_status='in_progress', context_probe={'probes': probes, 'probe_calls_not_study': 4})
    save(OUTPUT, summary)
    rows = []
    for item in schedule:
        row = run_explanation(item['shared'], policy, config, item['enum_ids'], call_chat)
        row.update({k: item[k] for k in ('cohort', 'scenario_id', 'student_id', 'repetition', 'graph_variant', 'permutation')})
        rows.append(row)
        save(PRIVATE / 'runs.partial.json', rows)
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
