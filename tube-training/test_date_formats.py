import unittest
from date_formats import format_sample_date as fmt


class DateTests(unittest.TestCase):
    def test_full_and_mixed_separators(self):
        for raw in ['9.27.26','9.27-26','9/27/2026']:
            self.assertEqual(fmt(raw)['formatted'],'09/27/2026')

    def test_partial_policy(self):
        self.assertEqual(fmt('9-26')['formatted'],'09/2026')
        self.assertIsNotNone(fmt('9-26')['assumption'])
        self.assertEqual(fmt('9/2026')['formatted'],'09/2026')
        self.assertEqual(fmt('9/20',two_part='review')['status'],'needs_review')

    def test_do_not_guess_or_accept_invalid(self):
        for value in ['9120','87','e912866','2/30/26','13/2026','8/7']:
            self.assertEqual(fmt(value)['status'],'needs_review')
        self.assertEqual(fmt('')['status'],'blank')


if __name__=='__main__':unittest.main()
