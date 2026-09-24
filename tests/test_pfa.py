import importlib.util
import unittest
import numpy as np
import pandas as pd
from scipy.special import expit


class PFATests(unittest.TestCase):
    def model(self, **kwargs):
        self.assertIsNotNone(importlib.util.find_spec('src.models.pfa'), 'PFA implementation missing')
        from src.models.pfa import PFA
        return PFA(**kwargs)

    def frame(self):
        return pd.DataFrame({'skill_id':['a','b','a','b'],
          'prior_skill_success':[0,0,1,2], 'prior_skill_failure':[0,1,1,2],
          'correct':[0,1,1,0], 'split':['train']*4})

    def test_skill_specific_logits_and_unseen_global_intercept(self):
        model=self.model().fit(self.frame())
        model.classifier.coef_[:]=[[.2,-.3,.4,.5,-.6,-.7]]
        model.classifier.intercept_[:]=.1
        query=pd.DataFrame({'skill_id':['a','b','new'],
          'prior_skill_success':[2,3,100], 'prior_skill_failure':[1,2,100]})
        np.testing.assert_allclose(model.predict_batch(query),expit([.5,-.1,.1]))

    def test_batch_matches_scalar_and_ignores_current_label(self):
        model=self.model().fit(self.frame()); query=self.frame()
        before=model.global_parameters_snapshot()
        batch=model.predict_batch(query)
        np.testing.assert_allclose(batch,[model.predict(row) for row in query.to_dict('records')])
        query['correct']=1-query.correct
        np.testing.assert_allclose(batch,model.predict_batch(query))
        model.reset('x'); model.update({'correct':1})
        self.assertEqual(before,model.global_parameters_snapshot())
        model.classifier.coef_[0,0]+=1
        self.assertNotEqual(before,model.global_parameters_snapshot())

    def test_heldout_fit_one_class_and_invalid_history_rejected(self):
        for change in ['heldout','oneclass','negative','missing']:
            bad=self.frame()
            if change=='heldout': bad.loc[0,'split']='validation'
            elif change=='oneclass': bad['correct']=1
            elif change=='negative': bad.loc[0,'prior_skill_success']=-1
            else: bad.loc[0,'prior_skill_failure']=np.nan
            with self.subTest(change=change), self.assertRaises(ValueError): self.model().fit(bad)

    def test_nonconvergence_invalidates_candidate(self):
        self.model()
        from src.models import pfa
        self.assertTrue(hasattr(pfa, 'PFAConvergenceError'))
        with self.assertRaises(pfa.PFAConvergenceError):
            self.model(C=10,max_iter=1,tol=1e-12).fit(self.frame())

if __name__=='__main__': unittest.main()
