"""Fixed B+ choice, checked citations and controlled explanation rendering."""

from copy import deepcopy
import json
import time
from typing import Literal
from urllib.error import HTTPError

from pydantic import BaseModel, ConfigDict, Field

from src.rq2.calculator_agent import candidate_evidence
from src.rq2.foundational_validation import checked_telemetry, recommend_foundational_bplus

FACTORS = ('source_signal', 'success_gap', 'support', 'problem_id', 'single_candidate')


class Explanation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    problem_id: str = Field(min_length=1)
    decisive_factor: Literal['source_signal', 'success_gap', 'support', 'problem_id', 'single_candidate']
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    draft: str = Field(min_length=1)


def explanation_packet(shared, policy):
    """Trace frozen B+ lexicographic stages; catalog contains true facts only."""
    chosen = recommend_foundational_bplus(shared, policy)
    facts = candidate_evidence(shared, policy)
    remaining = list(facts)
    stages = []
    decisive = 'single_candidate' if len(remaining) == 1 else None
    keys = (('source_signal', lambda e: 0 if e['weak_linked_source'] else 1),
            ('success_gap', lambda e: e['train_success_gap']),
            ('support', lambda e: -e['train_support']),
            ('problem_id', lambda e: e['problem_id']))
    for factor, key in keys:
        before = len(remaining)
        best = min(key(e) for e in remaining)
        remaining = [e for e in remaining if key(e) == best]
        stages.append({'factor': factor, 'before': before, 'after': len(remaining)})
        if decisive is None and len(remaining) == 1:
            decisive = factor
    if len(remaining) != 1 or remaining[0]['problem_id'] != chosen['problem_id']:
        raise ValueError('explanation trace differs from frozen B+')
    mastery = shared['state']['skills'][chosen['skill_id']]
    catalog = [
        {'id': 'selected_item', 'text': f"B+ đã chọn bài {chosen['problem_id']}, kỹ năng {chosen['skill_id']}."},
        {'id': 'state_estimate', 'text': f"Mastery BKT của kỹ năng này là {mastery:.6f}; đây là ước lượng trạng thái tiềm ẩn, không phải kiến thức thực tế đã đo hoặc xác suất làm đúng bài."},
        {'id': 'train_proxy', 'text': f"Tỷ lệ đúng trên TRAIN của bài là {chosen['difficulty']:.6f}, với {chosen['support']} tương tác TRAIN; đây là thống kê của bài, không phải dự đoán cho học sinh hiện tại."},
        {'id': 'graph_assumption', 'text': 'Graph là giả định tiến trình chương trình do tác giả đề xuất, chưa được chuyên gia xác nhận; cạnh không phải điều kiện tiên quyết mastery đã kiểm chứng.'},
        {'id': 'learning_limit', 'text': 'Lựa chọn và lời giải thích này không chứng minh cải thiện kết quả học tập.'},
    ]
    labels = {'source_signal': 'ưu tiên nguồn yếu liên kết trực tiếp tới đích yếu có bài trong danh sách',
              'success_gap': f"độ gần tỷ lệ đúng TRAIN với mốc {policy['target_train_success_rate']}",
              'support': 'support TRAIN lớn hơn', 'problem_id': 'ID theo thứ tự từ điển'}
    for step in stages:
        catalog.append({'id': 'rank_' + step['factor'],
                        'text': f"Bước {labels[step['factor']]} giữ {step['after']}/{step['before']} ứng viên còn lại."})
    if decisive == 'single_candidate':
        catalog.append({'id': 'rank_single_candidate', 'text': 'Danh sách chỉ có một ứng viên; không có so sánh xếp hạng giữa các bài.'})
    selected_fact = next(e for e in facts if e['problem_id'] == chosen['problem_id'])
    packet = {'selected_problem_id': chosen['problem_id'], 'selected_skill_id': chosen['skill_id'],
              'selected_numeric_evidence': selected_fact, 'selection_trace': stages,
              'initial_candidate_count': len(facts),
              'graph_has_edges': bool(shared['graph']['edges']), 'fact_catalog': catalog}
    return packet, decisive


def required_citations(factor):
    return {'selected_item', 'rank_' + factor, 'state_estimate', 'graph_assumption', 'learning_limit'}


def template_explanation(packet, decisive):
    ids = ['selected_item', 'rank_' + decisive, 'train_proxy', 'state_estimate', 'graph_assumption', 'learning_limit']
    return {'problem_id': packet['selected_problem_id'], 'decisive_factor': decisive,
            'evidence_ids': ids, 'draft': 'Deterministic template baseline.'}


def assess_explanation(content, packet, decisive, max_chars):
    parsed = Explanation.model_validate_json(content)
    if not parsed.draft.strip() or len(parsed.draft) > max_chars:
        raise ValueError('blank or overlong draft')
    ids = parsed.evidence_ids
    known = {f['id'] for f in packet['fact_catalog']}
    return parsed, {
        'fixed_id_consistent': parsed.problem_id == packet['selected_problem_id'],
        'decisive_factor_correct': parsed.decisive_factor == decisive,
        'citations_valid': len(ids) == len(set(ids)) and set(ids) <= known,
        'citation_coverage': required_citations(decisive) <= set(ids),
    }


