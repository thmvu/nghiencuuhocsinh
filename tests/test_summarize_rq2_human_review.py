import unittest

from scripts.summarize_rq2_human_review import FIELDS, summarize


class HumanReviewSummaryTests(unittest.TestCase):
    def test_paired_difference_and_missing_agent(self):
        key = [{'case_code': 'C01', 'option_code': 'a', 'policy': 'B+', 'status': 'VALID'},
               {'case_code': 'C01', 'option_code': 'b', 'policy': 'Agent', 'status': 'VALID'},
               {'case_code': 'C02', 'option_code': 'c', 'policy': 'B+', 'status': 'VALID'},
               {'case_code': 'C02', 'option_code': 'd', 'policy': 'Agent', 'status': 'INVALID'}]
        ratings = {('C01', 'a'): dict.fromkeys(FIELDS, 1),
                   ('C01', 'b'): dict.fromkeys(FIELDS, 2),
                   ('C02', 'c'): dict.fromkeys(FIELDS, 0)}
        result = summarize(key, ratings, ratings)
        self.assertEqual(result['n_invalid_agent_options'], 1)
        self.assertEqual(result['criteria'][FIELDS[0]]['mean_agent_minus_bplus'], 1)
        self.assertEqual(result['criteria'][FIELDS[0]]['n_paired_cases_with_complete_scores'], 1)

    def test_unfilled_sheets_are_rejected(self):
        key = [{'case_code': 'C01', 'option_code': 'a', 'policy': 'B+', 'status': 'VALID'}]
        blank = {('C01', 'a'): dict.fromkeys(FIELDS, None)}
        with self.assertRaises(ValueError):
            summarize(key, blank, blank)


if __name__ == '__main__':
    unittest.main()
