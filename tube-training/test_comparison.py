import unittest
from compare_recognizers import formatted_match


class FormattingComparisonTests(unittest.TestCase):
    def test_separator_equivalence(self):
        self.assertTrue(formatted_match('date_sampled','9.27.26','09/27/2026'))

    def test_does_not_repair_missing_or_wrong_digits(self):
        self.assertFalse(formatted_match('date_sampled','9/20','9120'))
        self.assertFalse(formatted_match('date_sampled','8/7','87'))
        self.assertFalse(formatted_match('serial_number','PP0004037','VP004037'))

    def test_precision_is_not_invented(self):
        self.assertFalse(formatted_match('date_sampled','9/20','09/2020'))
        self.assertTrue(formatted_match('date_sampled','9/20','09/2020','month_year'))
        self.assertFalse(formatted_match('date_sampled','9/2026','09/01/2026'))


if __name__=='__main__':unittest.main()
