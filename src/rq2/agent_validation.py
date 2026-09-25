"""Run a local Agent on fixed VALIDATION scenarios and report aggregates."""

import json
import statistics
import time

from pydantic import ValidationError

from src.rq2.agent import Recommendation, build_agent_request, validate_agent_output
from src.rq2.ollama_client import call_local_ollama
from src.rq2.policy import recommend_bplus


def run_validation_cases(cases, *, model, temperature=0, num_ctx=2048,
                         timeout=90, call=call_local_ollama):
    """One Agent run per validation scenario; records may contain local IDs."""
    if not cases:
        raise ValueError('nonempty validation scenarios required')
    runs = []
    for case in cases:
        if not str(case['scenario_id']).startswith('validation_'):
            raise ValueError('only validation scenario IDs are permitted')
        shared = case['shared_input']
        if (case['state'] != shared['state'] or
                case['bplus'] != recommend_bplus(shared['state'], shared['graph'],
                                                 shared['candidates'])):
            raise ValueError('B+ and Agent must use the same state and candidate list')
        request = build_agent_request(shared['state'], shared['graph'], shared['candidates'],
                                      model=model, temperature=temperature, num_ctx=num_ctx)
        record = {'scenario_id': case['scenario_id'], 'student_id': case['student_id'],
                  'json_syntax_valid': False, 'schema_valid': False,
                  'candidate_valid': False,
                  'agrees_with_bplus': False, 'selected_problem_id': None,
                  'latency_seconds': None, 'error_type': None}
        start = time.perf_counter()
        try:
            content = call(request, timeout=timeout)
            record['latency_seconds'] = time.perf_counter() - start
            json.loads(content)
            record['json_syntax_valid'] = True
            Recommendation.model_validate_json(content)
            record['schema_valid'] = True
            selected = validate_agent_output(content, shared['candidates'])
            record['candidate_valid'] = True
            record['selected_problem_id'] = selected['problem_id']
            record['agrees_with_bplus'] = selected['problem_id'] == case['bplus']['problem_id']
        except (ValidationError, ValueError, OSError, TimeoutError) as error:
            record['latency_seconds'] = time.perf_counter() - start
            record['error_type'] = type(error).__name__
        runs.append(record)
    return runs


def summarize_agent_validation(runs):
    """No per-student or per-scenario values leave the ignored run artifact."""
    if not runs:
        raise ValueError('nonempty runs required')
    latencies = [run['latency_seconds'] for run in runs if run['latency_seconds'] is not None]
    count = len(runs)
    json_syntax_valid = sum(run['json_syntax_valid'] for run in runs)
    schema_valid = sum(run['schema_valid'] for run in runs)
    candidate_valid = sum(run['candidate_valid'] for run in runs)
    errors = sum(run['error_type'] is not None for run in runs)
    return {
        'stage': 'rq2_validation_development_not_final_test',
        'test_opened': False,
        'n_scenarios': count,
        'n_students': len({run['student_id'] for run in runs}),
        'json_syntax_valid_count': json_syntax_valid,
        'json_syntax_valid_rate': json_syntax_valid / count,
        'schema_valid_count': schema_valid,
        'schema_valid_rate': schema_valid / count,
        'candidate_valid_count': candidate_valid,
        'candidate_valid_rate': candidate_valid / count,
        'agreement_with_bplus_count': sum(run['agrees_with_bplus'] for run in runs),
        'error_count': errors,
        'error_rate': errors / count,
        'timeout_count': sum(run['error_type'] == 'TimeoutError' for run in runs),
        'latency_seconds_mean': statistics.mean(latencies) if latencies else None,
        'latency_seconds_median': statistics.median(latencies) if latencies else None,
        'latency_seconds_max': max(latencies) if latencies else None,
    }
