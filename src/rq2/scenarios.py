"""Reproducible one-snapshot-per-student RQ2 VALIDATION scenarios."""

from numbers import Integral

import numpy as np
import pandas as pd

from src.rq2.state import bkt_mastery_snapshot


def sample_validation_scenarios(validation: pd.DataFrame, model, n_scenarios: int,
                                seed: int = 42, min_history: int = 5,
                                skill_universe=None) -> list[dict]:
    """Sample distinct validation students and a prefix cutoff for each.

    Future labels never enter the snapshot. Student IDs in returned scenarios
    are sensitive and any serialized artifact must stay out of Git.
    """
    if (not isinstance(validation, pd.DataFrame) or validation.empty or
            not validation.columns.is_unique or
            not {'user_id', 'order_id', 'skill_id', 'correct', 'split'}.issubset(validation.columns) or
            validation[['user_id', 'order_id', 'skill_id', 'correct', 'split']].isna().any().any() or
            not validation.split.eq('validation').all() or
            not validation.correct.isin([0, 1]).all()):
        raise ValueError('validation-only rows with binary labels required')
    if (isinstance(n_scenarios, bool) or not isinstance(n_scenarios, Integral) or n_scenarios < 1 or
            isinstance(min_history, bool) or not isinstance(min_history, Integral) or min_history < 1 or
            isinstance(seed, bool) or not isinstance(seed, Integral)):
        raise ValueError('positive scenario count/history and integer seed required')
    order = pd.to_numeric(validation.order_id, errors='coerce')
    if not np.isfinite(order).all():
        raise ValueError('finite chronology required')
    frame = validation.assign(order_id=order)
    if frame.duplicated(['user_id', 'order_id']).any():
        raise ValueError('duplicate student chronology')
    groups = {student: group.sort_values('order_id', kind='stable')
              for student, group in frame.groupby('user_id', sort=False)
              if len(group) >= min_history}
    students = sorted(groups, key=lambda value: (str(type(value)), str(value)))
    if n_scenarios > len(students):
        raise ValueError('not enough eligible validation students')
    rng = np.random.default_rng(seed)
    chosen = rng.choice(len(students), size=n_scenarios, replace=False)
    scenarios = []
    for index, student_index in enumerate(chosen):
        student = students[int(student_index)]
        sequence = groups[student]
        length = int(rng.integers(min_history, len(sequence) + 1))
        prefix = sequence.iloc[:length]
        scenarios.append({
            'scenario_id': f'validation_{index + 1:03d}',
            'student_id': student,
            'cutoff_order_id': prefix.order_id.iloc[-1].item() if hasattr(prefix.order_id.iloc[-1], 'item') else prefix.order_id.iloc[-1],
            'state': bkt_mastery_snapshot(model, prefix, skill_universe=skill_universe),
        })
    return scenarios
