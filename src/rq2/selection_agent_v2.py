"""Independent metadata selection; no B+ winner or exact B+ ranking objective."""

from copy import deepcopy
import json
import time

from src.rq2.agent import Recommendation
from src.rq2.foundational_validation import checked_telemetry, make_agent_request
from src.rq2.runtime_journal import RuntimeIntegrityError


def selection_request(shared, config, enum_ids):
    if config['stage'] != 'validation_development_not_lock_c' or config['test_access'] is not False:
        raise ValueError('VALIDATION selection development only')
    ids = {c['problem_id'] for c in shared['candidates']}
    if len(enum_ids) != len(ids) or set(enum_ids) != ids:
        raise ValueError('enum must contain each candidate ID exactly once')
    request, _ = make_agent_request(shared, config['agent'])
    request['format']['properties']['problem_id']['enum'] = list(enum_ids)
    request['format']['properties']['reason']['maxLength'] = config['reason_max_chars']
    request['messages'][0]['content'] += (
        ' Choose a practice opportunity using the supplied estimated mastery, optional '
        'curriculum links, and TRAIN item statistics. Consider weaker estimated skills '
        'and a suitable level of challenge, and explain your tradeoff briefly in Vietnamese. '
        'There is no supplied gold answer or required lexicographic ranking to reproduce. '
        'TRAIN success rate is not this student\'s success probability. Ground numeric '
        'statements in the supplied values. Express estimates as estimates; do not claim '
        'confirmed deficits, causal prerequisite relations, or improved learning.'
    )
    runtime = config['agent']
    bound = sum(len(m['content'].encode('utf-8')) for m in request['messages'])
    bound += len(json.dumps(request['format']).encode('utf-8')) + runtime['template_token_reserve']
    if bound + runtime['num_predict'] > runtime['num_ctx']:
        raise ValueError('selection context exceeded; no truncation')
    return request, bound


def run_selection(shared, config, enum_ids, call):
    row = {'request': None, 'raw_response': None, 'candidate_valid': False,
           'selected_problem_id': None, 'reason': None, 'selected_position': None,
           'selected_enum_position': None, 'prompt_eval_count': None, 'eval_count': None,
           'error_stage': None, 'error_type': None, 'error_message': None,
           'reason_semantically_verified': False}
    start, stage = time.perf_counter(), 'request'
    try:
        request, bound = selection_request(shared, config, enum_ids)
        row['request'] = deepcopy(request)
        stage = 'transport'
        response = call(request, timeout=config['agent']['timeout_seconds'])
        row['raw_response'] = deepcopy(response)
        stage = 'telemetry'
        row['prompt_eval_count'] = response.get('prompt_eval_count')
        row['eval_count'] = response.get('eval_count')
        checked_telemetry(response, config['agent'], bound)
        stage = 'output_contract'
        parsed = Recommendation.model_validate_json(response['message']['content'])
        if not parsed.reason.strip() or len(parsed.reason) > config['reason_max_chars']:
            raise ValueError('blank or overlong reason')
        ids = [c['problem_id'] for c in shared['candidates']]
        if parsed.problem_id not in ids:
            raise ValueError('selected problem is outside candidate set')
        row.update(candidate_valid=True, selected_problem_id=parsed.problem_id, reason=parsed.reason,
                   selected_position=ids.index(parsed.problem_id), selected_enum_position=enum_ids.index(parsed.problem_id))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        row.update(error_stage='runtime_integrity' if isinstance(error, RuntimeIntegrityError) else stage,
                   error_type=type(error).__name__, error_message=str(error))
    row['latency_seconds'] = time.perf_counter() - start
    return row
