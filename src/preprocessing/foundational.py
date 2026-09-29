"""FoundationalASSIST v4: structural cleaning and conservative content screening."""
import re
import unicodedata
import numpy as np
import pandas as pd

BUSINESS = ['user_id', 'problem_id', 'end_time', 'discrete_score',
            'answer_text', 'hint_count', 'saw_answer']


def clean_primary(raw, skills):
    if not {'id', *BUSINESS} <= set(raw.columns):
        raise ValueError('missing interaction columns')
    frame = raw.copy()
    frame['source_row'] = np.arange(len(frame))
    funnel = [{'stage': 'raw', 'rows': len(frame), 'removed': 0}]

    def record(stage, previous):
        funnel.append({'stage': stage, 'rows': len(frame), 'removed': previous - len(frame)})

    previous = len(frame)
    frame = frame.drop_duplicates(['id', *BUSINESS], keep='first').copy()
    record('exact_dedup_with_id', previous)
    if frame.id.duplicated().any():
        raise ValueError('conflicting interaction IDs require review')
    if frame[['id', 'user_id', 'problem_id']].isna().any().any() or frame[['id', 'user_id', 'problem_id']].eq('').any().any():
        raise ValueError('missing identity')
    score = pd.to_numeric(frame.discrete_score, errors='coerce')
    previous = len(frame)
    frame = frame.loc[score.isin([0, 1])].copy()
    frame['correct'] = score.loc[frame.index].astype('int64')
    record('valid_binary_label', previous)
    timestamp = pd.to_datetime(frame.end_time, errors='coerce', utc=True, format='mixed')
    previous = len(frame)
    frame = frame.loc[timestamp.notna()].copy()
    frame['timestamp'] = timestamp.loc[frame.index]
    record('valid_time', previous)
    mapping = skills[['problem_id', 'skill_id']].drop_duplicates()
    mapping = mapping.dropna().loc[lambda x: x.problem_id.ne('') & x.skill_id.ne('')]
    counts = mapping.groupby('problem_id').skill_id.nunique()
    previous = len(frame)
    frame = frame.loc[frame.problem_id.isin(counts.index)].copy()
    record('valid_skill_mapping', previous)
    previous = len(frame)
    frame = frame.loc[frame.problem_id.isin(counts[counts.eq(1)].index)].copy()
    record('single_skill', previous)
    single = mapping.loc[mapping.problem_id.isin(counts[counts.eq(1)].index)]
    frame = frame.merge(single, on='problem_id', how='left', validate='many_to_one')
    if frame.duplicated(['user_id', 'timestamp']).any():
        raise ValueError('ambiguous student chronology; do not infer order from id')
    frame = frame.sort_values(['user_id', 'timestamp'], kind='stable').reset_index(drop=True)
    frame['order_id'] = frame.groupby('user_id', sort=False).cumcount()
    return frame[['source_row', 'id', 'user_id', 'problem_id', 'skill_id',
                  'timestamp', 'order_id', 'correct']], funnel


def make_split(students, seed=42):
    values = np.asarray(sorted(set(students)), dtype=object)
    rng = np.random.default_rng(seed)
    rng.shuffle(values)
    n_train, n_validation = int(len(values) * .70), int(len(values) * .15)
    return {str(student): ('train' if index < n_train else
                          'validation' if index < n_train + n_validation else 'test')
            for index, student in enumerate(values)}


def content_screen(problem, *, conflict, skill_count):
    """Screen only: never certify semantic completeness without review.

    Preserve HTML/LaTeX. NFC + newline normalization does not strip math tags.
    Answer/option parsing and dependency checks remain manual at this stage.
    """
    body = unicodedata.normalize('NFC', str(problem.get('Problem Body', '')))
    body = body.replace('\r\n', '\n').replace('\r', '\n')
    combined = '\n'.join(str(problem.get(c, '')) for c in
                         ('Problem Body', 'Fill-in Options', 'Multiple Choice Options'))
    media = bool(re.search(r'<\s*(?:img|svg|video|audio|canvas|iframe|object|embed)\b|'
                           r'(?:src|href)\s*=|url\s*\(|data:image', combined, re.I))
    reasons = []
    if conflict:
        reasons.append('metadata_conflict')
    if not re.sub(r'<[^>]*>', '', body).strip():
        reasons.append('empty_or_nontext_body')
    if media:
        reasons.append('media_or_external_asset')
    if skill_count != 1:
        reasons.append('not_single_skill')
    answer_type = problem.get('Answer Types', '')
    if answer_type in ('Multiple Choice', 'Check All That Apply'):
        if not problem.get('Multiple Choice Options') or not problem.get('Multiple Choice Answers'):
            reasons.append('missing_options_or_answer')
    elif answer_type in ('Numeric', 'Algebraic Expression', 'Exact Match', 'Ordering',
                         'Exact Fraction', 'Drop Down', 'Numeric Expression'):
        if not problem.get('Fill-in Answers'):
            reasons.append('missing_answer')
        if answer_type in ('Ordering', 'Drop Down') and not problem.get('Fill-in Options'):
            reasons.append('missing_options')
    else:
        reasons.append('unsupported_or_mixed_answer_type')
    auto_pass = not reasons
    reasons.append('manual_review_required')
    return {'normalized_body': body, 'has_media_signal': media,
            'automatic_screen_pass': auto_pass, 'rq2_text_eligible': False,
            'reasons': reasons}
