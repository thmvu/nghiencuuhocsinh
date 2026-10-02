"""Shared v4 inputs and VALIDATION-only operational policies and diagnostics."""

from collections import Counter
from copy import deepcopy
import json
import math
import statistics
import time

import numpy as np

from src.rq2.agent import Recommendation, build_agent_request, validate_agent_output
from src.rq2.candidates import generate_candidates
from src.rq2.scenarios import sample_validation_scenarios
from src.rq2.state import bkt_mastery_snapshot

LINK_SEMANTICS = (
    'Author-proposed curriculum links, not verified mastery prerequisites. '
    'Separate state per skill ID even if standard codes match. Each source ID '
    'may signal optional remediation for its linked target; never require all '
    'IDs of a standard to be mastered, pool their states, or count repeated '
    'links as votes. No hard readiness constraint is imposed.'
)


def compact_graph(audit_graph, variant):
    """Allowlisted projection: audit edges/order cannot leak into ablation."""
    if variant not in ('curriculum_edges', 'no_edges'):
        raise ValueError('unknown graph variant')
    skills = audit_graph['skills']
    if len(skills) != len(set(skills)) or not all(isinstance(s, str) for s in skills):
        raise ValueError('unique string skills required')
    mapping = audit_graph['skill_to_standard']
    if set(mapping) != set(skills):
        raise ValueError('graph skill mapping mismatch')
    pairs = sorted({(e['prerequisite'], e['target']) for e in audit_graph['edges']})
    if any(a not in skills or b not in skills or a == b for a, b in pairs):
        raise ValueError('invalid graph endpoint')
    return {'skills': sorted(skills), 'skill_to_standard': dict(sorted(mapping.items())),
            'edges': [{'prerequisite': a, 'target': b} for a, b in pairs] if variant == 'curriculum_edges' else [],
            'link_semantics': LINK_SEMANTICS}


def validate_shared(shared):
    state, graph, candidates = (shared[k] for k in ('state', 'graph', 'candidates'))
    if set(graph) != {'skills', 'skill_to_standard', 'edges', 'link_semantics'} or graph['link_semantics'] != LINK_SEMANTICS:
        raise ValueError('only compact graph fields and frozen semantics permitted')
    if set(state['skills']) != set(graph['skills']):
        raise ValueError('state must contain exactly the graph skill scope')
    if set(graph['skill_to_standard']) != set(graph['skills']):
        raise ValueError('graph mapping mismatch')
    for edge in graph['edges']:
        if set(edge) != {'prerequisite', 'target'} or any(edge[k] not in state['skills'] for k in edge):
            raise ValueError('invalid compact edge')
    # Reuse candidate/state schema validation without calling a model.
    build_agent_request(state, graph, candidates, model='validation_only')


