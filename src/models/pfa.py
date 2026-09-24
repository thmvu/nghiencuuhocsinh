"""Skill-specific Performance Factors Analysis with train-only vocabulary."""
import hashlib
import json
import warnings

import numpy as np
from scipy import sparse
from scipy.special import expit
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression


class PFAConvergenceError(RuntimeError):
    """The configured optimizer budget was exhausted without convergence."""


class PFA:
    """L2 logistic PFA; fit budgets and candidate selection belong to the runner."""

    def __init__(self, C=.01, max_iter=2000, tol=1e-6, seed=42):
        self.C, self.max_iter, self.tol, self.seed = C, max_iter, tol, seed
        self.classifier = None
        self.skills = []

    @staticmethod
    def _validated(df):
        columns = ['skill_id', 'prior_skill_success', 'prior_skill_failure']
        if not set(columns).issubset(df.columns):
            raise ValueError('PFA requires skill and prior success/failure features')
        if df.skill_id.isna().any():
            raise ValueError('skill_id cannot be missing')
        histories = df[columns[1:]].to_numpy(dtype=float)
        if not np.isfinite(histories).all() or (histories < 0).any():
            raise ValueError('Prior counts must be finite and nonnegative')
        return df.skill_id.astype(str).to_numpy(), histories

    def _design(self, df):
        skill, counts = self._validated(df)
        vocabulary = {value: index for index, value in enumerate(self.skills)}
        indices = np.array([vocabulary.get(value, -1) for value in skill])
        rows = np.flatnonzero(indices >= 0)
        onehot = sparse.csr_matrix((np.ones(len(rows)), (rows, indices[rows])), shape=(len(df), len(self.skills)))
        return sparse.hstack([onehot, onehot.multiply(counts[:, 0:1]), onehot.multiply(counts[:, 1:2])], format='csr')

    def fit(self, train_df):
        if 'split' in train_df and not train_df.split.eq('train').all():
            raise ValueError('PFA fit accepts training rows only')
        skills, _ = self._validated(train_df)
        if 'correct' not in train_df or not train_df.correct.isin([0, 1]).all() or train_df.correct.nunique() != 2:
            raise ValueError('PFA fit requires both binary target classes')
        self.classifier = None
        self.skills = sorted(set(skills))
        classifier = LogisticRegression(C=self.C, penalty='l2', solver='lbfgs',
                                        fit_intercept=True, max_iter=self.max_iter,
                                        tol=self.tol, random_state=self.seed)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', ConvergenceWarning)
            classifier.fit(self._design(train_df), train_df.correct.to_numpy(dtype=int))
        if any(issubclass(item.category, ConvergenceWarning) for item in caught):
            raise PFAConvergenceError('PFA candidate did not converge within configured budget')
        self.classifier = classifier
        return self

    def _require_fit(self):
        if self.classifier is None:
            raise RuntimeError('PFA is not fitted')

    def predict_batch(self, df):
        self._require_fit()
        if len(df) == 0:
            return np.empty(0, dtype=float)
        return self.classifier.predict_proba(self._design(df))[:, 1]

    def predict(self, row):
        self._require_fit()
        success = float(row['prior_skill_success'])
        failure = float(row['prior_skill_failure'])
        if not np.isfinite([success, failure]).all() or min(success, failure) < 0:
            raise ValueError('Prior counts must be finite and nonnegative')
        logit = float(self.classifier.intercept_[0])
        skill = str(row['skill_id'])
        if skill in self.skills:
            index = self.skills.index(skill)
            size = len(self.skills)
            weights = self.classifier.coef_[0]
            logit += weights[index] + success * weights[size + index] + failure * weights[2 * size + index]
        return float(expit(logit))

    def reset(self, user_id):
        """No state: validated shifted features supply the student's history."""

    def update(self, row):
        """No state: current outcomes never modify fitted PFA coefficients."""

    def global_parameters_snapshot(self):
        self._require_fit()
        digest = hashlib.sha256(json.dumps(self.skills, ensure_ascii=True).encode())
        for values in [self.classifier.coef_, self.classifier.intercept_, self.classifier.classes_]:
            array = np.ascontiguousarray(values)
            digest.update(str((array.shape, array.dtype.str)).encode())
            digest.update(array.tobytes())
        return {'sha256': digest.hexdigest()}
