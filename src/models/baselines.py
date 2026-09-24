"""Train-only global and smoothed problem probability baselines."""
import hashlib
import math
from numbers import Real
from types import MappingProxyType

import numpy as np


def _validate_train(train):
    if not train.columns.is_unique or 'correct' not in train or train.empty:
        raise ValueError('nonempty training data with unique columns and correct required')
    if 'split' in train and not train['split'].eq('train').all():
        raise ValueError('fitting requires only train rows')
    if train.correct.isna().any() or not train.correct.isin([0, 1]).all():
        raise ValueError('training targets must be binary')


class GlobalBaseline:
    def fit(self, train):
        _validate_train(train)
        self.global_mean_ = float(train.correct.mean())
        return self

    def _check_fitted(self):
        if not hasattr(self, 'global_mean_'):
            raise RuntimeError('fit the baseline before predicting')

    def predict(self, row):
        self._check_fitted()
        return self.global_mean_

    def predict_batch(self, df):
        self._check_fitted()
        return np.full(len(df), self.global_mean_, dtype=float)

    def reset(self, user_id):
        """No student state is used by this baseline."""

    def update(self, row):
        """Observed evaluation labels never change fitted probabilities."""

    def global_parameters_snapshot(self):
        self._check_fitted()
        return {'model': 'global', 'global_mean': self.global_mean_}


class ProblemBaseline(GlobalBaseline):
    def __init__(self, alpha=10):
        if (isinstance(alpha, bool) or not isinstance(alpha, Real)
                or not math.isfinite(alpha) or alpha < 0):
            raise ValueError('alpha must be finite and nonnegative')
        self.alpha = float(alpha)

    def fit(self, train):
        _validate_train(train)
        if 'problem_id' not in train or train.problem_id.isna().any():
            raise ValueError('nonmissing problem_id required')
        mean = float(train.correct.mean())
        stats = train.groupby('problem_id', sort=False).correct.agg(['sum', 'count'])
        probabilities = ((stats['sum'] + self.alpha * mean) /
                         (stats['count'] + self.alpha)).to_dict()
        # Immutable fitted table allows a compact cached hash in per-row checks.
        self.problem_probabilities_ = MappingProxyType(probabilities)
        self._hashed_table = self.problem_probabilities_
        encoded = sorted((type(key).__name__, repr(key), float(value))
                         for key, value in probabilities.items())
        self._table_hash = hashlib.sha256(repr(encoded).encode('utf-8')).hexdigest()
        self.global_mean_ = mean
        return self

    def predict(self, row):
        self._check_fitted()
        return float(self.problem_probabilities_.get(row['problem_id'], self.global_mean_))

    def predict_batch(self, df):
        self._check_fitted()
        if 'problem_id' not in df:
            raise ValueError('problem_id required for problem predictions')
        return df.problem_id.map(self.problem_probabilities_).fillna(self.global_mean_).to_numpy(dtype=float)

    def global_parameters_snapshot(self):
        self._check_fitted()
        table_hash = self._table_hash
        if self.problem_probabilities_ is not self._hashed_table:
            encoded = sorted((type(key).__name__, repr(key), float(value))
                             for key, value in self.problem_probabilities_.items())
            table_hash = hashlib.sha256(repr(encoded).encode('utf-8')).hexdigest()
        return {'model': 'problem', 'global_mean': self.global_mean_,
                'alpha': self.alpha, 'table_sha256': table_hash}

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('_hashed_table', None)
        if 'problem_probabilities_' in state:
            state['problem_probabilities_'] = dict(self.problem_probabilities_)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if 'problem_probabilities_' in state:
            self.problem_probabilities_ = MappingProxyType(dict(state['problem_probabilities_']))
            encoded = sorted((type(key).__name__, repr(key), float(value))
                             for key, value in self.problem_probabilities_.items())
            self._table_hash = hashlib.sha256(repr(encoded).encode('utf-8')).hexdigest()
            self._hashed_table = self.problem_probabilities_
