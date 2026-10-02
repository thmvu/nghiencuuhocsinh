"""Versioned calculator-assisted rule execution, without handing over a winner."""

from copy import deepcopy
import json
import time
from urllib.error import HTTPError
from src.rq2.agent import Recommendation
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus

from src.rq2.agent_revision import revision_request
from src.rq2.foundational_validation import relevant_weak_sources


def candidate_evidence(shared, policy):
    """Derived facts in DISPLAY order; no sorting, rank or chosen ID."""
    sources = relevant_weak_sources(shared, policy)
    return [{'problem_id': c['problem_id'],
             'weak_linked_source': c['skill_id'] in sources,
             'train_success_gap': abs(c['difficulty'] - policy['target_train_success_rate']),
             'train_support': c['support']}
            for c in shared['candidates']]


def recommend_calculator_bplus(shared, policy, evidence):
    """B+ receives the SAME facts; preserve its original binary-float ordering."""
    if evidence != candidate_evidence(shared, policy):
        raise ValueError('calculator evidence differs from shared inputs')
    winner = min(evidence, key=lambda e: (0 if e['weak_linked_source'] else 1,
                                         e['train_success_gap'], -e['train_support'],
                                         e['problem_id']))
    return dict(next(c for c in shared['candidates'] if c['problem_id'] == winner['problem_id']))


def calculator_request(shared, config, enum_ids):
    request, _ = revision_request(shared, config, 'schema_and_objective', enum_ids)
    payload = json.loads(request['messages'][1]['content'])
    payload['calculator_evidence'] = candidate_evidence(shared, config['bplus'])
    request['messages'][1]['content'] = json.dumps(payload, ensure_ascii=False)
    request['messages'][0]['content'] += (
        ' calculator_evidence contains computed facts for EVERY candidate in the same '
        'display order, not a ranking. Apply the preceding lexicographic rule: prefer '
        'weak_linked_source=true, then smaller train_success_gap, then larger '
        'train_support, then smaller problem_id. Do not recompute or round these facts. '
        'These are rule-execution aids, not evidence of educational benefit.'
    )
    runtime = config['agent']
    bound = sum(len(m['content'].encode('utf-8')) for m in request['messages'])
    bound += len(json.dumps(request['format']).encode('utf-8')) + runtime['template_token_reserve']
    if bound + runtime['num_predict'] > runtime['num_ctx']:
        raise ValueError('calculator context budget exceeded; no truncation')
    return request, bound


# Logging contract copied from frozen revision1; earlier study code is unchanged.
def run_calculator_call(shared, config, enum_ids, call):
    """Keep raw diagnostic data private; no repair, retry or fallback selection."""
    record = {'policy': 'Agent_calculator1', 'schema_valid': False, 'candidate_valid': False,
              'selected_problem_id': None, 'selected_position': None, 'selected_enum_position': None,
              'agrees_with_bplus': False, 'soft_source_remediation_selected': False,
              'prompt_eval_count': None, 'eval_count': None, 'done_reason': None,
              'request': None, 'raw_response': None, 'error_type': None,
              'error_stage': None, 'error_message': None, 'http_status': None,
              'http_body': None, 'enum_ids': list(enum_ids)}
    start = time.perf_counter()
    stage = 'request'
    try:
        request, bound = calculator_request(shared, config, enum_ids)
        record['request'] = deepcopy(request)
        stage = 'transport'
        response = call(request, timeout=config['agent']['timeout_seconds'])
        record['raw_response'] = deepcopy(response)
        stage = 'response'
        if not isinstance(response, dict):
            raise ValueError('response must be an object')
        # Preserve telemetry even when generation ends at the output limit.
        for key in ('prompt_eval_count', 'eval_count', 'done_reason'):
            record[key] = response.get(key)
        for key in ('prompt_eval_count', 'eval_count'):
            if type(record[key]) is not int or record[key] < 0:
                record[key] = None
        stage = 'telemetry'
        checked_telemetry(response, config['agent'], bound)
        stage = 'schema'
        content = response['message']['content']
        selected = Recommendation.model_validate_json(content)
        record['schema_valid'] = True
        stage = 'reason'
        if not selected.reason.strip():
            raise ValueError('Agent reason is blank')
        if len(selected.reason) > config['reason_max_chars']:
            raise ValueError('Agent reason exceeds the schema length limit')
        stage = 'candidate_membership'
        by_id = {c['problem_id']: c for c in shared['candidates']}
        if selected.problem_id not in by_id:
            raise ValueError('selected ID is outside the supplied candidates')
        record['candidate_valid'] = True
        record['selected_problem_id'] = selected.problem_id
        record['selected_position'] = next(i for i, c in enumerate(shared['candidates']) if c['problem_id'] == selected.problem_id)
        record['selected_enum_position'] = enum_ids.index(selected.problem_id)
        record['agrees_with_bplus'] = selected.problem_id == recommend_foundational_bplus(shared, config['bplus'])['problem_id']
        reference = {**shared, 'graph': config['reference_graph']}
        record['soft_source_remediation_selected'] = by_id[selected.problem_id]['skill_id'] in relevant_weak_sources(reference, config['bplus'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        record['error_type'] = type(error).__name__
        record['error_stage'] = stage
        record['error_message'] = str(error)
        if isinstance(error, HTTPError):
            record['http_status'] = error.code
            record['http_body'] = error.read().decode('utf-8', errors='replace')
    record['latency_seconds'] = time.perf_counter() - start
    return record
