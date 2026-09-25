"""Small, explicitly hypothetical prerequisite graph for RQ2 development."""

import pandas as pd


# Skill labels are for audit only. These edges need a curriculum expert review.
PROTOTYPE_EDGES = (
    ('277', '279', 'Addition/Subtraction Integers -> Multiplication/Division Integers'),
    ('311', '312', 'Equation Solving Two or Fewer Steps -> More Than Two Steps'),
    ('47', '77', 'Conversion Fraction Decimals Percents -> Finding Percents'),
    ('47', '79', 'Conversion Fraction Decimals Percents -> Proportion'),
    ('18', '17', 'Probability Single Event -> Two Distinct Events'),
)


def require_train_only(frame: pd.DataFrame) -> None:
    """Reject a mixed or held-out split before reading outcome metadata."""
    if 'split' in frame and not frame['split'].eq('train').all():
        raise ValueError('RQ2 graph and candidate metadata require TRAIN rows only')


def build_prototype_graph(train: pd.DataFrame, n_skills: int = 20) -> dict:
    """Select popular TRAIN skills; retain only named, provisional edges."""
    if not 10 <= n_skills <= 30:
        raise ValueError('n_skills must be between 10 and 30')
    require_train_only(train)
    if 'skill_id' not in train:
        raise ValueError('TRAIN must contain skill_id')
    counts = train['skill_id'].dropna().astype(str).value_counts()
    if len(counts) < n_skills:
        raise ValueError('TRAIN has fewer distinct skills than n_skills')
    skills = sorted(counts.index, key=lambda s: (-int(counts[s]), s))[:n_skills]
    selected = set(skills)
    edges = [
        {'prerequisite': before, 'target': after,
         'basis': 'prototype_assumption', 'rationale': rationale}
        for before, after, rationale in PROTOTYPE_EDGES
        if before in selected and after in selected
    ]
    return {'skills': skills, 'edges': edges,
            'status': 'prototype_assumptions_pending_curriculum_review'}
