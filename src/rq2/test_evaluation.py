"""Frozen RQ2 TEST protocol. No IO occurs in this module."""

import json
import math
import statistics
import time
from numbers import Integral

import numpy as np
import pandas as pd
from pydantic import ValidationError

from src.rq2.agent import Recommendation, build_agent_request, validate_agent_output
from src.rq2.candidates import generate_candidates
from src.rq2.ollama_client import call_local_ollama
from src.rq2.policy import recommend_bplus
from src.rq2.state import bkt_mastery_snapshot


FROZEN_CODE = ('src/rq2/state.py', 'src/rq2/scenarios.py', 'src/rq2/graph.py',
               'src/rq2/candidates.py', 'src/rq2/policy.py', 'src/rq2/agent.py',
               'src/rq2/ollama_client.py', 'src/rq2/test_evaluation.py',
               'scripts/evaluate_rq2_test.py')


def validate_lock_c(lock, digest):
    """Check the complete preflight manifest before a caller reads TEST rows."""
    try:
        if (lock['stage'] != 'C' or lock['gate_c'] != 'RQ2 PRE-TEST CHECKLIST PASS' or
                lock['test_opened'] is not False or lock['test_policy'] != 'one_final_evaluation_no_test_tuning'):
            raise ValueError('RQ2 TEST gate is not locked')
        expected = lock['frozen_artifacts_sha256']
        required = {'configs/protocol_b.json', 'data/processed/test.parquet',
                    lock['bkt_checkpoint_path'], lock['graph_path'], lock['candidate_pool_path'],
                    *FROZEN_CODE}
        if not required <= set(expected):
            raise ValueError('incomplete RQ2 frozen artifact manifest')
        for path in required:
            if digest(path) != expected[path]:
                raise ValueError(f'RQ2 frozen artifact changed: {path}')
        if expected['data/processed/test.parquet'] != lock['test_input_sha256']:
            raise ValueError('TEST partition hash mismatch')
        protocol = lock['scenario_protocol']
        agent = lock['agent']
        bootstrap = lock['bootstrap']
        if (protocol['n_students'] != 50 or protocol['min_history'] < 1 or
                protocol['n_candidates'] < 1 or not isinstance(protocol['seed'], int) or
                bootstrap['unit'] != 'student' or bootstrap['iterations'] < 1 or
                not isinstance(bootstrap['seed'], int) or
                agent['runs_per_scenario'] != 3 or agent['repair_attempts'] != 0 or
                not agent['model'] or not agent['model_digest'] or not agent['quantization'] or
                agent['temperature'] != 0 or agent['seed_policy'] != 'no_seed_option' or
                agent['timeout_seconds'] <= 0):
            raise ValueError('invalid frozen RQ2 test protocol')
        return lock
    except (KeyError, TypeError) as error:
        raise ValueError('incomplete RQ2 Lock C') from error


def sample_test_scenarios(test, bkt, graph, pool, *, n_students=50, seed=42,
                          min_history=5, n_candidates=8, snapshot=bkt_mastery_snapshot):
    """One random prefix per distinct TEST student, with no future-row exposure."""
    needed = {'user_id', 'order_id', 'skill_id', 'correct', 'split'}
    if (not isinstance(test, pd.DataFrame) or test.empty or not test.columns.is_unique or
            not needed <= set(test.columns) or test[list(needed)].isna().any().any() or
            not test.split.eq('test').all() or not test.correct.isin([0, 1]).all()):
        raise ValueError('TEST-only binary history required')
    if (isinstance(n_students, bool) or not isinstance(n_students, Integral) or n_students < 1 or
            isinstance(min_history, bool) or not isinstance(min_history, Integral) or min_history < 1 or
            isinstance(n_candidates, bool) or not isinstance(n_candidates, Integral) or n_candidates < 1 or
            isinstance(seed, bool) or not isinstance(seed, Integral)):
        raise ValueError('invalid scenario sampling protocol')
    order = pd.to_numeric(test.order_id, errors='coerce')
    if not np.isfinite(order).all():
        raise ValueError('finite chronology required')
    frame = test.assign(order_id=order)
    if frame.duplicated(['user_id', 'order_id']).any():
        raise ValueError('duplicate student chronology')
    groups = {student: group.sort_values('order_id', kind='stable')
              for student, group in frame.groupby('user_id', sort=False)
              if len(group) >= min_history}
    students = sorted(groups, key=lambda value: (str(type(value)), str(value)))
    if len(students) < n_students:
        raise ValueError('insufficient eligible TEST students')
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(students), size=n_students, replace=False)
    cases = []
    for index, student_index in enumerate(chosen):
        student = students[int(student_index)]
        sequence = groups[student]
        length = int(rng.integers(min_history, len(sequence) + 1))
        prefix = sequence.iloc[:length]
        state = snapshot(bkt, prefix, skill_universe=graph['skills'], expected_split='test')
        candidates = generate_candidates(state, graph, pool, n_candidates=n_candidates)
        if len(candidates) != n_candidates:
            raise ValueError('candidate generator did not fill frozen set')
        shared = {'state': state, 'graph': graph, 'candidates': candidates}
        cases.append({'scenario_id': f'test_{index + 1:03d}', 'student_id': student,
                      'cutoff_order_id': sequence.order_id.iloc[length - 1],
                      'state': state, 'shared_input': shared,
                      'bplus': recommend_bplus(state, graph, candidates)})
    return cases


