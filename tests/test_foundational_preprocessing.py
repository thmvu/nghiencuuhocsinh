import unittest
import pandas as pd
from src.preprocessing.foundational import clean_primary, make_split, content_screen


class FoundationalTests(unittest.TestCase):
    def data(self):
        rows = [dict(id=str(k), user_id='s', problem_id='p', end_time=f'2020-01-01 00:00:0{k}',
                     discrete_score='1', answer_text='NA', hint_count='0', saw_answer='False',
                     **{'Unnamed: 0': str(k)}) for k in range(1, 5)]
        return pd.DataFrame(rows), pd.DataFrame([dict(problem_id='p', skill_id='a')])

    def test_duplicate_requires_id_and_keeps_first_source_row(self):
        rows, skills = self.data()
        duplicate = rows.iloc[[0]].copy()
        duplicate['Unnamed: 0'] = '99'
        out, counts = clean_primary(pd.concat([rows, duplicate], ignore_index=True), skills)
        self.assertEqual(len(out), 4)
        self.assertEqual(out.iloc[0].source_row, 0)
        self.assertEqual(counts[1]['removed'], 1)
        self.assertNotIn('answer_text', out.columns)

    def test_conflicting_id_and_valid_time_ties_fail(self):
        rows, skills = self.data()
        rows.loc[1, 'id'] = rows.loc[0, 'id']
        with self.assertRaises(ValueError):
            clean_primary(rows, skills)
        rows, skills = self.data()
        rows.loc[1, 'end_time'] = rows.loc[0, 'end_time']
        with self.assertRaises(ValueError):
            clean_primary(rows, skills)

    def test_missing_and_multiskill_filter_funnel(self):
        rows, skills = self.data()
        rows.loc[0, 'discrete_score'] = ''
        rows.loc[1, 'end_time'] = ''
        rows.loc[2, 'problem_id'] = 'multi'
        skills = pd.concat([skills, pd.DataFrame([dict(problem_id='multi', skill_id=x)
                                                 for x in ('a', 'b')])])
        out, counts = clean_primary(rows, skills)
        self.assertEqual(len(out), 1)
        self.assertEqual(sum(c['removed'] for c in counts), 3)

    def test_distinct_ids_with_same_missing_time_are_preserved_until_time_filter(self):
        rows, skills = self.data()
        rows.loc[1, rows.columns.difference(['id', 'Unnamed: 0'])] = rows.loc[0, rows.columns.difference(['id', 'Unnamed: 0'])]
        rows.loc[[0, 1], 'end_time'] = ''
        out, counts = clean_primary(rows, skills)
        self.assertEqual(counts[1]['removed'], 0)
        self.assertEqual(len(out), 2)

    def test_split_is_disjoint_reproducible_independent_of_row_order(self):
        a = make_split([str(i) for i in range(20)])
        b = make_split([str(i) for i in reversed(range(20))])
        self.assertEqual(a, b)
        self.assertEqual(len(a), 20)
        self.assertEqual(sum(v == 'train' for v in a.values()), 14)

    def test_text_only_does_not_auto_pass(self):
        p = {'Problem Body': '<p>Solve \\(x+1=2\\)</p>', 'Answer Types': 'Numeric',
             'Fill-in Answers': '1', 'Fill-in Options': '1'}
        result = content_screen(p, conflict=False, skill_count=1)
        self.assertFalse(result['rq2_text_eligible'])
        self.assertIn('manual_review_required', result['reasons'])
        self.assertIn('x+1=2', result['normalized_body'])
        p['Problem Body'] = '<p>See figure</p><img src="x.png">'
        result = content_screen(p, conflict=True, skill_count=1)
        self.assertIn('media_or_external_asset', result['reasons'])
        self.assertIn('metadata_conflict', result['reasons'])
