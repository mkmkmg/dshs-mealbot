import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_kakao import make_html, make_text, publish


class TestBotReadablePage(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 28)
        self.rows = {'2026-10-28': {'date': '2026-10-28', 'dinner': ['로제순살찜닭', '허니버터감자칩']}}

    def test_menu_and_date(self):
        page = make_html(self.day, self.rows, '2026-10-28T08:00:00Z', '오늘')
        self.assertIn('2026년 10월 28일 (수)', page)
        self.assertIn('<li>로제순살찜닭</li>', page)
        self.assertIn('허니버터감자칩', make_text(self.day, self.rows, 'verified'))

    def test_missing_is_not_closed(self):
        page = make_text(date(2026, 11, 2), self.rows, 'verified')
        self.assertIn('아직 확인되지', page)
        self.assertIn('급식 미운영으로 확정된 것은 아닙니다', page)

    def test_html_escaped(self):
        rows = {'2026-10-28': {'dinner': ['<script>alert(1)</script>']}}
        page = make_html(self.day, rows, '', '오늘')
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)

    def test_generates_today_tomorrow_week(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            data = path / 'meals.json'
            data.write_text('{"updatedAt":"2026-10-28T09:47:40Z","days":[{"date":"2026-10-28","dinner":["로제순살찜닭"]}]}', encoding='utf-8')
            publish(self.day, path, data)
            for file in ['kakao-today.html', 'kakao-today.txt', 'kakao-tomorrow.html', 'kakao-tomorrow.txt', 'kakao-week.txt', 'kakao-week.html']:
                self.assertTrue((path / file).exists(), file)
            self.assertIn('로제순살찜닭', (path / 'kakao-today.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
