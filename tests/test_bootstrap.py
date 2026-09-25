import unittest
import pandas as pd
from src.evaluation.bootstrap import paired_student_brier_bootstrap


class BootstrapTests(unittest.TestCase):
    def test_resamples_whole_students_and_paired_differences(self):
        rows = pd.DataFrame({
            'user_id': ['a', 'a', 'b', 'b'], 'source_row': [0, 1, 2, 3],
            'correct': [1, 1, 0, 0], 'is_scored': [True] * 4,
            'ModelA': [1., 1., 1., 1.], 'ModelB': [0., 0., 0., 0.],
        })
        out = paired_student_brier_bootstrap(rows, 'ModelA', 'ModelB', iterations=100, seed=42)
        self.assertAlmostEqual(out['difference'], 0.)
        self.assertLessEqual(out['ci_low'], 0)
        self.assertGreaterEqual(out['ci_high'], 0)
        self.assertEqual(out['n_students'], 2)
        self.assertEqual(out['iterations'], 100)

    def test_rejects_duplicate_row_ids_and_mismatched_mask(self):
        rows = pd.DataFrame({'user_id': ['a', 'a'], 'source_row': [0, 0],
                             'correct': [1, 0], 'is_scored': [True, True],
                             'A': [.2, .3], 'B': [.1, .4]})
        with self.assertRaises(ValueError):
            paired_student_brier_bootstrap(rows, 'A', 'B', iterations=10, seed=42)


if __name__ == '__main__':
    unittest.main()
