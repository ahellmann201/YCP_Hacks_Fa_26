import unittest
from sample_dates import normalize_sample_date, same_sample_date
from reading_quality import guard_readings


class DateTests(unittest.TestCase):
    def test_full_dates_normalize_separators_and_keep_digits(self):
        for value in ['4.13.26','4-13-26','4/13/2026','4.13-26']:
            self.assertEqual(normalize_sample_date(value),'04/13/2026')
        self.assertTrue(same_sample_date('4-13-26','04/13/2026'))
        self.assertFalse(same_sample_date('4-13-34','04/13/2026'))

    def test_partial_and_invalid_dates_do_not_gain_missing_digits(self):
        self.assertEqual(normalize_sample_date('9.20'),'9/20')
        self.assertEqual(normalize_sample_date('8/7'),'8/7')
        self.assertEqual(normalize_sample_date('92866'),'92866')
        self.assertEqual(normalize_sample_date('2/30/26'),'2/30/26')

    def test_normalization_preserves_matching_ocr_confidence(self):
        result={'images':[{'fields':{'date_sampled':'4.13.26'},'field_scores':{'date_sampled':.99}}]}
        fields,_,warnings=guard_readings({'date_sampled':'04/13/2026'},'large',result,'2026-11-07')
        self.assertEqual(fields['date_sampled'],'04/13/2026')
        self.assertNotIn('date_sampled',warnings)


if __name__=='__main__':
    unittest.main()
