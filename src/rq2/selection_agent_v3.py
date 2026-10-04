"""Final development contract, diagnostic flags and predeclared decision rules."""

from copy import deepcopy
import json
import re
import time

import numpy as np

from src.rq2.agent import Recommendation
from src.rq2.foundational_validation import checked_telemetry
from src.rq2.runtime_journal import RuntimeIntegrityError
from src.rq2.selection_agent_v2 import selection_request as v2_request


def selection_request(shared, config, enum_ids):
    request, _ = v2_request(shared, config, enum_ids)
    request['messages'][0]['content'] += (
        ' Trả lời reason chỉ bằng tiếng Việt, tối đa hai câu ngắn, hoàn chỉnh. '
        'Chỉ diễn giải metadata được cung cấp; không đoán nội dung đề bài. '
        'Chỉ nhắc số liệu có trong input. Support là số tương tác TRAIN của bài, '
        'không phải số lần học sinh này luyện tập. Mastery là ước lượng BKT; '
        'difficulty là tỷ lệ đúng trên TRAIN, giá trị cao hơn nghĩa là dễ hơn. '
        'Không khẳng định việc chọn bài sẽ cải thiện học tập.'
    )
    bound = sum(len(m['content'].encode('utf-8')) for m in request['messages'])
    bound += len(json.dumps(request['format']).encode('utf-8')) + config['agent']['template_token_reserve']
    if bound + config['agent']['num_predict'] > config['agent']['num_ctx']:
        raise ValueError('v3 context budget exceeded; no truncation')
    return request, bound


