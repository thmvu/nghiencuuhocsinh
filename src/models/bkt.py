"""Bounded, no-forgetting BKT with independent student-skill histories."""
import hashlib
import json
from copy import deepcopy

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.evaluation.sequential import sequential_predict

BOUNDS = ((0.001, 0.999), (0.001, 0.5), (0.001, 0.3), (0.001, 0.3))
DEFAULT_CONFIG = {
    'minimum_train_interactions': 100,
    'bounds': dict(zip(('L0', 'T', 'G', 'S'), BOUNDS)),
    'initializations_L0_T_G_S': [[.2, .1, .2, .1], [.5, .05, .1, .2], [.8, .2, .25, .05]],
    'maxiter': 500, 'maxfun': 10000, 'ftol': 1e-9,
    'maximum_fit_groups': 106, 'maximum_optimizer_runs': 318,
}


def _pack_sequences(sequences):
    """Pack each time position across sequences; never concatenate histories."""
    sequences = [np.asarray(sequence, dtype=float) for sequence in sequences]
    if not sequences or any(sequence.ndim != 1 or len(sequence) == 0
                            or not np.isin(sequence, [0, 1]).all() for sequence in sequences):
        raise ValueError('nonempty binary sequences required')
    lengths = np.array([len(sequence) for sequence in sequences])
    packed = []
    for step in range(int(lengths.max())):
        active = np.flatnonzero(lengths > step)
        packed.append((active, np.array([sequences[index][step] for index in active])))
    return len(sequences), packed


def _packed_nll(parameters, packed):
    l0, transition, guess, slip = parameters
    n_sequences, steps = packed
    log_unknown = np.full(n_sequences, np.log1p(-l0), dtype=float)
    log_known = np.full(n_sequences, np.log(l0), dtype=float)
    log_transition = np.log(transition)
    log_stay_unknown = np.log1p(-transition)
    loss = 0.0
    for active, labels in steps:
        known_observation = log_known[active] + np.where(labels == 1, np.log1p(-slip), np.log(slip))
        unknown_observation = log_unknown[active] + np.where(labels == 1, np.log(guess), np.log1p(-guess))
        log_observed = np.logaddexp(known_observation, unknown_observation)
        loss -= float(log_observed.sum())
        log_posterior_unknown = unknown_observation - log_observed
        log_unknown[active] = log_posterior_unknown + log_stay_unknown
        log_known[active] = np.logaddexp(known_observation - log_observed,
                                        log_posterior_unknown + log_transition)
    return loss


def sequence_negative_log_likelihood(parameters, sequences):
    """Return sequence likelihood using parameter order (L0,T,G,S)."""
    values = np.asarray(parameters, dtype=float)
    if values.shape != (4,) or not np.isfinite(values).all() or ((values <= 0) | (values >= 1)).any():
        raise ValueError('four finite probabilities strictly between zero and one required')
    return _packed_nll(values, _pack_sequences(sequences))