def run_test_cases(cases, *, model, runs_per_scenario=3, temperature=0,
                   num_ctx=2048, timeout=90, call=call_local_ollama):
    """Run B+ once per case and Agent exactly three times on identical inputs."""
    if not cases or runs_per_scenario != 3 or len({c['student_id'] for c in cases}) != len(cases):
        raise ValueError('one scenario per TEST student and three runs required')
    runs = []
    for case in cases:
        if not str(case['scenario_id']).startswith('test_'):
            raise ValueError('TEST scenario ID required')
        shared = case['shared_input']
        if (case['state'] != shared['state'] or
                case['bplus'] != recommend_bplus(shared['state'], shared['graph'], shared['candidates'])):
            raise ValueError('B+ and Agent inputs differ')
        request = build_agent_request(shared['state'], shared['graph'], shared['candidates'],
                                      model=model, temperature=temperature, num_ctx=num_ctx)
        for repeat in range(runs_per_scenario):
            record = {'scenario_id': case['scenario_id'], 'student_id': case['student_id'],
                      'repeat': repeat + 1, 'json_syntax_valid': False,
                      'schema_valid': False, 'candidate_valid': False,
                      'agrees_with_bplus': False, 'selected_problem_id': None,
                      'latency_seconds': None, 'error_type': None}
            start = time.perf_counter()
            try:
                content = call(request, timeout=timeout)
                json.loads(content)
                record['json_syntax_valid'] = True
                Recommendation.model_validate_json(content)
                record['schema_valid'] = True
                selected = validate_agent_output(content, shared['candidates'])
                record['candidate_valid'] = True
                record['selected_problem_id'] = selected['problem_id']
                record['agrees_with_bplus'] = selected['problem_id'] == case['bplus']['problem_id']
            except (ValidationError, ValueError, TypeError, OSError, TimeoutError) as error:
                record['error_type'] = type(error).__name__
            record['latency_seconds'] = time.perf_counter() - start
            runs.append(record)
    return runs


def summarize_test_runs(runs, *, expected_students=50, runs_per_scenario=3,
                        bootstrap_iterations=1000, bootstrap_seed=42):
    """Emit aggregate operational metrics; students, not runs, are units."""
    groups = {}
    for run in runs:
        groups.setdefault(run['student_id'], []).append(run)
    if (len(groups) != expected_students or len(runs) != expected_students * runs_per_scenario or
            any(len(group) != runs_per_scenario or len({r['scenario_id'] for r in group}) != 1 or
                {r['repeat'] for r in group} != set(range(1, runs_per_scenario + 1))
                for group in groups.values())):
        raise ValueError('incomplete repeated-run TEST design')
    count = len(runs)
    latency = [r['latency_seconds'] for r in runs]
    if any(v is None or not math.isfinite(v) or v < 0 for v in latency):
        raise ValueError('invalid run latency')
    consistent = sum(all(r['candidate_valid'] for r in group) and
                     len({r['selected_problem_id'] for r in group}) == 1
                     for group in groups.values())
    if (isinstance(bootstrap_iterations, bool) or
            not isinstance(bootstrap_iterations, Integral) or bootstrap_iterations < 1 or
            isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, Integral)):
        raise ValueError('invalid student bootstrap protocol')
    student_rates = np.asarray([sum(r['candidate_valid'] for r in group) / runs_per_scenario
                                for group in groups.values()], dtype=float)
    rng = np.random.default_rng(bootstrap_seed)
    indices = rng.integers(0, len(groups), size=(bootstrap_iterations, len(groups)))
    replicates = student_rates[indices].mean(axis=1)
    ci_low, ci_high = np.quantile(replicates, [.025, .975]).tolist()
    return {
        'stage': 'rq2_final_test', 'test_opened': True,
        'n_students': len(groups), 'n_scenarios': len(groups), 'n_runs': count,
        'runs_per_scenario': runs_per_scenario,
        'json_syntax_valid_count': sum(r['json_syntax_valid'] for r in runs),
        'json_syntax_valid_rate': sum(r['json_syntax_valid'] for r in runs) / count,
        'schema_valid_count': sum(r['schema_valid'] for r in runs),
        'schema_valid_rate': sum(r['schema_valid'] for r in runs) / count,
        'candidate_valid_count': sum(r['candidate_valid'] for r in runs),
        'candidate_valid_rate': sum(r['candidate_valid'] for r in runs) / count,
        'candidate_valid_student_bootstrap_ci_low': ci_low,
        'candidate_valid_student_bootstrap_ci_high': ci_high,
        'candidate_valid_bootstrap_iterations': bootstrap_iterations,
        'candidate_valid_bootstrap_seed': bootstrap_seed,
        'agreement_with_bplus_count': sum(r['agrees_with_bplus'] for r in runs),
        'timeout_count': sum(r['error_type'] == 'TimeoutError' for r in runs),
        'error_count': sum(r['error_type'] is not None for r in runs),
        'latency_seconds_mean': statistics.mean(latency),
        'latency_seconds_median': statistics.median(latency),
        'latency_seconds_max': max(latency),
        'latency_seconds_p95': float(np.quantile(latency, .95)),
        'consistent_students': consistent,
        'within_scenario_consistency_rate': consistent / len(groups),
        'independent_unit': 'student',
        'quality_claim': 'none_without_blind_rubric',
    }
