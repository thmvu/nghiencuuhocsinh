"""Build a causal, model-based BKT mastery snapshot from a student prefix."""

import math

import numpy as np
import pandas as pd

from src.models.bkt import BKT


def bkt_mastery_snapshot(model: BKT, history: pd.DataFrame, skill_universe=None,
                         *, expected_split='validation') -> dict:
    """Return post-response mastery after *only* the provided student prefix.

    The caller chooses the cutoff and passes no later rows. Model parameters are
    fitted on TRAIN and never updated here; only one student's latent state moves.
    The output is an estimate, not a ground-truth mastery label.
    """
    required = {'user_id', 'order_id', 'skill_id', 'correct', 'split'}
    if expected_split not in ('validation', 'test'):
        raise ValueError('state snapshots require validation or gated test history')
    if (not isinstance(model, BKT) or not isinstance(history, pd.DataFrame) or
            history.empty or not history.columns.is_unique or
            not required.issubset(history.columns)):
        raise ValueError('fitted BKT and nonempty validation history required')
    if (history[list(required)].isna().any().any() or
            not history.split.eq(expected_split).all() or
            history.user_id.nunique() != 1 or not history.correct.isin([0, 1]).all()):
        raise ValueError('one validation student with binary history required')
    order = pd.to_numeric(history.order_id, errors='coerce')
    if not np.isfinite(order).all() or order.duplicated().any():
        raise ValueError('finite unique chronology required')
    frozen = model.global_parameters_snapshot()
    sequence = history.assign(order_id=order).sort_values('order_id', kind='stable')
    student = sequence.user_id.iloc[0]
    model.reset(student)
    encountered = {}
    for row in sequence[['user_id', 'skill_id', 'correct']].to_dict('records'):
        key = str(row['skill_id'])
        if key in encountered and (type(encountered[key]) is not type(row['skill_id']) or
                                   encountered[key] != row['skill_id']):
            raise ValueError('ambiguous skill string identifier')
        model.update(row)
        encountered[key] = row['skill_id']
    all_skills = dict(encountered)
    if skill_universe is not None:
        for skill in skill_universe:
            if pd.isna(skill):
                raise ValueError('skill universe cannot contain missing values')
            key = str(skill)
            if key in all_skills and (type(all_skills[key]) is not type(skill) or
                                      all_skills[key] != skill):
                raise ValueError('ambiguous skill string identifier')
            all_skills[key] = skill
    skills = {}
    for key in sorted(all_skills):
        skill = all_skills[key]
        if skill in model._state:
            mastery = float(math.exp(model._state[skill][1]))
        else:
            mastery = float(model._parameters(skill)[0])
        if not math.isfinite(mastery) or not 0 <= mastery <= 1:
            raise ValueError('invalid BKT mastery probability')
        skills[key] = mastery
    if model.global_parameters_snapshot() != frozen:
        raise RuntimeError('fitted BKT parameters changed during state update')
    return {'state_type': 'BKT_p_mastery', 'skills': skills,
            'history_length': int(len(sequence))}
