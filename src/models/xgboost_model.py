"""Protocol A XGBoost adapter using train-only nominal skill encoding."""
import hashlib
import json

import numpy as np
import pandas as pd
from xgboost import XGBClassifier


NUMERIC_FEATURES = (
    'prior_skill_success', 'prior_skill_failure', 'prior_skill_accuracy',
    'prior_overall_accuracy', 'history_length', 'problem_difficulty',
)


class XGBoostModel:
    """Fit budgets and validation selection are controlled by the runner.

    Dense features deliberately preserve numeric and one-hot zeros as observed
    values: sparse absent entries would otherwise be treated as missing by XGB.
    """

    def __init__(self, max_depth=2, learning_rate=.05, n_estimators=100, seed=42):
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.n_estimators = n_estimators
        self.seed = seed
        self.skills = []
        self.classifier = None

    @staticmethod
    def _validated(df):
        if not df.columns.is_unique or not (set(NUMERIC_FEATURES) | {'skill_id'}).issubset(df.columns):
            raise ValueError('XGBoost requires unique skill and protocol numeric feature columns')
        if df.skill_id.isna().any() or df.skill_id.astype(str).str.strip().eq('').any():
            raise ValueError('skill_id cannot be missing or empty')
        values = df[list(NUMERIC_FEATURES)].to_numpy(dtype=np.float32)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError('XGBoost features must be finite and nonnegative')
        if (values[:, [2, 3, 5]] > 1).any():
            raise ValueError('Accuracy and difficulty features must be in [0, 1]')
        return df.skill_id.astype(str).to_numpy(), values

    def _design(self, df):
        skills, numeric = self._validated(df)
        vocabulary = {skill: index for index, skill in enumerate(self.skills)}
        matrix = np.zeros((len(df), len(NUMERIC_FEATURES) + len(self.skills)), dtype=np.float32)
        matrix[:, :len(NUMERIC_FEATURES)] = numeric
        for row, skill in enumerate(skills):
            index = vocabulary.get(skill)
            if index is not None:
                matrix[row, len(NUMERIC_FEATURES) + index] = 1
        return matrix

    def fit(self, train_df):
        if 'split' in train_df and not train_df.split.eq('train').all():
            raise ValueError('XGBoost fit accepts training rows only')
        skills, _ = self._validated(train_df)
        if ('correct' not in train_df or not train_df.correct.isin([0, 1]).all()
                or train_df.correct.nunique() != 2):
            raise ValueError('XGBoost fit requires both binary target classes')
        self.classifier = None
        self.skills = sorted(set(skills))
        classifier = XGBClassifier(
            max_depth=self.max_depth, learning_rate=self.learning_rate,
            n_estimators=self.n_estimators, objective='binary:logistic',
            tree_method='hist', n_jobs=1, random_state=self.seed,
            min_child_weight=5, subsample=1., colsample_bytree=1.,
            reg_lambda=1., reg_alpha=0., gamma=0.,
        )
        classifier.fit(self._design(train_df), train_df.correct.to_numpy(dtype=int))
        self.classifier = classifier
        return self

    def _require_fit(self):
        if self.classifier is None:
            raise RuntimeError('XGBoostModel is not fitted')

    def predict_batch(self, df):
        self._require_fit()
        if len(df) == 0:
            return np.empty(0, dtype=float)
        return self.classifier.predict_proba(self._design(df))[:, 1]

    def predict(self, row):
        return float(self.predict_batch(pd.DataFrame([dict(row)]))[0])

    def reset(self, user_id):
        """No state: shifted features supply the student's available history."""

    def update(self, row):
        """Current outcomes cannot alter the fitted global model."""

    def global_parameters_snapshot(self):
        self._require_fit()
        booster = self.classifier.get_booster()
        digest = hashlib.sha256(json.dumps(self.skills).encode())
        digest.update(booster.save_raw())
        digest.update(booster.save_config().encode())
        return {'sha256': digest.hexdigest()}
