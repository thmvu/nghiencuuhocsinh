import unittest
import importlib.util
import pandas as pd
import numpy as np


class PreprocessingTests(unittest.TestCase):
    def api(self):
        spec = importlib.util.find_spec('src.preprocessing.pipeline')
        self.assertIsNotNone(spec, 'Preprocessing pipeline must exist')
        from src.preprocessing import pipeline
        return pipeline

    def frame(self):
        return pd.DataFrame({'user_id':['b','a','a','a','a','b'],
          'problem_id':['p','p','p','q','q','r'], 'skill_id':['1','1','1','2','1_2',None],
          'order_id':[1,2,1,3,4,2], 'correct':[0,0,1,1,0,1]})

    def test_clean_retains_repeated_problems_and_source_positions(self):
        out = self.api().clean_interactions(self.frame())
        self.assertEqual(out.source_row.tolist(), [2,1,3,0])
        self.assertEqual(out.skill_id.tolist(), ['1','1','2','1'])
        self.assertEqual(out.user_id.tolist(), ['a','a','a','b'])

    def test_clean_rejects_invalid_targets_identity_and_duplicate_order(self):
        api = self.api()
        for column, value in [('correct',2),('correct',None),('user_id',None),('problem_id',''),('order_id',None)]:
            with self.subTest(column=column,value=value):
                bad=self.frame(); bad.loc[0,column]=value
                with self.assertRaises(ValueError): api.clean_interactions(bad)
        bad=self.frame(); bad.loc[1,'order_id']=1
        with self.assertRaises(ValueError): api.clean_interactions(bad)

    def test_clean_rejects_unknown_skill_encoding_and_bad_source_identity(self):
        api = self.api()
        for skill in ['1;2', 'unknown', '1__2']:
            bad = self.frame(); bad.loc[0, 'skill_id'] = skill
            with self.subTest(skill=skill), self.assertRaises(ValueError):
                api.clean_interactions(bad)
        for source in [[0, 0, 2, 3, 4, 5], [None, 1, 2, 3, 4, 5]]:
            bad = self.frame(); bad['source_row'] = source
            with self.assertRaises(ValueError): api.clean_interactions(bad)

    def test_split_reuses_manifest_and_rejects_overlap_or_missing(self):
        api=self.api(); df=api.clean_interactions(self.frame())
        manifest={'students':{'train':['a'],'validation':['b'],'test':[]}}
        self.assertEqual(api.apply_split(df,manifest).split.tolist(), ['train']*3+['validation'])
        for wrong in [{'students':{'train':['a'],'validation':['a','b'],'test':[]}},
                      {'students':{'train':['a'],'validation':[],'test':[]}}]:
            with self.assertRaises(ValueError): api.apply_split(df,wrong)

    def test_history_is_shifted_and_warmup_counts_all_skills(self):
        api=self.api(); df=api.clean_interactions(self.frame())
        out=api.add_history_features(df,warmup=2)
        self.assertEqual(out.prior_skill_success.tolist(), [0,1,0,0])
        self.assertEqual(out.prior_skill_failure.tolist(), [0,0,0,0])
        self.assertEqual(out.prior_skill_count.tolist(), [0,1,0,0])
        self.assertEqual(out.prior_skill_accuracy.tolist(), [.5,1,.5,.5])
        self.assertEqual(out.prior_overall_accuracy.tolist(), [.5,1,.5,.5])
        self.assertEqual(out.history_length.tolist(), [0,1,2,0])
        self.assertEqual(out.scored.tolist(), [False,False,True,False])
        changed=df.copy(); changed.loc[1:,'correct']=1-changed.loc[1:,'correct']
        cols=['prior_skill_success','prior_skill_failure','prior_overall_accuracy']
        pd.testing.assert_frame_equal(out.loc[:1,cols],api.add_history_features(changed).loc[:1,cols])

    def difficulty_frame(self):
        return pd.DataFrame({'user_id':['a','a','b','b','v','t'],
          'problem_id':['p','q','p','r','p','new'], 'correct':[1,1,0,0,1,0],
          'split':['train']*4+['validation','test']})

    def test_oof_excludes_entire_student_and_heldout_targets(self):
        api=self.api(); df=self.difficulty_frame()
        out=api.add_problem_difficulty(df,n_splits=2,alpha=10)
        np.testing.assert_allclose(out.problem_difficulty,[0,0,1,1,.5,.5])
        changed=df.copy(); changed.loc[4:,'correct']=1-changed.loc[4:,'correct']
        np.testing.assert_allclose(api.add_problem_difficulty(changed,n_splits=2).problem_difficulty,out.problem_difficulty)
        changed=df.copy(); changed.loc[:1,'correct']=0
        np.testing.assert_allclose(api.add_problem_difficulty(changed,n_splits=2).problem_difficulty[:2],[0,0])

    def test_difficulty_smoothing_uses_training_global_and_unseen_fallback(self):
        api=self.api(); df=self.difficulty_frame(); df.loc[3,'correct']=1
        out=api.add_problem_difficulty(df,n_splits=2,alpha=2)
        self.assertAlmostEqual(out.loc[4,'problem_difficulty'],.625)
        self.assertAlmostEqual(out.loc[5,'problem_difficulty'],.75)
        with self.assertRaises(ValueError): api.add_problem_difficulty(df,n_splits=3)
        with self.assertRaises(ValueError): api.add_problem_difficulty(df,n_splits=2,alpha=-1)

if __name__ == '__main__':
    unittest.main()
