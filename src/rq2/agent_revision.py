"""Versioned Agent repair; original requests and study outputs stay frozen."""

from copy import deepcopy
import json
import time
from urllib.error import HTTPError

from src.rq2.agent import Recommendation
from src.rq2.foundational_validation import (
    checked_telemetry, make_agent_request,
    recommend_foundational_bplus, relevant_weak_sources,
)


def revision_request(shared, config, arm, enum_ids):
    if config.get('stage') != 'validation_development_not_lock_c' or config.get('test_access') is not False:
        raise ValueError('VALIDATION development only')
    if arm not in ('schema_only', 'schema_and_objective'):
        raise ValueError('unknown revision arm')
    ids = {c['problem_id'] for c in shared['candidates']}
    if len(enum_ids) != len(ids) or set(enum_ids) != ids:
        raise ValueError('enum must contain exactly the candidate IDs once each')
    runtime = config['agent']
    request, _ = make_agent_request(shared, runtime)
    request['format']['properties']['problem_id']['enum'] = list(enum_ids)
    request['format']['properties']['reason']['maxLength'] = config['reason_max_chars']
    if arm == 'schema_and_objective':
        policy = config['bplus']
        request['messages'][0]['content'] += (
            ' Selection objective: compare ALL candidates using this lexicographic rule. '
            f"First prefer a source skill with mastery below {policy['source_weak_threshold']} "
            'if a supplied direct edge links it to a target skill with mastery below '
            f"{policy['target_weak_threshold']} and that target has a candidate in this list. "
            'Use only supplied edges, never inferred curriculum relations. If no candidate '
            'has this signal (including when edges are empty), all candidates tie on this step. '
            f"Next minimize absolute distance of TRAIN success rate from {policy['target_train_success_rate']}. "
            'Next prefer larger TRAIN support, then lexicographically smaller problem_id. '
            'Display position and schema enum order must never break ties. '
            'Give a short reason citing the selected skill and relevant numeric evidence. '
            'Do not output a long analysis or claim pedagogical benefit.'
        )
    payload_bytes = sum(len(m['content'].encode('utf-8')) for m in request['messages'])
    payload_bytes += len(json.dumps(request['format']).encode('utf-8'))
    bound = payload_bytes + runtime['template_token_reserve']
    if bound + runtime['num_predict'] > runtime['num_ctx']:
        raise ValueError('revision context budget exceeded; no truncation')
    return request, bound


def run_revision_call(shared, config, arm, enum_ids, call):
    """Keep raw diagnostic data private; no repair, retry or fallback selection."""
    record = {'policy': 'Agent_' + arm, 'schema_valid': False, 'candidate_valid': False,
              'selected_problem_id': None, 'selected_position': None, 'selected_enum_position': None,
              'agrees_with_bplus': False, 'soft_source_remediation_selected': False,
              'prompt_eval_count': None, 'eval_count': None, 'done_reason': None,
              'request': None, 'raw_response': None, 'error_type': None,
              'error_stage': None, 'error_message': None, 'http_status': None,
              'http_body': None, 'enum_ids': list(enum_ids)}
    start = time.perf_counter()
    stage = 'request'
    try:
        request, bound = revision_request(shared, config, arm, enum_ids)
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
