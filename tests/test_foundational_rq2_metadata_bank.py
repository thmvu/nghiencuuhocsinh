import unittest

import pandas as pd

from src.rq2.candidates import build_foundational_metadata_pool


class FoundationalMetadataBankTests(unittest.TestCase):
    def setUp(self):
        self.train = pd.DataFrame([
            {'split': 'train', 'problem_id': 'p1', 'skill_id': '135', 'correct': 1,
             'rq2_text_eligible': False, 'Problem Body': 'private item text'},
            {'split': 'train', 'problem_id': 'p1', 'skill_id': '135', 'correct': 0,
             'rq2_text_eligible': False, 'Problem Body': 'private item text'},
            {'split': 'train', 'problem_id': 'p2', 'skill_id': '135', 'correct': 1,
             'rq2_text_eligible': True, 'Problem Body': 'private item text'},
            {'split': 'train', 'problem_id': 'p3', 'skill_id': '999', 'correct': 0,
             'rq2_text_eligible': True, 'Problem Body': 'private item text'},
            {'split': 'train', 'problem_id': 'p4', 'skill_id': '129', 'correct': 1,
             'rq2_text_eligible': False, 'Problem Body': 'private item text'},
        ])

    def test_pool_is_metadata_only_and_uses_train_success_rate(self):
        pool = build_foundational_metadata_pool(
            self.train, skill_ids={'135', '129'}, excluded_problem_ids={'p2'})
        self.assertEqual(pool, [
            {'problem_id': 'p1', 'skill_id': '135', 'difficulty': .5, 'support': 2},
            {'problem_id': 'p4', 'skill_id': '129', 'difficulty': 1.0, 'support': 1},
        ])
        self.assertTrue(all(set(row) == {
            'problem_id', 'skill_id', 'difficulty', 'support'} for row in pool))

    def test_rejects_non_train_rows(self):
        heldout = self.train.copy()
        heldout.loc[0, 'split'] = 'validation'
        with self.assertRaises(ValueError):
            build_foundational_metadata_pool(heldout, skill_ids={'135'})

    def test_rejects_nonbinary_outcomes(self):
        invalid = self.train.copy()
        invalid['correct'] = invalid['correct'].astype(float)
        invalid.loc[0, 'correct'] = .5
        with self.assertRaises(ValueError):
            build_foundational_metadata_pool(invalid, skill_ids={'135'})


if __name__ == '__main__':
    unittest.main()
