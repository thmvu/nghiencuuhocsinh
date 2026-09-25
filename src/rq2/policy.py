"""Deterministic B+ policy. Lower ranking tuple is preferred."""

import math


def recommend_bplus(state: dict, graph: dict, candidates: list[dict]) -> dict:
    """Rank weak prerequisite relevance, fit, remediation, support, problem ID."""
    if not candidates:
        raise ValueError('No candidates')
    skills = set(graph['skills'])
    mastery = state['skills']
    if not skills <= set(mastery):
        raise ValueError('state lacks a graph skill')
    if any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1 for v in mastery.values()):
        raise ValueError('Invalid mastery probability')
    prerequisite = {e['prerequisite'] for e in graph['edges']}
    for c in candidates:
        if not {'problem_id', 'skill_id', 'difficulty', 'support'} <= set(c):
            raise ValueError('Candidate missing required field')
        if c['skill_id'] not in skills or not math.isfinite(float(c['difficulty'])) \
                or not 0 <= float(c['difficulty']) <= 1 or int(c['support']) < 1:
            raise ValueError('Invalid candidate')

    def rank(c):
        p = float(mastery[c['skill_id']])
        # A weak prerequisite is prioritized over a weak unrelated target.
        prerequisite_priority = 0 if c['skill_id'] in prerequisite and p < .5 else 1
        difficulty_fit = abs(float(c['difficulty']) - p)
        # Weak skills get remediation, strong skills progression; proximity
        # breaks ties in the direction of easier or harder items respectively.
        remediation_penalty = (0 if (p < .5 and c['difficulty'] >= p) or
                              (p >= .5 and c['difficulty'] <= p) else 1)
        return (prerequisite_priority, difficulty_fit, remediation_penalty,
                -int(c['support']), str(c['problem_id']))

    return dict(min(candidates, key=rank))
