"""Assemble shared RQ2 VALIDATION inputs and aggregate diagnostics."""

from collections import Counter

from src.rq2.candidates import build_candidate_pool, generate_candidates
from src.rq2.graph import build_prototype_graph
from src.rq2.policy import recommend_bplus
from src.rq2.scenarios import sample_validation_scenarios


def build_validation_cases(train, validation, bkt, *, n_scenarios=50, seed=42,
                           n_skills=20, min_support=5, n_candidates=8,
                           min_history=5):
    """Prepare one shared state/graph/candidate set per validation student."""
    graph = build_prototype_graph(train, n_skills=n_skills)
    pool = build_candidate_pool(train, graph, min_support=min_support)
    if len(pool) < n_candidates:
        raise ValueError('TRAIN candidate pool is too small')
    scenarios = sample_validation_scenarios(
        validation, bkt, n_scenarios, seed=seed, min_history=min_history,
        skill_universe=graph['skills'])
    cases = []
    for scenario in scenarios:
        state = scenario['state']
        candidates = generate_candidates(state, graph, pool, n_candidates=n_candidates)
        if len(candidates) != n_candidates:
            raise ValueError('candidate generator did not fill the shared set')
        choice = recommend_bplus(state, graph, candidates)
        cases.append({**scenario,
                      'shared_input': {'state': state, 'graph': graph,
                                       'candidates': candidates},
                      'bplus': choice})
    return cases, graph, pool


def summarize_validation_cases(cases, graph, pool):
    """Return only aggregate, non-identifying development diagnostics."""
    if not cases:
        raise ValueError('nonempty validation cases required')
    n_candidates = [len(case['shared_input']['candidates']) for case in cases]
    target_counts = [len({candidate['skill_id'] for candidate in case['shared_input']['candidates']})
                     for case in cases]
    difficulty_spans = [max(candidate['difficulty'] for candidate in case['shared_input']['candidates']) -
                        min(candidate['difficulty'] for candidate in case['shared_input']['candidates'])
                        for case in cases]
    selected_skills = Counter(case['bplus']['skill_id'] for case in cases)
    return {
        'stage': 'rq2_validation_development',
        'test_opened': False,
        'n_scenarios': len(cases),
        'n_students': len({case['student_id'] for case in cases}),
        'n_graph_skills': len(graph['skills']),
        'n_prototype_edges': len(graph['edges']),
        'graph_status': graph['status'],
        'n_train_pool_items': len(pool),
        'candidate_count_min': min(n_candidates),
        'candidate_count_max': max(n_candidates),
        'distinct_target_skills_min': min(target_counts),
        'distinct_target_skills_mean': sum(target_counts) / len(target_counts),
        'difficulty_span_min': min(difficulty_spans),
        'difficulty_span_mean': sum(difficulty_spans) / len(difficulty_spans),
        'bplus_selected_skill_counts': dict(sorted(selected_skills.items())),
    }
