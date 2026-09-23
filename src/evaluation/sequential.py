"""Leakage-aware sequential evaluation; no model fitting is performed here."""
import json
import math
from numbers import Integral, Real
from types import MappingProxyType

import pandas as pd

IDENTITY_COLUMNS = ('user_id', 'order_id', 'problem_id', 'skill_id', 'source_row')
PREDICT_COLUMNS = IDENTITY_COLUMNS + (
    'prior_skill_success', 'prior_skill_failure', 'prior_skill_accuracy',
    'prior_overall_accuracy', 'history_length', 'problem_difficulty',
)
OUTPUT_COLUMNS = IDENTITY_COLUMNS + ('correct', 'probability', 'history_length', 'is_scored')


def sequential_predict(df, model, warmup=5):
    """Return every prediction with an explicit post-warmup scoring mask.

    Model contract: reset(user_id) clears student state; predict(mapping) reads
    pre-response state; update(mapping) observes correct only after prediction.
    All three methods MUST leave fitted global parameters unchanged. Adapters
    may expose global_parameters_snapshot() returning JSON-serializable fitted
    parameters to enforce this contract at each callback. Without that hook,
    immutability remains an adapter obligation, not an introspection guarantee.
    Input features must already be leakage-safe (shifted / cross-fitted).
    The evaluator overwrites history_length with the actual sequence position.
    """
    if isinstance(warmup, bool) or not isinstance(warmup, Integral) or warmup < 0:
        raise ValueError('warmup must be a nonnegative integer')
    required = set(IDENTITY_COLUMNS) | {'correct'}
    if not df.columns.is_unique or not required.issubset(df.columns):
        raise ValueError('unique required identity and correct columns are required')
    if df[list(required)].isna().any().any():
        raise ValueError('identity and labels cannot be missing')
    if df.source_row.duplicated().any() or df.duplicated(['user_id', 'order_id']).any():
        raise ValueError('source_row and student/order identities must be unique')
    if not df.correct.isin([0, 1]).all():
        raise ValueError('correct must be binary')
    order = pd.to_numeric(df.order_id, errors='coerce')
    if not order.map(lambda value: math.isfinite(value)).all():
        raise ValueError('order_id must be finite numeric chronology')
    frame = df.assign(order_id=order).sort_values(
        ['user_id', 'order_id', 'source_row'], kind='stable'
    )
    snapshot = getattr(model, 'global_parameters_snapshot', None)
    frozen = json.dumps(snapshot(), sort_keys=True, allow_nan=False) if snapshot else None

    def check_frozen():
        if snapshot and json.dumps(snapshot(), sort_keys=True, allow_nan=False) != frozen:
            raise RuntimeError('model changed fitted global parameters during evaluation')

    output = []
    for user_id, sequence in frame.groupby('user_id', sort=False):
        model.reset(user_id)
        check_frozen()
        for history_length, row in enumerate(sequence.to_dict('records')):
            before = {key: row[key] for key in PREDICT_COLUMNS if key in row}
            before['history_length'] = history_length
            probability = model.predict(MappingProxyType(before))
            check_frozen()
            if (isinstance(probability, bool) or not isinstance(probability, Real)
                    or not math.isfinite(probability) or not 0 <= probability <= 1):
                raise ValueError('prediction must be a finite probability in [0, 1]')
            output.append({
                **{key: row[key] for key in IDENTITY_COLUMNS},
                'correct': int(row['correct']), 'probability': float(probability),
                'history_length': history_length, 'is_scored': history_length >= warmup,
            })
            model.update(MappingProxyType({**before, 'correct': int(row['correct'])}))
            check_frozen()
    result = pd.DataFrame(output, columns=OUTPUT_COLUMNS)
    result['is_scored'] = result['is_scored'].astype(bool)
    return result
