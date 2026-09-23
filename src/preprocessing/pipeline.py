"""Leakage-safe interaction cleaning and prequential feature construction."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


def clean_interactions(df):
    """Keep single numeric skills; source_row is the original zero-based position.

    Identity, binary labels and ordering must be valid before filtering. Repeated
    student/problem attempts are legitimate and are never deduplicated.
    """
    required = {'user_id', 'problem_id', 'skill_id', 'order_id', 'correct'}
    if required - set(df.columns):
        raise ValueError(f'Missing columns: {sorted(required - set(df.columns))}')
    out = df.copy()
    for col in ['user_id', 'problem_id']:
        out[col] = out[col].astype('string').str.strip()
        if out[col].isna().any() or out[col].eq('').any():
            raise ValueError(f'Missing identity: {col}')
    order = pd.to_numeric(out.order_id, errors='coerce')
    if order.isna().any() or not np.isfinite(order).all() or (order % 1 != 0).any():
        raise ValueError('order_id must contain finite integers')
    out['order_id'] = order.astype('int64')
    target = pd.to_numeric(out.correct, errors='coerce')
    if not target.isin([0, 1]).all():
        raise ValueError('correct must contain binary labels')
    out['correct'] = target.astype('int64')
    if out.duplicated(['user_id', 'order_id']).any():
        raise ValueError('Duplicate student/order identity')
    skill = out.skill_id.astype('string').str.strip()
    single = skill.str.fullmatch(r'[0-9]+', na=False)
    multi = skill.str.fullmatch(r'[0-9]+(?:_[0-9]+)+', na=False)
    missing = skill.isna() | skill.eq('').fillna(False)
    if (~(single | multi | missing)).any():
        raise ValueError('Unrecognized skill encoding; review schema before filtering')
    if 'source_row' not in out:
        out['source_row'] = np.arange(len(out))
    elif out.source_row.isna().any() or out.source_row.duplicated().any():
        raise ValueError('source_row must be nonmissing and unique')
    out['skill_id'] = skill
    return out.loc[single].sort_values(['user_id', 'order_id'], kind='stable').reset_index(drop=True)


def apply_split(df, manifest):
    """Apply the existing student manifest (mapping or JSON path), never resplit."""
    if isinstance(manifest, (str, Path)):
        with open(manifest, encoding='utf-8') as stream:
            manifest = json.load(stream)
    students = manifest['students']
    membership = {}
    for split in ['train', 'validation', 'test']:
        for user in students[split]:
            user = str(user)
            if user in membership:
                raise ValueError(f'Duplicate or overlapping manifest student: {user}')
            membership[user] = split
    out = df.copy()
    out['user_id'] = out.user_id.astype('string')
    out['split'] = out.user_id.map(membership)
    if out.split.isna().any():
        raise ValueError('Some students are missing from split manifest')
    return out


def add_history_features(df, warmup=5):
    """Predict-before-update histories; cold-start accuracy is fixed at 0.5."""
    if not isinstance(warmup, int) or warmup < 0:
        raise ValueError('warmup must be a nonnegative integer')
    out = df.sort_values(['user_id', 'order_id'], kind='stable').reset_index(drop=True).copy()
    groups = out.groupby(['user_id', 'skill_id'], sort=False)
    out['prior_skill_count'] = groups.cumcount()
    out['prior_skill_success'] = groups.correct.cumsum() - out.correct
    out['prior_skill_failure'] = out.prior_skill_count - out.prior_skill_success
    out['prior_skill_accuracy'] = (out.prior_skill_success / out.prior_skill_count.replace(0, np.nan)).fillna(.5)
    users = out.groupby('user_id', sort=False)
    out['history_length'] = users.cumcount()
    prior_success = users.correct.cumsum() - out.correct
    out['prior_overall_accuracy'] = (prior_success / out.history_length.replace(0, np.nan)).fillna(.5)
    out['scored'] = out.history_length >= warmup
    return out


def add_problem_difficulty(df, n_splits=5, alpha=10):
    """Smoothed success probability (larger means easier).

    Train receives deterministic student GroupKFold OOF values; validation/test
    receive full-train statistics. Fold-global means are fitted independently.
    Requires at least n_splits distinct training students; never reduces folds.
    """
    if not isinstance(n_splits, int) or n_splits < 2:
        raise ValueError('n_splits must be an integer >= 2')
    if not np.isfinite(alpha) or alpha < 0:
        raise ValueError('alpha must be finite and nonnegative')
    out = df.copy().reset_index(drop=True)
    if not out.split.isin(['train', 'validation', 'test']).all():
        raise ValueError('Unknown or missing split')
    if (out.groupby('user_id').split.nunique() > 1).any():
        raise ValueError('Student occurs in multiple splits')
    train = out.loc[out.split.eq('train')]
    if train.user_id.nunique() < n_splits:
        raise ValueError('Not enough training students for requested folds')
    values = np.empty(len(out), dtype=float)

    def transform(fit, query):
        global_mean = fit.correct.mean()
        stats = fit.groupby('problem_id').correct.agg(['sum', 'count'])
        probabilities = (stats['sum'] + alpha * global_mean) / (stats['count'] + alpha)
        return query.problem_id.map(probabilities).fillna(global_mean).to_numpy()

    for fit_pos, held_pos in GroupKFold(n_splits=n_splits).split(train, groups=train.user_id):
        fit, held = train.iloc[fit_pos], train.iloc[held_pos]
        values[held.index] = transform(fit, held)
    held = out.loc[~out.split.eq('train')]
    values[held.index] = transform(train, held)
    out['problem_difficulty'] = values
    return out
