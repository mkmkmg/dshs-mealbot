import unittest
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect import normalize, collect


class TestCollector(unittest.TestCase):
    def test_valid_dinner(self):
        row = normalize({'isoDate': '2026-10-28', 'lunch': ['밥'], 'dinner': ['로제순살찜닭'], 'dinnerSource': 'mcp'})
        self.assertEqual(row['dinner'], ['로제순살찜닭'])
        self.assertEqual(row['dinnerStatus'], 'listed')
        self.assertEqual(row['dinnerSource'], 'mcp')

    def test_missing_dinner_unknown_not_closed(self):
        row = normalize({'isoDate': '2026-11-02', 'lunch': ['율무밥']})
        self.assertIsNone(row['dinner'])
        self.assertEqual(row['dinnerStatus'], 'not_provided')

    def test_other_year_or_date_rejected(self):
        self.assertIsNone(normalize({'isoDate': '2025-11-02', 'dinner': ['x']}, expected=date(2026,11,2)))
        self.assertIsNone(normalize({'isoDate': 'not-a-date', 'dinner': ['x']}))

    def test_bad_menu_rejected(self):
        self.assertIsNone(normalize({'isoDate': '2026-10-28', 'dinner': ['x'] * 40})['dinner'])

    def test_weekly_and_specific(self):
        observed = []
        def fake_fetch(params=None):
            if params is None:
                return [
                    {'isoDate': '2026-10-28', 'lunch': ['중식'], 'dinner': ['석식'], 'dinnerSource': 'mcp'},
                    {'isoDate': '2026-10-29', 'lunch': ['중식2'], 'dinner': ['석식2']},
                    {'isoDate': '2026-10-30', 'lunch': ['중식3']},
                ]
            observed.append(params['date'])
            month, day = map(int, params['date'].split('/'))
            if (month, day) == (11, 2):
                return {'isoDate': '2026-11-02', 'lunch': ['율무밥']}
            return {}
        result, errors, succeeded, count = collect(fake_fetch, today=date(2026,10,28), sleep=lambda _: None)
        rows = {row['date']: row for row in result['days']}
        self.assertEqual(rows['2026-10-28']['dinner'], ['석식'])
        self.assertIsNone(rows['2026-11-02']['dinner'])
        self.assertIn('11/2', observed)
        self.assertGreaterEqual(succeeded, 2)
        self.assertLessEqual(count, 10)


if __name__ == '__main__':
    unittest.main()
