"""TRAIN-only problem metadata and diverse, deterministic RQ2 candidate sets."""

import math
import pandas as pd

from src.rq2.graph import require_train_only


def build_candidate_pool(train: pd.DataFrame, graph: dict, min_support: int = 1) -> list[dict]:
    """Summarize observed TRAIN problems; success probability is difficulty fit proxy.

    ``difficulty`` is the TRAIN success rate (larger means easier), not a claim
    about intrinsic or IRT difficulty. Callers must pass TRAIN only.
    """
    require_train_only(train)
    if not {'problem_id', 'skill_id', 'correct'} <= set(train.columns):
        raise ValueError('TRAIN requires problem_id, skill_id, correct')
    if min_support < 1:
        raise ValueError('min_support must be positive')
    frame = train[['problem_id', 'skill_id', 'correct']].dropna().copy()
    frame['skill_id'] = frame['skill_id'].astype(str)
    frame['problem_id'] = frame['problem_id'].astype(str)
    frame = frame[frame['skill_id'].isin(set(graph['skills']))]
    if not frame['correct'].isin([0, 1]).all():
        raise ValueError('correct must be binary')
    stats = frame.groupby(['problem_id', 'skill_id'], sort=True)['correct'].agg(['mean', 'count'])
    pool = [
        {'problem_id': problem, 'skill_id': skill, 'difficulty': float(row['mean']),
         'support': int(row['count'])}
        for (problem, skill), row in stats.iterrows()
        if int(row['count']) >= min_support
    ]
    return sorted(pool, key=lambda c: (c['skill_id'], c['problem_id']))


def generate_candidates(state: dict, graph: dict, pool: list[dict],
                        n_candidates: int = 8) -> list[dict]:
    """Round-robin across skills, retaining problem difficulty variation."""
    if n_candidates < 1:
        raise ValueError('n_candidates must be positive')
    mastery = state['skills']
    skills = set(graph['skills'])
    by_skill = {skill: [] for skill in skills}
    for candidate in pool:
        if candidate['skill_id'] in skills:
            by_skill[candidate['skill_id']].append(candidate)
    # Spread the first pass across the full readiness range. Taking the first
    # n weakest skills would silently remove all progression choices whenever
    # the graph has more skills than candidate slots.
    ranked = sorted((s for s in by_skill if by_skill[s]),
                    key=lambda s: (float(mastery.get(s, .5)), s))
    n_spread = min(n_candidates, len(ranked))
    spread = [ranked[int((i + .5) * len(ranked) / n_spread)]
              for i in range(n_spread)] if n_spread else []
    ordered = spread + [s for s in ranked if s not in set(spread)]
    for skill in ordered:
        p = float(mastery.get(skill, .5))
        by_skill[skill].sort(key=lambda c: (abs(c['difficulty'] - p), c['problem_id']))
    selected = []
    depth = 0
    while len(selected) < n_candidates:
        added = False
        for skill in ordered:
            if depth < len(by_skill[skill]):
                selected.append(dict(by_skill[skill][depth]))
                added = True
                if len(selected) == n_candidates:
                    break
        if not added:
            break
        depth += 1
    return selected