def render_verified(parsed, packet, checks):
    known = {f['id'] for f in packet['fact_catalog']}
    decisive = ('single_candidate' if packet['initial_candidate_count'] == 1 else
                next(s['factor'] for s in packet['selection_trace'] if s['after'] == 1))
    expected_keys = {'fixed_id_consistent', 'decisive_factor_correct', 'citations_valid', 'citation_coverage'}
    if (set(checks) != expected_keys or not all(checks.values())
            or parsed.problem_id != packet['selected_problem_id'] or parsed.decisive_factor != decisive
            or len(parsed.evidence_ids) != len(set(parsed.evidence_ids))
            or not set(parsed.evidence_ids) <= known
            or not required_citations(decisive) <= set(parsed.evidence_ids)):
        raise ValueError('explanation rejected; never display an unchecked draft')
    # Canonical catalog order, independent of the model's citation ordering.
    return ' '.join(f['text'] for f in packet['fact_catalog'] if f['id'] in parsed.evidence_ids)


def explanation_request(packet, config, candidate_ids):
    if config['stage'] != 'validation_development_not_lock_c' or config['test_access'] is not False:
        raise ValueError('VALIDATION development only')
    if len(candidate_ids) != len(set(candidate_ids)) or packet['selected_problem_id'] not in candidate_ids:
        raise ValueError('unique candidate IDs including fixed choice required')
    schema = Explanation.model_json_schema()
    schema['properties']['problem_id']['enum'] = candidate_ids
    schema['properties']['evidence_ids']['items']['enum'] = [f['id'] for f in packet['fact_catalog']]
    schema['properties']['draft']['maxLength'] = config['draft_max_chars']
    prompt = (
        'Explain a decision already made by B+. You may NOT select a different problem. '
        'Return JSON problem_id, decisive_factor, evidence_ids, draft. '
        'Find the FIRST ranking stage where after becomes 1; later stages are tie-breaks '
        'that no longer decide the winner. If initial_candidate_count is 1 use single_candidate. '
        'Cite selected_item, rank_<decisive_factor>, state_estimate, graph_assumption, '
        'learning_limit, and optionally other relevant catalog facts. No duplicate citations. '
        'Use ONLY supplied facts. Write a brief draft in Vietnamese. Mastery is estimated; '
        'TRAIN success rate is an item statistic; curriculum links are author assumptions. '
        'Never assert verified mastery, causal prerequisites, or improved learning.'
    )
    runtime = config['agent']
    request = {'model': config['model'], 'stream': False, 'format': schema,
               'options': {k: runtime[k] for k in ('temperature', 'num_ctx', 'num_predict')},
               'messages': [{'role': 'system', 'content': prompt},
                            {'role': 'user', 'content': json.dumps(packet, ensure_ascii=False, allow_nan=False)}]}
    bound = sum(len(m['content'].encode('utf-8')) for m in request['messages'])
    bound += len(json.dumps(schema).encode('utf-8')) + runtime['template_token_reserve']
    if bound + runtime['num_predict'] > runtime['num_ctx']:
        raise ValueError('explanation context exceeded; no truncation')
    return request, bound


def run_explanation(shared, policy, config, candidate_ids, call):
    packet, decisive = explanation_packet(shared, policy)
    record = {'fixed_problem_id': packet['selected_problem_id'], 'expected_factor': decisive,
              'packet': packet, 'request': None, 'raw_response': None,
              'schema_valid': False, 'fixed_id_consistent': False, 'decisive_factor_correct': False,
              'citations_valid': False, 'citation_coverage': False, 'accepted': False,
              'rendered_explanation': None, 'draft_semantically_verified': False,
              'error_stage': None, 'error_type': None, 'error_message': None,
              'http_status': None, 'http_body': None,
              'prompt_eval_count': None, 'eval_count': None, 'done_reason': None}
    start, stage = time.perf_counter(), 'request'
    try:
        request, bound = explanation_request(packet, config, candidate_ids)
        record['request'] = deepcopy(request)
        stage = 'transport'
        response = call(request, timeout=config['agent']['timeout_seconds'])
        record['raw_response'] = deepcopy(response)
        stage = 'telemetry'
        for key in ('prompt_eval_count', 'eval_count', 'done_reason'):
            record[key] = response.get(key)
        checked_telemetry(response, config['agent'], bound)
        stage = 'schema'
        parsed, checks = assess_explanation(response['message']['content'], packet, decisive, config['draft_max_chars'])
        record.update(schema_valid=True, **checks)
        stage = 'evidence_checks'
        if not all(checks.values()):
            raise ValueError('failed evidence checks: ' + ', '.join(k for k, value in checks.items() if not value))
        record['rendered_explanation'] = render_verified(parsed, packet, checks)
        record['accepted'] = True
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        record.update(error_stage=stage, error_type=type(error).__name__, error_message=str(error))
        if isinstance(error, HTTPError):
            record.update(http_status=error.code, http_body=error.read().decode('utf-8', errors='replace'))
    record['latency_seconds'] = time.perf_counter() - start
    return record