class BKT:
    def __init__(self, config=None):
        self.config = deepcopy(DEFAULT_CONFIG)
        if config is not None:
            self.config.update(deepcopy(config))
        self.bounds = tuple(tuple(self.config['bounds'][key]) for key in ('L0', 'T', 'G', 'S'))
        if self.bounds != BOUNDS:
            raise ValueError('BKT parameter bounds must match Lock A')
        if self.config.get('forgetting', 0) != 0:
            raise ValueError('Lock A forbids forgetting')
        self._user = None
        self._state = {}

    @classmethod
    def from_parameters(cls, pooled, skill_parameters=None):
        """Construct an adapter from existing fitted/checkpoint parameters."""
        model = cls()
        model.pooled_parameters_ = model._validate_parameters(pooled)
        model.skill_parameters_ = {key: model._validate_parameters(value)
                                   for key, value in (skill_parameters or {}).items()}
        model.fit_diagnostics_ = {'source': 'supplied_parameters'}
        return model

    def _validate_parameters(self, parameters):
        values = np.asarray(parameters, dtype=float)
        if values.shape != (4,) or not np.isfinite(values).all():
            raise ValueError('four finite BKT parameters required')
        if any(not low <= value <= high for value, (low, high) in zip(values, self.bounds)):
            raise ValueError('parameters outside Lock A bounds')
        return tuple(float(value) for value in values)

    def _fit_group(self, sequences):
        packed = _pack_sequences(sequences)
        runs = []
        candidates = []
        for start in self.config['initializations_L0_T_G_S']:
            result = minimize(_packed_nll, self._validate_parameters(start), args=(packed,),
                              method='L-BFGS-B', bounds=self.bounds,
                              options={key: self.config[key] for key in ('maxiter', 'maxfun', 'ftol')})
            valid = bool(result.success and np.isfinite(result.fun) and np.isfinite(result.x).all())
            runs.append({'success': valid, 'nll': float(result.fun) if np.isfinite(result.fun) else None,
                         'iterations': int(result.nit), 'function_evaluations': int(result.nfev),
                         'message': str(result.message)})
            if valid:
                candidates.append((float(result.fun), self._validate_parameters(result.x)))
        best = min(candidates, key=lambda candidate: candidate[0])[1] if candidates else None
        return best, {'runs': runs, 'converged': best is not None}

    def fit(self, train):
        required = {'user_id', 'skill_id', 'order_id', 'correct'}
        if train.empty or not train.columns.is_unique or not required.issubset(train.columns):
            raise ValueError('nonempty train data with unique required columns required')
        if train[list(required)].isna().any().any() or not train.correct.isin([0, 1]).all():
            raise ValueError('nonmissing identities and binary correct required')
        if 'split' in train and not train.split.eq('train').all():
            raise ValueError('BKT fit requires train rows only')
        order = pd.to_numeric(train.order_id, errors='coerce')
        if not np.isfinite(order).all():
            raise ValueError('order_id must be finite numeric chronology')
        frame = train.assign(order_id=order)
        if frame.duplicated(['user_id', 'order_id']).any():
            raise ValueError('duplicate student/order chronology')
        frame = frame.sort_values(['user_id', 'order_id'], kind='stable')
        sequences = [group.correct.to_numpy(dtype=float) for _, group in
                     frame.groupby(['user_id', 'skill_id'], sort=False)]
        eligible = [(skill, group) for skill, group in frame.groupby('skill_id', sort=False)
                    if len(group) >= self.config['minimum_train_interactions'] and group.correct.nunique() == 2]
        n_groups = 1 + len(eligible)
        if (n_groups > self.config['maximum_fit_groups'] or
                n_groups * len(self.config['initializations_L0_T_G_S']) > self.config['maximum_optimizer_runs']):
            raise ValueError('BKT optimization budget exceeded')
        pooled, diagnostics = self._fit_group(sequences)
        if pooled is None:
            raise RuntimeError('pooled BKT fit failed for all starts; stop development')
        skills = {}
        skill_diagnostics = {}
        for skill, group in eligible:
            params, details = self._fit_group([student.correct.to_numpy(dtype=float)
                                              for _, student in group.groupby('user_id', sort=False)])
            details['pooled_fallback'] = params is None
            skill_diagnostics[skill] = details
            if params is not None:
                skills[skill] = params
        self.pooled_parameters_ = pooled
        self.skill_parameters_ = skills
        self.fit_diagnostics_ = {'pooled': diagnostics, 'skills': skill_diagnostics,
                                 'fit_groups': n_groups, 'optimizer_runs': n_groups * len(self.config['initializations_L0_T_G_S']),
                                 'sparse_or_one_class_skills': int(frame.skill_id.nunique() - len(eligible))}
        self._user, self._state = None, {}
        return self

    def _parameters(self, skill):
        if not hasattr(self, 'pooled_parameters_'):
            raise RuntimeError('fit BKT before predicting')
        return self.skill_parameters_.get(skill, self.pooled_parameters_)

    def reset(self, user_id):
        self._user, self._state = user_id, {}

    def _before(self, row):
        if self._user is None or row.get('user_id', self._user) != self._user:
            raise ValueError('reset model for the current student before prediction/update')
        skill = row['skill_id']
        parameters = self._parameters(skill)
        return skill, self._state.get(skill, (np.log1p(-parameters[0]), np.log(parameters[0]))), parameters

    def predict(self, row):
        _, (log_unknown, log_known), (_, _, guess, slip) = self._before(row)
        return float(np.exp(log_known) * (1 - slip) + np.exp(log_unknown) * guess)

    def update(self, row):
        label = row['correct']
        if label not in (0, 1):
            raise ValueError('correct must be binary')
        skill, (log_unknown, log_known), (_, transition, guess, slip) = self._before(row)
        known_observation = log_known + (np.log1p(-slip) if label == 1 else np.log(slip))
        unknown_observation = log_unknown + (np.log(guess) if label == 1 else np.log1p(-guess))
        log_observed = np.logaddexp(known_observation, unknown_observation)
        log_posterior_unknown = unknown_observation - log_observed
        self._state[skill] = (log_posterior_unknown + np.log1p(-transition),
                              np.logaddexp(known_observation - log_observed,
                                           log_posterior_unknown + np.log(transition)))

    def predict_batch(self, df):
        """Predict sequentially, observe each label afterward, restore input order."""
        predictions = sequential_predict(df, self, warmup=0)
        return predictions.set_index('source_row').probability.reindex(df.source_row).to_numpy(dtype=float)

    def global_parameters_snapshot(self):
        self._parameters(None)
        payload = {'pooled': list(self.pooled_parameters_),
                   'skills': sorted((type(key).__name__, repr(key), list(value))
                                    for key, value in self.skill_parameters_.items())}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode('utf-8')).hexdigest()
        return {'model': 'BKT', 'parameters_sha256': digest}
