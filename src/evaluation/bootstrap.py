"""Paired, student-cluster bootstrap for interaction-weighted Brier differences."""

import numpy as np


def paired_student_brier_bootstrap(frame, model_a, model_b, iterations=1000, seed=42):
    """Return the Brier difference A minus B and a percentile 95% interval.

    Each draw samples students with replacement and retains every scored row
    belonging to each sampled student. The denominator is the sampled row count.
    """
    required = ['user_id', 'source_row', 'correct', 'is_scored', model_a, model_b]
    if model_a == model_b or not frame.columns.is_unique or any(c not in frame for c in required):
        raise ValueError('unique columns for two different models are required')
    if not isinstance(iterations, int) or iterations < 1:
        raise ValueError('iterations must be a positive integer')
    if frame[required].isna().any().any() or frame.source_row.duplicated().any():
        raise ValueError('missing values or duplicate source_row identities')
    if not frame.correct.isin([0, 1]).all():
        raise ValueError('correct must be binary')
    if not frame.is_scored.map(lambda v: isinstance(v, (bool, np.bool_))).all():
        raise ValueError('is_scored must be boolean')
    for model in (model_a, model_b):
        values = frame[model].to_numpy(dtype=float)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError('probabilities must be finite and in [0, 1]')

    scored = frame.loc[frame.is_scored].copy()
    if scored.empty:
        raise ValueError('at least one scored row is required')
    y = scored.correct.to_numpy(dtype=float)
    diff = (scored[model_a].to_numpy(dtype=float) - y) ** 2 - (
        scored[model_b].to_numpy(dtype=float) - y) ** 2
    student_codes, students = scored.user_id.factorize(sort=True)
    n_students = len(students)
    sums = np.bincount(student_codes, weights=diff, minlength=n_students)
    counts = np.bincount(student_codes, minlength=n_students)
    point = float(sums.sum() / counts.sum())
    rng = np.random.default_rng(seed)
    draws = np.empty(iterations, dtype=float)
    for i in range(iterations):
        chosen = rng.integers(0, n_students, size=n_students)
        draws[i] = sums[chosen].sum() / counts[chosen].sum()
    low, high = np.percentile(draws, [2.5, 97.5])
    return {'difference': point, 'ci_low': float(low), 'ci_high': float(high),
            'n_students': n_students, 'iterations': iterations}
