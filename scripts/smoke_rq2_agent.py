"""Five synthetic local-LLM feasibility probes; never RQ2 study results."""

from pathlib import Path
import json
import statistics
import sys
import time

import psutil
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rq2.agent import Recommendation, build_agent_request, validate_agent_output
from src.rq2.ollama_client import call_local_ollama


def synthetic_inputs(mastery):
    graph = {'skills': ['11', '12'],
             'edges': [{'prerequisite': '11', 'target': '12',
                        'basis': 'prototype_assumption',
                        'rationale': 'synthetic smoke-test edge'}],
             'status': 'synthetic_feasibility_only'}
    state = {'state_type': 'BKT_p_mastery',
             'skills': {'11': mastery, '12': round(1 - mastery / 2, 3)},
             'history_length': 12}
    candidates = [
        {'problem_id': 'synthetic_1', 'skill_id': '11', 'difficulty': .3, 'support': 20},
        {'problem_id': 'synthetic_2', 'skill_id': '11', 'difficulty': .6, 'support': 12},
        {'problem_id': 'synthetic_3', 'skill_id': '12', 'difficulty': .5, 'support': 15},
        {'problem_id': 'synthetic_4', 'skill_id': '12', 'difficulty': .8, 'support': 10},
    ]
    return state, graph, candidates


def ollama_rss_bytes():
    total = 0
    for process in psutil.process_iter(['name', 'memory_info']):
        name = (process.info['name'] or '').lower()
        if name.startswith('ollama') and process.info['memory_info'] is not None:
            total += process.info['memory_info'].rss
    return total


def main(model='gemma3:1b', timeout=90):
    latencies = []
    json_valid = 0
    candidate_valid = 0
    errors = []
    peak_ollama_rss = 0
    for index, mastery in enumerate((.15, .3, .5, .7, .9), start=1):
        state, graph, candidates = synthetic_inputs(mastery)
        request = build_agent_request(state, graph, candidates, model=model,
                                      temperature=0, num_ctx=2048)
        start = time.perf_counter()
        try:
            content = call_local_ollama(request, timeout=timeout)
            latencies.append(time.perf_counter() - start)
            Recommendation.model_validate_json(content)
            json_valid += 1
            validate_agent_output(content, candidates)
            candidate_valid += 1
        except (ValidationError, ValueError, OSError) as error:
            errors.append({'probe': index, 'error_type': type(error).__name__,
                           'message': str(error)[:200]})
        peak_ollama_rss = max(peak_ollama_rss, ollama_rss_bytes())
    result = {
        'stage': 'synthetic_hardware_feasibility_not_rq2_results',
        'model': model, 'n_synthetic_probes': 5,
        'schema_valid_count': json_valid,
        'candidate_valid_count': candidate_valid,
        'latency_seconds_mean_successful': statistics.mean(latencies) if latencies else None,
        'latency_seconds_max_successful': max(latencies) if latencies else None,
        'ollama_process_rss_peak_observed_bytes': peak_ollama_rss,
        'memory_measurement_note': 'process RSS sampled between probes; not a GPU VRAM or true peak measurement',
        'errors': errors,
    }
    output = ROOT / 'artifacts/tables/rq2_agent_hardware_pilot.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result, indent=2, allow_nan=False))
    return result


if __name__ == '__main__':
    main()
