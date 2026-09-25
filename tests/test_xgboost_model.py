import importlib.util
import unittest
import numpy as np
import pandas as pd


class XGBoostModelTests(unittest.TestCase):
    def model(self):
        self.assertIsNotNone(importlib.util.find_spec('src.models.xgboost_model'), 'XGBoost adapter missing')
        from src.models.xgboost_model import XGBoostModel
        return XGBoostModel(n_estimators=3)

    def frame(self):
        y=np.tile([0,1],40)
        return pd.DataFrame({'skill_id':np.where(y,'2','1'), 'prior_skill_success':y*3,
            'prior_skill_failure':(1-y)*3, 'prior_skill_accuracy':y.astype(float),
            'prior_overall_accuracy':y.astype(float), 'history_length':np.full(80,3),
            'problem_difficulty':np.full(80,.5), 'correct':y, 'split':['train']*80})

    def test_encoding_keeps_numeric_zero_and_unknown_skill_all_zero(self):
        model=self.model().fit(self.frame())
        query=self.frame().iloc[:2].copy(); query['skill_id']=['2','999']
        expected=[[0,3,0,0,3,.5,0,1],[3,0,1,1,3,.5,0,0]]
        np.testing.assert_array_equal(model._design(query),expected)

    def test_scalar_batch_match_and_ignore_labels_and_raw_identifiers(self):
        model=self.model().fit(self.frame()); query=self.frame().iloc[:4].copy()
        before=model.global_parameters_snapshot(); predictions=model.predict_batch(query)
        self.assertLess(predictions[0],predictions[1])
        for col in ['correct','user_id','problem_id','order_id','source_row']:
            query[col]='unusable'
        np.testing.assert_allclose(predictions,model.predict_batch(query))
        np.testing.assert_allclose(predictions,[model.predict(row) for row in query.to_dict('records')])
        model.reset('a'); model.update({'correct':1})
        self.assertEqual(before,model.global_parameters_snapshot())
        self.assertEqual(model.predict_batch(query.iloc[:0]).size,0)

    def test_snapshot_detects_actual_booster_change(self):
        model=self.model().fit(self.frame()); before=model.global_parameters_snapshot()
        model.classifier.get_booster().set_attr(mutation_test='changed')
        self.assertNotEqual(before,model.global_parameters_snapshot())
        model.skills.append('new')
        self.assertNotEqual(before,model.global_parameters_snapshot())

    def test_train_validation_and_feature_validation(self):
        for change in ['heldout','one_class','nan','negative','probability','skill','missing']:
            bad=self.frame()
            if change=='heldout': bad.loc[0,'split']='test'
            elif change=='one_class': bad['correct']=1
            elif change=='nan': bad.loc[0,'history_length']=np.nan
            elif change=='negative': bad.loc[0,'prior_skill_success']=-1
            elif change=='probability': bad.loc[0,'problem_difficulty']=1.5
            elif change=='skill': bad.loc[0,'skill_id']=None
            else: bad=bad.drop(columns='prior_overall_accuracy')
            with self.subTest(change=change), self.assertRaises(ValueError): self.model().fit(bad)

if __name__=='__main__': unittest.main()