def relevant_weak_sources(shared, policy):
    """Binary soft signal from direct links to weak, represented target IDs."""
    validate_shared(shared)
    mastery = shared['state']['skills']
    represented = {c['skill_id'] for c in shared['candidates']}
    for key in ('source_weak_threshold', 'target_weak_threshold', 'target_train_success_rate'):
        value = policy[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('finite policy probabilities required')
    return {e['prerequisite'] for e in shared['graph']['edges']
            if e['target'] in represented
            and mastery[e['target']] < policy['target_weak_threshold']
            and mastery[e['prerequisite']] < policy['source_weak_threshold']}


def recommend_foundational_bplus(shared, policy):
    sources = relevant_weak_sources(shared, policy)
    def rank(c):
        return (0 if c['skill_id'] in sources else 1,
                abs(c['difficulty'] - policy['target_train_success_rate']),
                -c['support'], c['problem_id'])
    return dict(min(shared['candidates'], key=rank))


def build_foundational_cases(validation, bkt, audit_graph, pool, config):
    if config.get('stage') != 'validation_development_not_lock_c' or config.get('test_access') is not False:
        raise ValueError('VALIDATION development config required')
    if config['graph_variants'] != ['curriculum_edges', 'no_edges']:
        raise ValueError('both prespecified graph variants required')
    for key in ('validation_scenarios', 'min_history', 'minimum_train_support',
                'candidates_per_scenario', 'permutations_per_scenario'):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError('positive scenario/history/support/count settings required')
    graph = compact_graph(audit_graph, 'curriculum_edges')
    pool = [dict(c) for c in pool if c['support'] >= config['minimum_train_support']]
    if len(pool) < config['candidates_per_scenario']:
        raise ValueError('TRAIN pool too small')
    scenarios = sample_validation_scenarios(
        validation, bkt, config['validation_scenarios'], seed=config['seed'],
        min_history=config['min_history'], skill_universe=graph['skills'])
    cases = []
    for scenario in scenarios:
        state = deepcopy(scenario['state'])
        state['skills'] = {s: state['skills'][s] for s in graph['skills']}
        candidates = generate_candidates(state, graph, pool, config['candidates_per_scenario'])
        if len(candidates) != config['candidates_per_scenario']:
            raise ValueError('incomplete candidate list')
        validate_shared({'state': state, 'graph': graph, 'candidates': candidates})
        cases.append({**scenario, 'state': state, 'candidates': candidates})
    return cases, pool


def shared_repetitions(cases, audit_graph, config):
    """Permute once per case/repetition, then reuse order under both graphs."""
    for index, case in enumerate(cases):
        for repetition in range(config['permutations_per_scenario']):
            sequence = np.random.SeedSequence([config['seed'], index, repetition])
            order_rng, random_rng = [np.random.default_rng(s) for s in sequence.spawn(2)]
            order = order_rng.permutation(len(case['candidates'])).tolist()
            candidates = [deepcopy(case['candidates'][i]) for i in order]
            random_ids = sorted(c['problem_id'] for c in candidates)
            random_id = random_ids[int(random_rng.integers(len(random_ids)))]
            for variant in config['graph_variants']:
                shared = {'state': deepcopy(case['state']),
                          'graph': compact_graph(audit_graph, variant),
                          'candidates': deepcopy(candidates)}
                yield case, repetition, variant, order, random_id, shared


def build_observed_link_challenge(validation, bkt, audit_graph, pool, config):
    """Exploratory cohort, selected by prefix state only, never policy output.

    Candidates include a source and its target under BOTH graph variants.
    This measures conditional ranking sensitivity, not an end-to-end ablation.
    """
    design = config['supplementary_challenge']
    if (config.get('stage') != 'validation_development_not_lock_c'
            or config.get('test_access') is not False
            or design['stage'] != 'exploratory_validation_only_not_representative'):
        raise ValueError('exploratory VALIDATION config required')
    if (validation.empty or not validation.split.eq('validation').all()
            or validation.duplicated(['user_id', 'order_id']).any()):
        raise ValueError('unique VALIDATION chronology required')
    cutoff = design['prefix_length']
    if type(cutoff) is not int or cutoff < 1 or config['candidates_per_scenario'] < 2:
        raise ValueError('positive prefix and at least two candidates required')
    graph = compact_graph(audit_graph, 'curriculum_edges')
    pool = [dict(c) for c in pool if c['support'] >= config['minimum_train_support']]
    if len({c['problem_id'] for c in pool}) != len(pool):
        raise ValueError('single-skill pool must have unique problem IDs')
    by_skill = {}
    for item in sorted(pool, key=lambda c: c['problem_id']):
        by_skill.setdefault(item['skill_id'], []).append(item)
    rng = np.random.default_rng(config['seed'])
    cases = []
    for student, history in validation.groupby('user_id', sort=True):
        prefix = history.sort_values('order_id', kind='stable').iloc[:cutoff]
        if len(prefix) != cutoff:
            continue
        state = bkt_mastery_snapshot(bkt, prefix, skill_universe=graph['skills'])
        state['skills'] = {s: state['skills'][s] for s in graph['skills']}
        observed = set(prefix.skill_id.astype(str))
        by_standard_edge = {}
        for edge in graph['edges']:
            a, b = edge['prerequisite'], edge['target']
            if (a in observed & set(by_skill) and b in observed & set(by_skill)
                    and state['skills'][a] < config['bplus']['source_weak_threshold']
                    and state['skills'][b] < config['bplus']['target_weak_threshold']):
                pair = (graph['skill_to_standard'][a], graph['skill_to_standard'][b])
                by_standard_edge.setdefault(pair, []).append((a, b))
        if not by_standard_edge:
            continue
        standard_pair = sorted(by_standard_edge)[int(rng.integers(len(by_standard_edge)))]
        pairs = sorted(set(by_standard_edge[standard_pair]))
        a, b = pairs[int(rng.integers(len(pairs)))]
        candidates = [dict(by_skill[s][int(rng.integers(len(by_skill[s])))]) for s in (a, b)]
        selected = {c['problem_id'] for c in candidates}
        remaining = [c for c in pool if c['problem_id'] not in selected]
        slots = config['candidates_per_scenario'] - 2
        if slots:
            candidates.extend(generate_candidates(state, graph, remaining, slots))
        if len(candidates) != config['candidates_per_scenario']:
            raise ValueError('incomplete challenge candidate list')
        validate_shared({'state': state, 'graph': graph, 'candidates': candidates})
        value = prefix.order_id.iloc[-1]
        cases.append({'scenario_id': f'challenge_{len(cases) + 1:03d}',
                      'student_id': student.item() if hasattr(student, 'item') else student,
                      'cutoff_order_id': value.item() if hasattr(value, 'item') else value,
                      'state': state, 'candidates': candidates,
                      'construction_standard_pair': list(standard_pair),
                      'construction_skill_pair': [a, b]})
    if not cases:
        raise ValueError('no observed supported weak links at the fixed prefix')
    return cases, pool


def run_deterministic(cases, audit_graph, config):
    records = []
    for case, repetition, variant, order, random_id, shared in shared_repetitions(cases, audit_graph, config):
        bplus = recommend_foundational_bplus(shared, config['bplus'])['problem_id']
        # Hold evaluation labels fixed as well as inputs. Evaluating no_edges
        # against an empty graph would make this rate zero by definition.
        reference = {**shared, 'graph': compact_graph(audit_graph, 'curriculum_edges')}
        relevant = relevant_weak_sources(reference, config['bplus'])
        choices = {'B+': bplus, 'random': random_id,
                   'always_first': shared['candidates'][0]['problem_id']}
        by_id = {c['problem_id']: c for c in shared['candidates']}
        positions = {c['problem_id']: i for i, c in enumerate(shared['candidates'])}
        for name, chosen in choices.items():
            records.append({'scenario_id': case['scenario_id'], 'student_id': case['student_id'],
                            'repetition': repetition, 'graph_variant': variant, 'policy': name,
                            'schema_valid': True, 'candidate_valid': True, 'selected_problem_id': chosen,
                            'agrees_with_bplus': chosen == bplus,
                            'soft_source_remediation_selected': by_id[chosen]['skill_id'] in relevant,
                            'selected_position': positions[chosen], 'permutation': order,
                            'latency_seconds': None, 'prompt_eval_count': None, 'error_type': None})
    return records


def case_coverage(cases, audit_graph, config):
    """Count whether graph-dependent ranking can activate, once per student."""
    graph = compact_graph(audit_graph, 'curriculum_edges')
    sources = {e['prerequisite'] for e in graph['edges']}
    targets = {e['target'] for e in graph['edges']}
    result = {'n_scenarios': len(cases), 'scenarios_with_any_weak_source': 0,
              'scenarios_with_represented_weak_graph_target': 0,
              'scenarios_with_relevant_weak_source': 0,
              'scenarios_with_relevant_source_candidate': 0}
    for case in cases:
        mastery = case['state']['skills']
        represented = {c['skill_id'] for c in case['candidates']}
        relevant = relevant_weak_sources({'state': case['state'], 'graph': graph,
                                         'candidates': case['candidates']}, config['bplus'])
        result['scenarios_with_any_weak_source'] += int(any(mastery[s] < config['bplus']['source_weak_threshold'] for s in sources))
        result['scenarios_with_represented_weak_graph_target'] += int(any(mastery[s] < config['bplus']['target_weak_threshold'] for s in represented & targets))
        result['scenarios_with_relevant_weak_source'] += int(bool(relevant))
        result['scenarios_with_relevant_source_candidate'] += int(bool(represented & relevant))
    return result


def make_agent_request(shared, runtime):
    validate_shared(shared)
    request = build_agent_request(shared['state'], shared['graph'], shared['candidates'],
                                  model=runtime['model'], temperature=runtime['temperature'],
                                  num_ctx=runtime['num_ctx'])
    request['messages'][0]['content'] += (
        ' Edges are optional curriculum remediation signals, never hard readiness gates. '
        'Different skill IDs with the same standard keep separate states; do not apply AND '
        'or pool mastery. difficulty is TRAIN success rate (higher means easier), '
        'not this student\'s predicted probability of answering correctly.'
    )
    request['options']['num_predict'] = runtime['num_predict']
    payload_bytes = sum(len(m['content'].encode('utf-8')) for m in request['messages'])
    payload_bytes += len(json.dumps(request['format']).encode('utf-8'))
    # A conservative byte-based guard, explicitly not an exact token count.
    bound = payload_bytes + runtime['template_token_reserve']
    if bound + runtime['num_predict'] > runtime['num_ctx']:
        raise ValueError('conservative context budget exceeded; do not truncate inputs')
    return request, bound


def checked_telemetry(response, runtime, bound):
    prompt, output = response.get('prompt_eval_count'), response.get('eval_count')
    if type(prompt) is not int or type(output) is not int or prompt < 1 or output < 0:
        raise ValueError('runtime token telemetry missing')
    if prompt > bound or prompt + runtime['num_predict'] > runtime['num_ctx']:
        raise ValueError('runtime prompt exceeds reserved context budget')
    if response.get('done') is not True or response.get('done_reason') != 'stop':
        raise ValueError('generation incomplete or reached output limit')
    return prompt


def run_agent(cases, audit_graph, config, call, *, checkpoint=None):
    records = []
    runtime = config['agent']
    for case, repetition, variant, order, random_id, shared in shared_repetitions(cases, audit_graph, config):
        record = {'scenario_id': case['scenario_id'], 'student_id': case['student_id'],
                  'repetition': repetition, 'graph_variant': variant, 'policy': 'Agent',
                  'schema_valid': False, 'candidate_valid': False, 'selected_problem_id': None,
                  'agrees_with_bplus': False, 'soft_source_remediation_selected': False,
                  'selected_position': None, 'permutation': order, 'latency_seconds': None,
                  'prompt_eval_count': None, 'error_type': None}
        start = time.perf_counter()
        try:
            request, bound = make_agent_request(shared, runtime)
            response = call(request, timeout=runtime['timeout_seconds'])
            record['prompt_eval_count'] = checked_telemetry(response, runtime, bound)
            content = response['message']['content']
            Recommendation.model_validate_json(content)
            record['schema_valid'] = True
            selected = validate_agent_output(content, shared['candidates'])
            record['candidate_valid'] = True
            record['selected_problem_id'] = selected['problem_id']
            record['agrees_with_bplus'] = selected['problem_id'] == recommend_foundational_bplus(shared, config['bplus'])['problem_id']
            item = next(c for c in shared['candidates'] if c['problem_id'] == selected['problem_id'])
            record['selected_position'] = next(i for i, c in enumerate(shared['candidates']) if c['problem_id'] == selected['problem_id'])
            reference = {**shared, 'graph': compact_graph(audit_graph, 'curriculum_edges')}
            record['soft_source_remediation_selected'] = item['skill_id'] in relevant_weak_sources(reference, config['bplus'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            record['error_type'] = type(error).__name__
        record['latency_seconds'] = time.perf_counter() - start
        records.append(record)
        if checkpoint is not None:
            checkpoint(records)
    return records


def summarize_operational(records):
    """Aggregate per student first; no private IDs or per-row predictions."""
    if not records:
        raise ValueError('nonempty records required')
    summaries = {}
    for name in sorted({r['policy'] for r in records}):
        rows = [r for r in records if r['policy'] == name]
        variants = {}
        for variant in ('curriculum_edges', 'no_edges'):
            subset = [r for r in rows if r['graph_variant'] == variant]
            groups = {}
            for row in subset:
                groups.setdefault(row['student_id'], []).append(row)
            if not groups:
                raise ValueError('both variants required')
            result = {'n_calls': len(subset), 'n_students': len(groups)}
            for key in ('schema_valid', 'candidate_valid', 'agrees_with_bplus', 'soft_source_remediation_selected'):
                result[key + '_rate'] = statistics.mean(statistics.mean(float(r[key]) for r in group) for group in groups.values())
            complete = [group for group in groups.values() if all(r['candidate_valid'] for r in group)]
            result['all_valid_students'] = len(complete)
            result['order_sensitive_fraction_among_all_valid_students'] = (statistics.mean(len({r['selected_problem_id'] for r in group}) > 1 for group in complete) if complete else None)
            result['position_counts_valid'] = dict(sorted(Counter(r['selected_position'] for r in subset if r['candidate_valid']).items()))
            result['error_counts'] = dict(Counter(r['error_type'] for r in subset if r['error_type']))
            for key in ('latency_seconds', 'prompt_eval_count'):
                values = [r[key] for r in subset if r[key] is not None]
                result[key + '_mean'] = statistics.mean(values) if values else None
                result[key + '_max'] = max(values) if values else None
            variants[variant] = result
        pairs = {}
        for row in rows:
            pairs.setdefault((row['student_id'], row['repetition']), {})[row['graph_variant']] = row
        usable, invalid = {}, 0
        for (student, repetition), pair in pairs.items():
            if set(pair) != {'curriculum_edges', 'no_edges'}:
                raise ValueError('unpaired graph variant')
            if all(r['candidate_valid'] for r in pair.values()):
                usable.setdefault(student, []).append(pair['curriculum_edges']['selected_problem_id'] != pair['no_edges']['selected_problem_id'])
            else:
                invalid += 1
        summaries[name] = {'variants': variants,
                           'variation_interpretation': 'different stochastic draws, not position bias' if name == 'random' else 'selection variation across candidate permutations',
                           'paired_selection_change_rate_among_valid_pairs': statistics.mean(statistics.mean(values) for values in usable.values()) if usable else None,
                           'paired_valid_student_count': len(usable),
                           'paired_valid_pair_count': sum(len(values) for values in usable.values()),
                           'invalid_graph_pairs': invalid}
    return {'stage': 'foundationalassist_v4_rq2_validation_development', 'test_opened': False,
            'claims': 'operational behavior only; not pedagogical quality or learning gain',
            'policies': summaries}