def rationale_flags(reason, shared, cap, valid):
    text = reason.strip() if isinstance(reason, str) else ''
    unavailable = not bool(text)
    ideographs = bool(re.search(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]', text))
    punctuation = bool(re.search(r'[\u3000-\u303f\uff00-\uffef]', text))
    at_cap = len(reason) == cap if isinstance(reason, str) else False
    no_terminal = bool(text) and text[-1] not in '.!?…'
    candidates = {c['problem_id']: c for c in shared['candidates']}
    skills = shared['state']['skills']
    supports = {str(c['support']) for c in candidates.values()}
    # Explicitly labelled IDs/counts are exact; remaining numbers are soft flags.
    labelled = re.compile(r'\b(problem(?:_id)?|skill(?:_id)?|support|ID|kỹ năng|bài số)\s*[:=#]?\s*(\d+)(?!\d|\.\d)', re.I)
    unknown, mismatch = False, False
    referenced_skills, referenced_items = set(), set()
    remaining = re.sub(r'\b\d+\.[A-Z]+\.[A-Z]\.\d+[a-z]?\b', '', text)
    for match in labelled.finditer(remaining):
        label, number = match.group(1).lower(), match.group(2)
        if label == 'support':
            mismatch |= number not in supports
        elif label.startswith('skill') or label == 'kỹ năng':
            unknown |= number not in skills
            referenced_skills.add(number)
        else:
            unknown |= number not in candidates
            referenced_items.add(number)
    remaining = labelled.sub('', remaining)
    # Plain IDs are only recognized when labelled: otherwise numeric ambiguity is flagged.
    allowed = [skills[s] for s in referenced_skills if s in skills]
    chosen = [c for c in candidates.values() if c['problem_id'] in referenced_items]
    if not chosen and not referenced_skills:
        chosen = [c for c in candidates.values() if c['problem_id'] == shared.get('selected_problem_id')]
    for c in chosen:
        allowed.extend([skills[c['skill_id']], c['difficulty']])
    if not allowed:
        allowed = list(skills.values()) + [c['difficulty'] for c in candidates.values()]
    for token, percent in re.findall(r'(?<!\w)(\d+(?:[.,]\d+)?)\s*(%)?', remaining):
        value = float(token.replace(',', '.')) / (100 if percent else 1)
        if not any(abs(value - v) <= .0100000001 for v in allowed):
            mismatch = True
    return {'observed_cjk_ideograph': ideographs, 'observed_cjk_punctuation': punctuation,
            'observed_length_cap': at_cap, 'observed_no_terminal_punctuation': no_terminal,
            'numeric_mismatch': mismatch, 'unknown_id': unknown, 'reason_unavailable': unavailable,
            'budget_cjk_ideograph': not valid or unavailable or ideographs,
            'budget_length_cap': not valid or unavailable or at_cap,
            'budget_no_terminal_punctuation': not valid or unavailable or no_terminal}


def run_selection(shared, config, enum_ids, call):
    row = {'request': None, 'raw_response': None, 'candidate_valid': False, 'selected_problem_id': None,
           'reason': None, 'selected_position': None, 'selected_enum_position': None,
           'prompt_eval_count': None, 'eval_count': None, 'error_stage': None, 'error_type': None,
           'error_message': None, 'reason_semantically_verified': False}
    start, stage = time.perf_counter(), 'request'
    try:
        request, bound = selection_request(shared, config, enum_ids)
        row['request'] = deepcopy(request)
        stage = 'transport'
        response = call(request, timeout=config['agent']['timeout_seconds'])
        row['raw_response'] = deepcopy(response)
        # Preserve available reason even if telemetry/schema later fails.
        try:
            value = json.loads(response['message']['content']).get('reason')
            row['reason'] = value if isinstance(value, str) else None
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        stage = 'telemetry'
        row.update(prompt_eval_count=response.get('prompt_eval_count'), eval_count=response.get('eval_count'))
        checked_telemetry(response, config['agent'], bound)
        stage = 'output_contract'
        parsed = Recommendation.model_validate_json(response['message']['content'])
        ids = [c['problem_id'] for c in shared['candidates']]
        if not parsed.reason.strip() or len(parsed.reason) > config['reason_max_chars'] or parsed.problem_id not in ids:
            raise ValueError('blank/overlong reason or ID outside candidate set')
        row.update(candidate_valid=True, selected_problem_id=parsed.problem_id, reason=parsed.reason,
                   selected_position=ids.index(parsed.problem_id), selected_enum_position=enum_ids.index(parsed.problem_id))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        row.update(error_stage='runtime_integrity' if isinstance(error, RuntimeIntegrityError) else stage,
                   error_type=type(error).__name__, error_message=str(error))
    row['latency_seconds'] = time.perf_counter() - start
    row['rationale_flags'] = rationale_flags(row['reason'], {**shared, 'selected_problem_id': row['selected_problem_id']}, config['reason_max_chars'], row['candidate_valid'])
    return row


def flag_rates(rows, planned):
    keys = ['observed_cjk_ideograph', 'observed_cjk_punctuation', 'observed_length_cap',
            'observed_no_terminal_punctuation', 'numeric_mismatch', 'unknown_id', 'reason_unavailable',
            'budget_cjk_ideograph', 'budget_length_cap', 'budget_no_terminal_punctuation']
    return {key: {'count': sum(r['rationale_flags'][key] for r in rows),
                  'fraction_all_planned': sum(r['rationale_flags'][key] for r in rows) / planned} for key in keys}


def choose_contract(rows):
    groups = {cap: [r for r in rows if r['cap'] == cap] for cap in (360, 600)}
    if any(len(g) != 24 for g in groups.values()):
        raise ValueError('complete fixed 48-call diagnostic required')
    metrics = {str(cap): {'planned': 24, 'at_cap': sum(r['rationale_flags']['observed_length_cap'] for r in group),
                         'output_errors': sum(not r['candidate_valid'] for r in group), 'flags': flag_rates(group, 24)}
               for cap, group in groups.items()}
    a, b = metrics['360'], metrics['600']
    selected = 600 if b['at_cap'] < a['at_cap'] and b['output_errors'] <= a['output_errors'] else 360
    return {'selected_cap': selected, 'arms': metrics,
            'interpretation': 'contract diagnostic only; no causal attribution or selection-metric comparison'}


def rubric_estimate(rows, ratings):
    groups = {v: [r for r in rows if r['graph_variant'] == v] for v in ('curriculum_edges', 'no_edges')}
    scores = {v: [] for v in groups}
    for rating in ratings:
        values = rating.get('scores')
        if values is None:
            return {'status': 'not_evaluated', 'unconditional_mean': None, 'pass': False}
        if len(values) != 4 or any(type(v) not in (int, float) or not np.isfinite(v) or not 0 <= v <= 2 for v in values):
            raise ValueError('four finite rubric scores in [0,2] required')
        scores[rating['graph_variant']].append((rating['student_id'], float(np.mean(values))))
    probabilities = {v: sum(r['candidate_valid'] for r in g) / len(g) for v, g in groups.items()}
    if any(probabilities[v] > 0 and not scores[v] for v in groups):
        return {'status': 'not_evaluated', 'unconditional_mean': None, 'pass': False}
    def estimate(sample):
        return sum(probabilities[v] * np.mean([s for _, s in sample[v]]) if probabilities[v] else 0 for v in groups) / 2
    mean = float(estimate(scores))
    rng, boot = np.random.default_rng(42), []
    for _ in range(1000):
        sampled = {}
        for variant, pairs in scores.items():
            students = sorted({s for s, _ in pairs}, key=str)
            sampled[variant] = [pair for student in rng.choice(students, size=len(students), replace=True) for pair in pairs if pair[0] == student] if students else []
        boot.append(estimate(sampled))
    return {'status': 'rated', 'unconditional_mean': mean, 'pass': mean >= 1.5,
            'ci95_rubric_sampling_only': np.quantile(boot, [.025, .975]).tolist(),
            'conditional_means': {v: float(np.mean([s for _, s in pairs])) if pairs else None for v, pairs in scores.items()}}


def stop_decision(rows, aggregate, ratings):
    if len(rows) != 240:
        raise ValueError('complete representative batch required for stop decision')
    flags = flag_rates(rows, 240)
    operational = sum(r['candidate_valid'] for r in rows) >= 236
    stable = all(aggregate['representative'][v]['id_stable_students'] >= 32 for v in ('curriculum_edges', 'no_edges'))
    rubric = rubric_estimate(rows, ratings)
    rationale_flags_pass = all(flags[k]['count'] <= maximum for k, maximum in [
        ('budget_cjk_ideograph', 4), ('budget_length_cap', 2), ('budget_no_terminal_punctuation', 12)])
    return {'technical_pass': operational, 'stability_pass': stable, 'rationale_flags_pass': rationale_flags_pass,
            'rubric': rubric, 'all_operational_requirements_met': operational and stable and rationale_flags_pass and rubric['pass'],
            'lock_c_authorized': False, 'further_prompt_model_contract_changes': False}
