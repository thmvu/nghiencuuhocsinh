"""RQ1 metrics on the common scored-row mask."""
import numpy as np
from sklearn.metrics import roc_auc_score


def evaluate_predictions(predictions):
    """Validate predictions and summarize only explicitly scored rows.

    No scored rows yields zero counts and None metrics; one-class AUC is None.
    Brier uses original probabilities; log loss clips at the protocol's 1e-15.
    Validation covers all supplied rows, including unscored warm-up rows.
    """
    required = {'user_id', 'source_row', 'correct', 'probability', 'is_scored'}
    if not predictions.columns.is_unique or not required.issubset(predictions.columns):
        raise ValueError('unique required prediction columns are required')
    if predictions[list(required)].isna().any().any():
        raise ValueError('prediction values and identities cannot be missing')
    if not predictions.is_scored.map(lambda value: isinstance(value, (bool, np.bool_))).all():
        raise ValueError('is_scored must contain booleans')
    if predictions.source_row.duplicated().any():
        raise ValueError('source_row identities must be unique')
    if not predictions.correct.isin([0, 1]).all():
        raise ValueError('correct must be binary')
    if not predictions.probability.map(
        lambda value: isinstance(value, (int, float, np.integer, np.floating))
        and not isinstance(value, (bool, np.bool_))
    ).all():
        raise ValueError('probabilities must be numeric')
    probability = predictions.probability.to_numpy(dtype=float)
    if not np.isfinite(probability).all() or ((probability < 0) | (probability > 1)).any():
        raise ValueError('probabilities must be finite and in [0, 1]')
    scored = predictions.loc[predictions.is_scored.astype(bool)]
    result = {'n_rows': len(scored), 'n_students': int(scored.user_id.nunique()),
              'brier_score': None, 'roc_auc': None, 'log_loss': None}
    if scored.empty:
        return result
    y = scored.correct.to_numpy(dtype=float)
    p = scored.probability.to_numpy(dtype=float)
    clipped = np.clip(p, 1e-15, 1 - 1e-15)
    result['brier_score'] = float(np.mean((p - y) ** 2))
    result['log_loss'] = float(-np.mean(y * np.log(clipped) + (1 - y) * np.log1p(-clipped)))
    if len(np.unique(y)) == 2:
        result['roc_auc'] = float(roc_auc_score(y, p))
    return result
